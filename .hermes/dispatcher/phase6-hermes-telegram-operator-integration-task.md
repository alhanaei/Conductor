# Conductor Phase 6 — Hermes / Telegram Operator Integration

## Objective
Implement Phase 6 from `.hermes/deep-analysis/next-build-plan.md`: make Conductor operable from Hermes/Telegram-style chat surfaces through safe, artifact-grounded command outputs and notifications.

Ahmed said “proceed” after Phase 5 was Hermes-verified. Treat Phase 6 implementation as authorized.

## Baseline
- Project root: `/home/alhanaei/projects/Conductor`
- Phase 5 verified checkpoint: `.hermes/dispatcher/runs/run_conductor-phase5-verification-gated-completion_20260629T064500Z/checkpoint.json`
- Current tests: `python -m pytest -q` exits 0 with 151 passing.
- Current CLI includes: `init`, `go`, `approve plan`, `dispatch`, `task status`, `followup`, `nudge`, `verify`, `fix`, `approve merge`, `close`, `reconcile`, `status`.

## Source documents
- `.hermes/deep-analysis/next-build-plan.md` lines 225-241
- Existing code: `src/conductor/cli.py`, `status.py`, `completion.py`, `dispatch.py`, `store.py`, `models.py`, `message_bus.py`
- Existing tests: `tests/test_cli_phase5.py`, `tests/test_completion.py`, `tests/test_dispatch.py`

## Phase 6 deliverables

### 1. Telegram-safe status summaries
Add a stable operator summary renderer that produces short chat-safe Markdown/plain text from current Conductor state.

Required command surface, unless an equivalent shape is clearly better:

```bash
python -m conductor operator summary --json
python -m conductor operator summary --track <id> --json
python -m conductor operator summary --track <id> --format telegram
```

Requirements:
- No raw huge JSON dumps by default.
- Include artifact paths, track state, plan approval, dispatched/verified/closed counts, and next action.
- Telegram-safe: avoid broken Markdown, avoid massive messages, deterministic truncation.
- Ground all claims in existing artifacts (`metadata.json`, task status, verification, summary/reconciliation, dispatcher run artifacts when present).

### 2. Terminal-state notifications
Add deterministic notification payloads for terminal or operator-relevant states.

Suggested command:

```bash
python -m conductor operator notify --track <id> --json
```

Payload should include:
- `signal`: e.g. `needs_approval`, `needs_verification`, `ready_for_merge`, `closed`, `blocked`, `heartbeat`
- `severity`: `info|success|warning|error`
- `track_id`, optional `task_id`
- `summary`
- `next_action`
- `artifact_refs`
- `telegram_text` or equivalent rendered text
- a deterministic `dedupe_key`

### 3. 5-minute heartbeat summaries for active long runs
Add pure heartbeat policy and command support without starting background daemons.

Suggested command:

```bash
python -m conductor operator heartbeat --track <id> --json
python -m conductor operator heartbeat --track <id> --now <iso> --json
```

Requirements:
- Pure/deterministic function that decides whether a heartbeat is due.
- Default cadence: 5 minutes.
- Terminal tracks do not heartbeat unless forced/explicitly requested.
- Heartbeat body says `no change` when no state changed; no filler.
- Persist last heartbeat metadata if needed under `.conductor/tracks/<id>/operator/`.

### 4. Approval request payloads
Expose approval payloads for plan approval and merge approval, chat-safe and artifact-grounded.

Suggested commands:

```bash
python -m conductor operator approval --track <id> --kind plan --json
python -m conductor operator approval --track <id> --kind merge --json
```

Requirements:
- Include exact CLI command the operator can run.
- Include risk/context summary and artifact links.
- Refuse/mark not-needed when already approved.
- For merge approval, include verification status evidence.

### 5. Artifact links
Add stable artifact reference collection for chat surfaces.

Requirements:
- Include paths to `spec.md`, `plan.md`, per-task `task.md`, `result.md`, `verification.json/md`, `summary.md`, `reconciliation.md` when present.
- Paths are local absolute or project-relative, consistently represented.
- Avoid exposing secret-containing raw logs; only known Conductor artifacts.

### 6. Hermes verification hook
Add a hook/command that outputs the exact verification commands Hermes should run next, grounded in track/task state.

Suggested command:

```bash
python -m conductor operator verify-hook --track <id> --json
```

