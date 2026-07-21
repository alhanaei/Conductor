# Event-Assisted Monitoring

Conductor's runtime monitor is event-first. A foreground monitor consumes tmux
control-mode records and Linux filesystem notifications, normalizes them into a
durable ledger, and refreshes only the affected task or lane. It does not run a
periodic pane-capture loop and does not install a service.

## Authority Boundary

Runtime events are telemetry. They can update runtime projections and operator
signals, but they cannot declare work complete.

- Pane output can correlate to one task, classify that task's stable lane, and
  surface `blocked_prompt`. It cannot set `ready_for_merge` or `complete`.
- A new or changed `result.md` can request
  `CompletionEngine.verify_ready_results`. The existing verification checks are
  still the only path to `ready_for_merge`.
- Normal `advance`, merge approval, and close gates remain mandatory after
  verification. A worker result and a terminal pane message are claims, not
  verdicts.
- Operator and Hermes projections must be checked against artifacts under
  `.conductor/`; terminal text is never accepted as authority by itself.

## Runtime Artifacts

The monitor writes these artifacts lazily:

| Artifact | Purpose |
| --- | --- |
| `.conductor/runtime/events.jsonl` | Append-only, deduplicated normalized events |
| `.conductor/runtime/cursors/<source>.json` | Last processed position per source |
| `.conductor/runtime/gaps/<event>.json` | Audited source-loss or explicit-refresh evidence |
| `.conductor/runtime/unresolved/<event>.json` | Missing, ambiguous, or conflicting provenance |

Event identity is stable for a source and source key. Replaying the same event
therefore performs no second lane refresh or verification request.

## Correlation

Task-targeted processing requires a task ID resolved to a dispatch with a stable
lane target and, for git-planned or git-created work, an assigned worktree path.
The monitor may enrich omitted source fields from that dispatch record because
it is the authoritative assignment. It refuses to guess when dispatch metadata
is incomplete.

The following cases are persisted as `unresolved_event` or
`workspace_provenance_mismatch` and trigger no targeted action:

- no matching or multiple matching active dispatches;
- a dispatch without a stable lane target;
- a git dispatch without its assigned worktree path;
- conflicting task, track, lane, or worktree facts;
- an event claiming a worktree for a dispatch that has none.

Historical pane events and events for terminal tasks remain telemetry and do not
cause reclassification.

## Sources

### tmux control mode

One control client attaches per active tmux session. `%output` and pane
lifecycle records are parsed without shell interpolation. Pane ownership is
accepted only when the pane-to-session/window map is known. Malformed records
are counted and ignored. EOF, process death, or `%exit` reports a source gap.

### Filesystem notifications

A stdlib-only Linux inotify adapter watches track task directories and message
bus directories. It emits content-addressed create/modify events for:

- `result.md`
- `status.json`
- `verification.json`
- `verification.md`
- `verdict.json`
- files below a track's `.message-bus/`

Queue overflow reports a source gap. There is no stat-poll fallback.

## Operator Commands

Start the monitor in the foreground:

```bash
python -m conductor monitor run --track <track_id> --json
```

The process owns and closes its control-mode and inotify sources. Stop it with
the foreground process controls. `--once` is available for diagnostics and
disposable checks; no command installs or starts a daemon.

Read health without starting a service:

```bash
python -m conductor monitor status --track <track_id> --json
python -m conductor doctor --json
```

Monitor status reports tmux/inotify capability, persisted cursors, latest event
freshness, unresolved count, and recorded gaps. Doctor reports whether the host
supports tmux control mode and filesystem notifications.

Run the engineering loop as one explicit tick:

```bash
python -m conductor loop --track <track_id> --json
```

The former recurring watch flag is rejected with a migration command. Blocked
prompt queries and operator summaries read fresh event-ledger observations; they
do not sweep every active pane.

## Recovery

Steady state is event-driven. Reconciliation is a bounded recovery operation,
not a fallback polling mode.

| Trigger | Recorded action |
| --- | --- |
| Monitor start with no cursor | `event_stream_gap`, then one reconciliation |
| tmux control disconnect or process exit | `event_stream_gap`, then one reconciliation |
| inotify queue overflow | `event_stream_gap`, then one reconciliation |
| Explicit operator refresh | audited gap, then one reconciliation |
| Explicit operator reconcile | audited gap, then one reconciliation |

Use explicit recovery when source state is suspect:

```bash
python -m conductor monitor refresh --track <track_id> --reason "source state suspect" --json
python -m conductor monitor reconcile --track <track_id> --reason "controlled recovery" --json
```

Each reconciliation is non-reentrant and scans active dispatches once. It may
refresh those lanes once and inspect result artifacts once. Repeated delivery of
the same gap event is deduplicated. Returning to steady state resumes event
reads without periodic `capture-pane` activity.

## Disposable Proof

A release proof should use a disposable state root and retain the emitted
artifacts. It must demonstrate all of the following:

1. A correlated pane-output event produces one blocked-prompt signal without
   changing task authority.
2. A controlled source disconnect produces one gap and one reconciliation even
   when polled again.
3. An empty source batch causes no lane refresh or pane capture.
4. A `result.md` event retains task, stable lane, and assigned-worktree
   provenance and reaches `ready_for_merge` only through the existing verifier.
5. The disposable track reaches complete only through advance, merge approval,
   and close.
6. Live gated smokes pass for tmux control mode and inotify on the target host.

Inspect monitor JSON, `runtime/events.jsonl`, gap/unresolved files, task result
and verification artifacts, and the final summary. Record any discrepancy as a
mismatch; do not resolve it from terminal appearance alone.
