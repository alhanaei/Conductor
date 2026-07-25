# Event-Assisted Monitoring Implementation Plan

> **For Hermes:** Dispatch through Conductor in a fresh, formally allocated worktree only after the Phase A runtime-contract track has independently verified and merged.

**Goal:** Replace Conductor's timer-driven lane/prompt/result polling with a durable event-assisted monitor driven by tmux control-mode output/lifecycle events and filesystem notifications under `.conductor/`.

**Architecture:** Add a Conductor-owned runtime event ledger and cursor, a tmux control-mode source, and an artifact filesystem source. Both feed a deduplicating monitor that refreshes only the affected lane/task projection. `event_stream_gap` triggers one bounded reconciliation capture; events remain telemetry and cannot advance task state without the existing verification gate.

**Tech Stack:** Python 3.9+, stdlib subprocess/asyncio/dataclasses/pathlib, tmux control mode, Linux filesystem notification adapter (minimal explicit dependency if stdlib cannot provide an event API), pytest.

**Authorization:** authorized (Ahmed, 2026-07-19T12:01:50+04:00), dependency-gated on verified/merged Phase A.

**Definition of Done:** `software-development/definition-of-done`; every task requires RED → GREEN → REFACTOR evidence and the full Conductor suite.

---

## Preconditions

- The approved feature spec is `.hermes/deep-analysis/feature-spec-standalone-command-center.md`.
- The active Phase A track `track_2b5a8390` must complete `verify → advance → review verdict → merge → close` before any Phase B worktree is allocated.
- Capture `git status --short` and the changed-path snapshot before new-track dispatch. Existing main-checkout WIP is protected and is not Phase B scope.
- Phase B uses a fresh Conductor track and a formally assigned worktree. It must not modify the active Phase A worktree.

## Non-Negotiable Contracts

1. No periodic `capture-pane` calls in steady state.
2. No `time.sleep` monitor loop for worker status, result artifacts, or blocked prompts.
3. A terminal event is telemetry only; only current `CompletionEngine` verification advances a task.
4. Correlation requires task ID + stable lane target + assigned worktree where applicable; otherwise persist `unresolved_event`.
5. Restart, explicit refresh, lost tmux-control connection, missing cursor, and filesystem watcher overflow emit `event_stream_gap` then run one bounded reconciliation.
6. Existing one-shot `conductor loop` semantics remain available. The recurring `--watch` polling path is removed or explicitly rejected in favor of the event monitor; it must not silently degrade into timer polling.
7. No Herdr runtime, API, package, binary, plugin, or source is introduced.

## Dependency Graph

- Task 1 — Runtime event schema and durable ledger → none
- Task 2 — tmux control-mode event source → Task 1
- Task 3 — filesystem artifact event source → Task 1
- Task 4 — event monitor/correlation/projection update → Tasks 2, 3
- Task 5 — CLI migration and blocked-prompt consumer migration → Task 4
- Task 6 — documentation, disposable smoke, and review → Task 5

Tasks 2 and 3 may run in parallel only if they do not edit shared event-schema files after Task 1 lands.

## Task 1: Runtime Event Schema and Ledger

**Objective:** Persist append-only, deduplicated runtime/artifact events with a durable cursor and explicit unresolved/gap outcomes.

**Files:**
- Create: `src/conductor/runtime/events.py`
- Modify: `src/conductor/store.py`
- Test: `tests/test_runtime_events.py`

**TDD requirements:**
1. Write failing tests for deterministic event IDs, duplicate suppression, source cursor persistence, `unresolved_event`, and `event_stream_gap` persistence.
2. Run `python -m pytest tests/test_runtime_events.py -q`; observe expected missing-module/API failure.
3. Add the smallest `RuntimeEvent`, `EventCursor`, and `RuntimeEventLedger` implementation.
4. Re-run the targeted test, then refactor only while green.

**Data layout:**

```text
.conductor/runtime/
  events.jsonl
  cursors/<source-id>.json
  unresolved/<event-id>.json
  gaps/<event-id>.json
```

