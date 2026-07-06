# Conductor Phase 4 — Worktree and Dispatch Loop

## Objective
Implement Phase 4 from `.hermes/deep-analysis/next-build-plan.md`: approved tasks can be turned into dispatch-ready work artifacts with lane/worktree allocation, route decisions, worker heartbeat/status, follow-up/nudge command surfaces, and stale-risk classification. Keep this phase deterministic and safe; do not build verification-gated completion yet.

## Authorization
Ahmed said: “proceed” after Hermes verified Phase 3. Treat Phase 4 implementation as authorized.

Verified baseline:
- Phase 1: durable state/message substrate complete.
- Phase 2: goal intake + plan artifacts complete.
- Phase 3: tmux lane adapter complete.
- Current tests: `python -m pytest -q` exits 0 with 107 tests.

## Source documents
- `.hermes/deep-analysis/next-build-plan.md` lines 166-194
- `.hermes/deep-analysis/architecture-map.md` Scheduler / Router, State Store, Verification Engine boundaries
- Existing implementation in `src/conductor/`: planner/intake/lanes/message_bus/locks/status/store

## Required CLI surface
Implement these commands unless a minor equivalent shape is strongly justified:

```bash
python -m conductor dispatch --track <id> --json
python -m conductor task status --track <id> --task <task_id> --json
python -m conductor followup --track <id> --task <task_id> --body-file <path> --json
python -m conductor nudge --track <id> --task <task_id> --json
```

## Scope
Phase 4 should bridge the Phase 2 plan DAG and Phase 3 lane adapter, but should not claim verification completion.

Required deliverables:
1. worktree allocation policy
2. branch naming policy
3. task artifact writer
4. lane scheduler
5. route-decision records
6. worker heartbeat updater / status projection
7. follow-up/nudge command
8. stale-risk classifier

## Required behavior

### 1. Dispatch gate
- `dispatch --track <id>` must require an approved plan (`plan_status=approved` / approved track state).
- If not approved, return JSON-friendly refusal and non-zero exit.
- Only dispatch tasks whose dependencies are satisfied enough for this phase. Minimum acceptable: dispatch first `ready` task; later tasks remain pending.
- Do not mark the task complete. Valid lifecycle target is `dispatched` or `working` depending on safe lane submit result.

### 2. Worktree allocation and branch naming policy
- Define deterministic branch names, e.g. `conductor/<track_id>/<task_id>-<slug>`.
- If current project root is not a git repo, degrade cleanly:
  - still write task artifacts and status records
  - mark worktree mode as `not_git_repo` / `workspace_current_root`
  - do not run `git init`
- If git is available and repo is a git repo, create or plan isolated worktrees safely. Do not use destructive git commands.

### 3. Task artifact writer
- For each dispatched task, write a compact task artifact under `.conductor/tracks/<track_id>/tasks/<task_id>/task.md` or equivalent.
- Include objective, dependency/access-list scope, source spec/plan refs, expected result artifact path, heartbeat/status path, and verification placeholder refs.
- Large bodies must stay in files; lane submission should use artifact references only.

### 4. Lane scheduler and route-decision records
- Deterministically select a lane/provider for the task.
- Minimum policy: provider from task kind/default (`claude` for clarify/design, `codex` for implement/test, `claude` for review) with fallback to configured/default lane target.
- Save route decision records with inputs, selected lane, reason, timestamp.
- Do not assume the target provider pane is ready; call/use Phase 3 status/classifier before submit.

### 5. Dispatch submit behavior
- Use Phase 3 lane adapter safety: submit only short artifact reference and only if lane is `provider_ready` unless an explicit safe `--force` is implemented.
- If lane is not ready, create task artifacts and route decision, record blocked/pending-lane state, and return a clear JSON status. This should not be treated as full failure if artifacts are ready.

### 6. Task status and projections
- `task status --track <id> --task <task_id> --json` should return task state, route decision, lane state, worktree/workspace info, artifact paths, heartbeat timestamps, blocker/stale-risk fields.
- Global `status --json` should remain valid and may include task/run summaries if cleanly integrated.

