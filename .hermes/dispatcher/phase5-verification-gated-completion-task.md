# Conductor Phase 5 — Verification-Gated Completion

## Objective
Implement Phase 5 from `.hermes/deep-analysis/next-build-plan.md`: worker completion is not true completion. Add deterministic verification gates, evaluator artifacts, fix-loop counters, merge approval gate, resume reconciliation, and final operator summary rendering.

## Authorization
Ahmed said: “proceed” after Phase 4 was Hermes-verified. Treat Phase 5 implementation as authorized.

Verified baseline:
- Phase 1: durable state/message substrate complete.
- Phase 2: goal intake + plan artifacts complete.
- Phase 3: tmux lane adapter complete.
- Phase 4: worktree + dispatch loop complete.
- Current tests: `python -m pytest -q` exits 0 with 133 tests.

## Source documents
- `.hermes/deep-analysis/next-build-plan.md` lines 196-223
- `.hermes/deep-analysis/architecture-map.md` Verification Engine section
- Existing implementation in `src/conductor/`: dispatch, worktree, lanes, message_bus, status, store, models

## Required CLI surface
Implement these commands unless a minor equivalent shape is strongly justified:

```bash
python -m conductor verify --track <id> --json
python -m conductor fix --track <id> --task <task_id> --json
python -m conductor approve merge --track <id> --json
python -m conductor close --track <id> --json
```

## Required behavior

### 1. Verification gate runner
- `verify --track <id>` must inspect dispatched task records and worker result artifacts.
- A lane marker like `TASK_COMPLETE` or a worker-written result must **not** mark task complete by itself.
- Add explicit verification result artifacts per task, e.g. `tasks/<task_id>/verification.json` and `verification.md`.
- If verification passes, transition task to a state like `verified` / `ready_for_merge`.
- If verification fails, transition task to `needs_fix` or `blocked` with concrete evidence.
- Verification should support safe configured commands/placeholders where present, but deterministic artifact checks are enough for Phase 5 MVP.
- Persist verifier identity, timestamp, commands/evidence, pass/fail, and reason.

### 2. Evaluator result artifacts
- Verification evidence must be separate from worker claims.
- Store evaluator artifacts under task directory and surface them from `task status --json` and/or `status --json`.
- Keep evidence structured and machine-readable.

### 3. Fix-loop counter
- `fix --track <id> --task <task_id>` should increment fix attempt count.
- Write a fix artifact/follow-up using the Phase 4 artifact-reference pattern.
- Enforce a max attempts policy, e.g. default 3, with a clear refusal when exceeded unless an explicit override is added.
- Do not paste large bodies into lanes.

### 4. Merge approval gate
- `approve merge --track <id>` must require all relevant dispatched tasks to be verified/ready_for_merge.
- It should persist a separate merge approval record with timestamp/approver.
- Merge approval is independent from plan approval and worker completion.
- If tasks are unverified/failed/needs_fix, refuse with JSON-friendly evidence and non-zero exit.

### 5. Close/final summary
- `close --track <id>` should require merge approval.
- It should write a final operator summary artifact containing plan, dispatch, verification, merge approval, and close evidence.
- It should transition track/flow to closed only after verification + merge approval.
- No actual git merge is required in Phase 5 unless already safe and trivial; focus on the approval/closure semantics.

### 6. Resume reconciliation report
- Implement deterministic reconstruction from plan + metadata + message bus + task status + lane/worktree state.
- Save a reconciliation report artifact, e.g. `reconciliation.json` / `reconciliation.md`.
- Surface inconsistencies: missing task artifact, missing route/status, worker result present but verification missing, merge approval missing, etc.

## Non-goals
- No Telegram/Hermes operator integration; that is Phase 6.
- No model-assisted evaluator.
- No destructive git merge.
- No worker result claim is enough for completion.
- Do not initialize git unless Ahmed explicitly asks.

## Tests
Add focused tests for:
- worker result / `TASK_COMPLETE` alone does not complete a task
- verify pass writes verification artifacts and changes state to verified/ready_for_merge
- verify failure writes evidence and returns task to needs_fix/blocked
- fix increments attempt counter and refuses after max attempts
- approve merge refuses before verification and passes after all required tasks verified
- close refuses before merge approval and writes final summary after approval
- resume reconciliation detects missing verification / missing route/status / worker claim without verifier proof
- JSON-after-subcommand behavior for new CLI commands

Use fakes/fixtures; do not require real provider lanes.

## Verification commands
Run and record exact output:

```bash
cd /home/alhanaei/projects/Conductor
python -m pytest -q
rm -rf /tmp/conductor-phase5-smoke && mkdir -p /tmp/conductor-phase5-smoke
cd /tmp/conductor-phase5-smoke
PYTHONPATH=/home/alhanaei/projects/Conductor/src python -m conductor init
TRACK=$(PYTHONPATH=/home/alhanaei/projects/Conductor/src python -m conductor go --plan-only "Build a small dashboard" --json | python -c 'import json,sys; print(json.load(sys.stdin)["track_id"])')
PYTHONPATH=/home/alhanaei/projects/Conductor/src python -m conductor approve plan --track "$TRACK" --json
DISPATCH=$(PYTHONPATH=/home/alhanaei/projects/Conductor/src python -m conductor dispatch --track "$TRACK" --json)
TASK=$(printf '%s' "$DISPATCH" | python -c 'import json,sys; print(json.load(sys.stdin)["dispatched"][0]["task_id"])')
# simulate worker claim/result without verifier proof
mkdir -p .conductor/tracks/$TRACK/tasks/$TASK
printf 'TASK_COMPLETE\nworker says done\n' > .conductor/tracks/$TRACK/tasks/$TASK/result.md
PYTHONPATH=/home/alhanaei/projects/Conductor/src python -m conductor close --track "$TRACK" --json ; test $? -ne 0
PYTHONPATH=/home/alhanaei/projects/Conductor/src python -m conductor approve merge --track "$TRACK" --json ; test $? -ne 0
PYTHONPATH=/home/alhanaei/projects/Conductor/src python -m conductor verify --track "$TRACK" --json
PYTHONPATH=/home/alhanaei/projects/Conductor/src python -m conductor task status --track "$TRACK" --task "$TASK" --json
PYTHONPATH=/home/alhanaei/projects/Conductor/src python -m conductor approve merge --track "$TRACK" --json
PYTHONPATH=/home/alhanaei/projects/Conductor/src python -m conductor close --track "$TRACK" --json
PYTHONPATH=/home/alhanaei/projects/Conductor/src python -m conductor status --json
```

Parse JSON outputs in Python. It is acceptable if the MVP verifier pass criteria are deterministic artifact-based, as long as worker claims alone do not bypass `verify` and merge/close gates.

## Expected deliverables
When complete:
1. Update run-scoped `.hermes/dispatcher/runs/<run_id>/result.md` with summary, files changed, exact verification output, and limitations/non-goals.
2. Update run-scoped `.hermes/dispatcher/runs/<run_id>/checkpoint.json` with `state: "ready_for_review"` or `state: "blocked"`.
3. Mirror result/checkpoint to top-level `.hermes/dispatcher/result.md` and `.hermes/dispatcher/checkpoint.json` if current run pattern expects that.
4. Update README status/usage lightly if appropriate.
5. Print `TASK_COMPLETE` only after artifacts are written.