**Acceptance criteria:**
- Event IDs are stable for equivalent source events.
- Duplicate source events do not re-run classification or append a second canonical event.
- Event records contain source, source event ID/content hash, timestamp, lane target/task/worktree when known, evidence reference, and confidence.
- Legacy `.conductor` state roots load without a runtime directory.

**Evidence:** targeted pytest output, persisted fixture files, `git diff --check`.

## Task 2: tmux Control-Mode Event Source

**Objective:** Convert tmux control-mode pane-output and lifecycle records into bounded normalized events without periodic `capture-pane` reads.

**Files:**
- Create: `src/conductor/runtime/tmux_control.py`
- Modify: `src/conductor/tmux.py`
- Test: `tests/test_tmux_control.py`

**TDD requirements:**
1. Write failing parser tests for `%output`, pane/session/window lifecycle records, malformed control records, and disconnect handling.
2. Run `python -m pytest tests/test_tmux_control.py -q`; verify RED.
3. Implement a narrow `TmuxControlClient` that starts explicit control mode, parses a stream incrementally, and exposes normalized source events.
4. Verify GREEN without spawning real tmux in unit tests; use an injected line reader/process seam.

**Acceptance criteria:**
- No production path invokes `capture-pane` per timer tick.
- `%output` is tied to the stable lane target only when the pane/session mapping is known.
- Control-client disconnect/invalid cursor emits `event_stream_gap`, never invents a task owner.
- Process termination is explicit and idempotent; no unmanaged background process is created by unit commands.

**Evidence:** targeted pytest output and captured synthetic control-mode records.

## Task 3: Filesystem Artifact Event Source

**Objective:** Turn result/status/verification artifact mutations into normalized events so verification is scheduled from durable evidence rather than timer scans.

**Files:**
- Create: `src/conductor/runtime/fs_events.py`
- Modify: `pyproject.toml` only if a minimal Linux event dependency is required
- Test: `tests/test_fs_events.py`

**TDD requirements:**
1. Write failing tests for create/modify events under a task artifact directory, path-to-track/task correlation, coalescing, watcher overflow, and ignored paths.
2. Run `python -m pytest tests/test_fs_events.py -q`; verify RED.
3. Implement an injected watcher interface with a Linux notification implementation. Do not implement file-stat polling as a fallback.
4. Verify GREEN with a deterministic fake watcher; keep live inotify smoke tests separately gated.

**Acceptance criteria:**
- A new/changed `result.md` produces one correlated artifact event.
- `verification.*`, `status.json`, `verdict.json`, and message-bus events are recognized without triggering broad rescans.
- Watch overflow produces `event_stream_gap` and one bounded reconciliation request.
- Unrelated files outside `.conductor/` are ignored.

**Evidence:** targeted pytest output and fake-watcher event trace.

## Task 4: Event Monitor, Correlation, and Targeted Reclassification

**Objective:** Consume ledger events and update only the impacted lane/task projection while preserving the verification authority boundary.

**Files:**
- Create: `src/conductor/runtime/monitor.py`
- Modify: `src/conductor/blocked_prompts.py`
- Modify: `src/conductor/operator.py`
- Test: `tests/test_runtime_monitor.py`
- Test: `tests/test_operator.py`

**TDD requirements:**
1. Add failing tests proving fresh pane output invokes prompt classification for one matching lane, fresh result artifacts schedule a verification-ready signal, stale/historical records do not reclassify, and gap recovery is bounded once.
2. Run `python -m pytest tests/test_runtime_monitor.py tests/test_operator.py -q`; verify RED.
3. Implement `EventMonitor.process(event)` and correlation rules; read blocked-prompt state from fresh ledger evidence rather than calling `LaneAdapter.status()` across all active tasks.
4. Run targeted tests and then the related completion/dispatch suites.