### 7. Follow-up and nudge
- `followup --body-file <path>` writes a follow-up artifact and message/event for the task. It should not paste large body text directly into a lane.
- `nudge` writes/attempts a short nudge artifact-reference instruction and event.
- If lane is not ready, record pending follow-up/nudge state rather than unsafe submit.

### 8. Stale-risk classifier
- Implement deterministic stale-risk classification from task status, heartbeat age, lane readiness, and recent message/event timestamps.
- Minimum states: `none`, `low`, `medium`, `high` or similar.
- Blocked/stale tasks must be visible through task status / message bus / events.

## Non-goals
- No Phase 5 verification gate runner.
- No worker-claim-to-complete promotion.
- No merge approval gate.
- No Telegram/Hermes operator integration.
- No model-assisted routing.
- Do not initialize git unless Ahmed explicitly asks.
- Do not paste full task/follow-up bodies into tmux lanes.

## Tests
Add focused tests for:
- dispatch refuses unapproved plan
- approved plan dispatch writes task artifact and status record
- non-git repo degrades cleanly with worktree policy status
- branch naming policy is deterministic/safe
- route-decision record is written
- lane-not-ready results in pending/blocked-lane state, not unsafe submit
- `task status` returns expected JSON fields
- `followup` writes artifact/event and does not paste body
- `nudge` records event and respects lane readiness
- stale-risk classifier behavior with fresh/stale heartbeat inputs

Use fakes/monkeypatches for lane adapter and git/worktree behavior; do not require real provider lanes in unit tests.

## Verification commands
Run and record exact output:

```bash
cd /home/alhanaei/projects/Conductor
python -m pytest -q
rm -rf /tmp/conductor-phase4-smoke && mkdir -p /tmp/conductor-phase4-smoke
cd /tmp/conductor-phase4-smoke
PYTHONPATH=/home/alhanaei/projects/Conductor/src python -m conductor init
TRACK=$(PYTHONPATH=/home/alhanaei/projects/Conductor/src python -m conductor go --plan-only "Build a small dashboard" --json | python -c 'import json,sys; print(json.load(sys.stdin)["track_id"])')
PYTHONPATH=/home/alhanaei/projects/Conductor/src python -m conductor dispatch --track "$TRACK" --json ; test $? -ne 0
PYTHONPATH=/home/alhanaei/projects/Conductor/src python -m conductor approve plan --track "$TRACK" --json
PYTHONPATH=/home/alhanaei/projects/Conductor/src python -m conductor dispatch --track "$TRACK" --json
PYTHONPATH=/home/alhanaei/projects/Conductor/src python -m conductor task status --track "$TRACK" --task <task_id> --json
printf 'follow-up body' > /tmp/conductor-followup.md
PYTHONPATH=/home/alhanaei/projects/Conductor/src python -m conductor followup --track "$TRACK" --task <task_id> --body-file /tmp/conductor-followup.md --json
PYTHONPATH=/home/alhanaei/projects/Conductor/src python -m conductor nudge --track "$TRACK" --task <task_id> --json
PYTHONPATH=/home/alhanaei/projects/Conductor/src python -m conductor status --json
```

Parse JSON outputs in Python during verification. For dispatch, it is acceptable if the task becomes `pending_lane` / `blocked_lane` because no provider lane is ready in the smoke environment, as long as artifacts, route decisions, and status projections are correct and safe.

## Expected deliverables
When complete:
1. Update run-scoped `.hermes/dispatcher/runs/<run_id>/result.md` with summary, files changed, exact verification output, and limitations/non-goals.
2. Update run-scoped `.hermes/dispatcher/runs/<run_id>/checkpoint.json` with `state: "ready_for_review"` or `state: "blocked"`.
3. Mirror result/checkpoint to top-level `.hermes/dispatcher/result.md` and `.hermes/dispatcher/checkpoint.json` if current run pattern expects that.
4. Update README status/usage lightly if appropriate.
5. Print `TASK_COMPLETE` only after artifacts are written.