Requirements:
- Return deterministic commands and expected pass/fail conditions.
- For unverified dispatched tasks, include `python -m conductor verify --track <id> --json`.
- For merge-ready tracks, include `python -m conductor approve merge --track <id> --json` only as a suggested operator action, not auto-run.
- For closed tracks, include summary/reconcile checks.

## Non-goals
- Do not integrate with the real Telegram Bot API.
- Do not modify Hermes Agent config/profile/gateway.
- Do not create cron jobs or long-running daemons.
- Do not expose network services or ports.
- Do not perform destructive git operations.
- Do not paste large bodies into lanes.

## Implementation guidance
- Prefer a new module like `src/conductor/operator.py` for pure rendering/notification/heartbeat/approval/hook logic.
- Keep CLI thin in `cli.py`.
- Use existing `ConductorStore` paths and models where possible.
- Add tests with temporary stores; no real Telegram, tmux, or provider lane required.
- Keep outputs stable and JSON-friendly.
- Advanced Markdown is optional; prioritize deterministic text that Telegram will not mangle.

## Acceptance criteria
- Ahmed can get a chat-safe summary for all tracks or one track without reading raw files manually.
- Ahmed can see what approval is needed and the exact command to approve.
- Ahmed can get terminal-state notification payloads grounded in artifacts.
- Heartbeat due/not-due behavior is deterministic and test-covered.
- Artifact links are surfaced and bounded.
- Hermes verification hook tells Hermes which commands to run next.
- Existing Phase 1-5 behavior and tests still pass.

## Tests to add
Add focused tests for:
- `operator summary --format telegram` returns bounded text with track state, plan status, next action, and artifact links.
- `operator notify` returns expected signals for: plan approval needed, verification needed, ready_for_merge, closed/complete, blocked/needs_fix.
- `operator heartbeat` due/not-due at 5-minute cadence and terminal-track suppression.
- `operator approval --kind plan` includes exact approve command and not-needed state after approval.
- `operator approval --kind merge` refuses/not-ready before verification and includes verification evidence after verify.
- `operator verify-hook` returns verify command before verification and summary/reconcile checks after close.
- JSON-after-subcommand behavior for new operator commands.

## Verification commands
Run and record exact output:

```bash
cd /home/alhanaei/projects/Conductor
python -m pytest -q
rm -rf /tmp/conductor-phase6-smoke && mkdir -p /tmp/conductor-phase6-smoke
cd /tmp/conductor-phase6-smoke
PYTHONPATH=/home/alhanaei/projects/Conductor/src python -m conductor init
TRACK=$(PYTHONPATH=/home/alhanaei/projects/Conductor/src python -m conductor go --plan-only "Build a small dashboard" --json | python -c 'import json,sys; print(json.load(sys.stdin)["track_id"])')
PYTHONPATH=/home/alhanaei/projects/Conductor/src python -m conductor operator summary --track "$TRACK" --format telegram
PYTHONPATH=/home/alhanaei/projects/Conductor/src python -m conductor operator approval --track "$TRACK" --kind plan --json
PYTHONPATH=/home/alhanaei/projects/Conductor/src python -m conductor approve plan --track "$TRACK" --json
PYTHONPATH=/home/alhanaei/projects/Conductor/src python -m conductor dispatch --track "$TRACK" --json
PYTHONPATH=/home/alhanaei/projects/Conductor/src python -m conductor operator notify --track "$TRACK" --json
PYTHONPATH=/home/alhanaei/projects/Conductor/src python -m conductor operator verify-hook --track "$TRACK" --json
PYTHONPATH=/home/alhanaei/projects/Conductor/src python -m conductor operator heartbeat --track "$TRACK" --now 2026-06-29T12:00:00Z --json
```

If implementing more complete smoke, simulate worker result and run Phase 5 verify/approve/close, then check `operator notify`, `operator summary`, and `verify-hook` on the closed track.

## Expected deliverables
When complete:
1. Update run-scoped `.hermes/dispatcher/runs/<run_id>/result.md` with summary, files changed, exact verification output, and limitations/non-goals.
2. Update run-scoped `.hermes/dispatcher/runs/<run_id>/checkpoint.json` with `state: "ready_for_review"` or `state: "blocked"`.
3. Mirror result/checkpoint to top-level `.hermes/dispatcher/result.md` and `.hermes/dispatcher/checkpoint.json` if current run pattern expects that.
4. Update README status/usage lightly if appropriate.
5. Print `TASK_COMPLETE` only after artifacts are written.