**Acceptance criteria:**
- An output event may update telemetry and notify Hermes, but cannot set `ready_for_merge` or `complete`.
- A result event may request/run existing `verify_ready_results`; the existing verifier remains the only promotion path.
- A single affected lane/task is refreshed; idle lanes are not captured.
- Mismatched worktree/lane/task data creates `unresolved_event` or `workspace_provenance_mismatch`.

**Evidence:** per-event assertions, event ledger records, existing gate-sequence tests still green.

## Task 5: CLI Migration and Monitor Lifecycle

**Objective:** Expose an explicit event-monitor command and remove steady-state timer polling from the recurring loop interface.

**Files:**
- Modify: `src/conductor/cli.py`
- Modify: `src/conductor/doctor.py`
- Test: `tests/test_cli_phase5.py`
- Test: `tests/test_doctor.py` if present, otherwise create `tests/test_runtime_monitor_cli.py`

**TDD requirements:**
1. Write failing CLI tests that prove an event monitor can report source health/cursors/gaps, `loop` stays a single tick, and `loop --watch` never sleeps/polls.
2. Run the narrow CLI test selection; verify RED.
3. Add a `conductor monitor` command group with explicit `status`, `run`, `refresh`, and `reconcile` semantics. `run` owns control-mode/filesystem sources for its foreground lifetime; it is not installed as a daemon by this task.
4. Migrate `lane blocked` and operator surfaces to event-backed fresh observations.

**Acceptance criteria:**
- `conductor loop --watch` is refused with a migration message or maps only to the event monitor without timer polling.
- `conductor monitor status --track <id> --json` reports source health, last cursor, event freshness, and recorded gaps.
- `conductor monitor refresh` is explicit, audited, and performs at most one bounded reconciliation.
- No command starts a service/daemon implicitly.

**Evidence:** CLI JSON contracts, no recurring sleep assertion, full relevant suite.

## Task 6: Documentation and Disposable End-to-End Proof

**Objective:** Prove native event-driven monitoring against one disposable Conductor track and document recovery/operator semantics.

**Files:**
- Modify: `README.md`
- Modify: `CONDUCTOR_USER_GUIDE.md`
- Modify: `.hermes/deep-analysis/standalone-command-center-architecture.md` if implementation differs
- Create: `.hermes/ui-runs/` evidence only if a command-center visual surface exists in this slice

**Agent verification:**
1. Run `python -m pytest tests/test_runtime_events.py tests/test_tmux_control.py tests/test_fs_events.py tests/test_runtime_monitor.py tests/test_cli_phase5.py -q`.
2. Run `python -m pytest -q`.
3. Run `git diff --check`.
4. In a disposable track, prove pane-output event → blocked prompt signal, artifact event → verification-ready signal, a controlled source disconnect → one `event_stream_gap` reconciliation, and no periodic `capture-pane` activity while idle.

**Hermes verification:** inspect the event-monitor JSON, event artifact paths, tmux control-session output, console/process errors, and compare displayed state with `.conductor` artifacts. Record any mismatch rather than accepting the terminal view as authority.

**Acceptance criteria:**
- Operator documentation states event-first monitoring, recovery-only reconciliation, and the no-authority rule.
- Disposable proof retains task/worktree provenance and completes through normal verify/advance/merge/close gates.
- No Herdr dependency appears in code, lockfiles, configuration, or commands.

## Global Verification

```bash
cd /home/alhanaei/projects/Conductor
python -m pytest tests/test_runtime_events.py tests/test_tmux_control.py tests/test_fs_events.py tests/test_runtime_monitor.py tests/test_cli_phase5.py -q
python -m pytest -q
git diff --check
```

## Dispatch Constraints

- Do not dispatch Phase B until Phase A is independently verified and merged.
- Every generated task must link this plan, the approved feature spec, the track Definition of Done, and its exact file scope.
- Use a distinct worktree for each implementation task; no work may occur in the main checkout or active Phase A worktree.
- A review task must produce `verdict.json` with `approve` or `reject` before merge eligibility.
