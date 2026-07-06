# Conductor Phase 2 — Goal Intake and Plan Artifacts

## Objective
Implement Phase 2 from `.hermes/deep-analysis/next-build-plan.md`: convert an operator goal into a durable Conductor track with `spec.md`, `plan.md`, metadata, deterministic task DAG scaffolding, access-list placeholders, and explicit plan approval state. Do **not** implement tmux lane automation, worker dispatch, worktrees, verification loops, or Telegram integration in this phase.

## Authorization
Ahmed said: “Lets proceed with conductor project.” Treat Phase 2 implementation as authorized. Phase 1 has been independently verified by Hermes:
- `python -m pytest -q` => 47 passed
- `python -m conductor init/status/doctor --json` works with `--json` after the subcommand

## Source documents
- `.hermes/deep-analysis/next-build-plan.md` lines 98-129
- `.hermes/deep-analysis/architecture-map.md` core subsystems / workflow graph / unified messaging
- `.hermes/deep-analysis/open-questions.md` says deterministic/manual task split first is recommended

## Scope
Implement only the goal-intake + plan artifact layer.

Required CLI surface:
```bash
python -m conductor go --plan-only "<goal>" --json
python -m conductor plan review --track <track_id> --json
python -m conductor approve plan --track <track_id> --json
```

Acceptable equivalent command shapes are okay if well justified, but preserve the user-facing concepts: `go`, `plan review`, `approve plan`.

## Required behavior
1. `go --plan-only "<goal>"`
   - Ensures `.conductor/` exists or returns a clear actionable error.
   - Creates a new track using the Phase 1 state substrate.
   - Writes a real `spec.md` with goal, assumptions, non-goals, acceptance criteria placeholder, and open questions placeholder.
   - Writes a real `plan.md` with a deterministic task DAG scaffold, dependencies, likely files/surfaces placeholder, verification criteria placeholder, and approval status.
   - Updates `metadata.json` with track goal, plan status, tasks, approvals, timestamps, and schema version.
   - No worker dispatch.

2. Task DAG model
   - Add or extend models as needed for planned tasks / dependencies / access lists.
   - Keep runtime stdlib-only.
   - Workers should not automatically see all context; include explicit access-list field(s) per task.

3. Plan review gate
   - `plan review --track <id> --json` returns a machine-readable summary of the generated spec/plan/task count/status and whether approval is pending.

4. Plan approval
   - `approve plan --track <id> --json` persists approval state and timestamp.
   - Approval should be separate from track creation.
   - Re-approving should be idempotent or return a clear state response.

5. Tests
   - Add tests for CLI and model/store behavior.
   - Include JSON-output tests with `--json` after the subcommand, matching Phase 1 convention.
   - Include restart/persistence behavior: a fresh process/read sees generated plan + approval state.

## Non-goals
- No `conductor dispatch` implementation.
- No tmux lane adapter.
- No provider launchers.
- No worktree creation.
- No Telegram/Hermes integration.
- No model-assisted planner call.
- Do not initialize git unless Ahmed explicitly asks.

## Verification commands
Run and record exact output:
```bash
cd /home/alhanaei/projects/Conductor
python -m pytest -q
rm -rf /tmp/conductor-phase2-smoke && mkdir -p /tmp/conductor-phase2-smoke
cd /tmp/conductor-phase2-smoke
PYTHONPATH=/home/alhanaei/projects/Conductor/src python -m conductor init
PYTHONPATH=/home/alhanaei/projects/Conductor/src python -m conductor go --plan-only "Build a small dashboard" --json
PYTHONPATH=/home/alhanaei/projects/Conductor/src python -m conductor plan review --track <track_id> --json
PYTHONPATH=/home/alhanaei/projects/Conductor/src python -m conductor approve plan --track <track_id> --json
PYTHONPATH=/home/alhanaei/projects/Conductor/src python -m conductor status --json
```
Parse the JSON outputs in Python during verification.

## Expected deliverables
When complete:
1. Update run-scoped `.hermes/dispatcher/runs/<run_id>/result.md` with:
   - summary
   - files changed
   - exact verification output
   - limitations / non-goals
2. Update run-scoped `.hermes/dispatcher/runs/<run_id>/checkpoint.json` with `state: "ready_for_review"` or `state: "blocked"`.
3. Mirror result/checkpoint to top-level `.hermes/dispatcher/result.md` and `.hermes/dispatcher/checkpoint.json` if the existing dispatcher run pattern expects that.
4. Print `TASK_COMPLETE` only after artifacts are written.
