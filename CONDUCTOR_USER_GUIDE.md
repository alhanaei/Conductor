# Conductor User Guide

**Project:** `/home/alhanaei/projects/Conductor`
**Status:** Phases 1–6 implemented and verified, plus the hardening pass (real verification commands, closed fix loop, worker protocol, lane pool, provider launch). 267 tests passing.
**Purpose:** Local-first control plane for coordinating tmux-backed coding-agent lanes through durable plans, task artifacts, approvals, verification gates, an autonomous loop, and operator-safe summaries.

---

## 1. What Conductor Is

Conductor is a dispatcher-style agent control plane. It manages the *workflow around* coding agents rather than calling model APIs directly.

It provides:

- local file-backed state under `.conductor/` (atomic writes, append-only logs, per-track mutex)
- goal intake into `spec.md`, `plan.md`, and task DAGs
- explicit plan approval before dispatch
- tmux lane readiness checks before submission
- provider launch (`claude`, `codex`, `gemini`, `grok`) with a tiered model policy
- a lane pool so parallel tasks never collide on one pane
- safe artifact-reference dispatch instead of pasting large prompts
- worktree/branch planning that degrades safely outside git
- a worker self-reporting protocol (`worker beat` / `worker complete`)
- independent verification gates that run **real, allowlisted commands**
- a long-horizon loop (`conductor loop`) with a bounded auto-fix cycle
- explicit merge approval (never auto-granted by default)
- close/final-summary semantics
- Hermes/Telegram-style operator summaries and notifications

Core principle:

```text
worker says done ≠ task complete
```

A task only moves through completion by evidence:

```text
worker result.md (claim)
→ conductor verify   (artifact checks + configured commands must pass)
→ ready_for_merge
→ approve merge      (operator gate)
→ close
```

---

## 2. Quick Start Sandbox

Use this first to test safely without touching any existing project state.

```bash
rm -rf /tmp/conductor-user-test
mkdir -p /tmp/conductor-user-test
cd /tmp/conductor-user-test

export PYTHONPATH=/home/alhanaei/projects/Conductor/src

python -m conductor init
TRACK=$(python -m conductor go --plan-only "Build a small dashboard" --json | python -c 'import json,sys; print(json.load(sys.stdin)["track_id"])')

echo "TRACK=$TRACK"
```

Inspect operator summary:

```bash
python -m conductor operator summary --track "$TRACK" --format telegram
```

Approve the plan and dispatch:

```bash
python -m conductor approve plan --track "$TRACK" --json
python -m conductor dispatch --track "$TRACK" --json
```

Check what Conductor wants next:

```bash
python -m conductor operator notify --track "$TRACK" --json
python -m conductor operator verify-hook --track "$TRACK" --json
```

---

## 3. Install / Invocation Modes

### Option A — run from source with `PYTHONPATH`

```bash
export PYTHONPATH=/home/alhanaei/projects/Conductor/src
python -m conductor --help
```

### Option B — editable install

```bash
cd /home/alhanaei/projects/Conductor
python -m pip install -e .
conductor --help
```

During development prefer `python -m conductor` so you know exactly which code path is running.

---

## 4. Core CLI Commands

```text
init        Create .conductor/ state layout
track       Track operations
go          Intake a goal into a track and generate a plan
plan        Plan operations
approve     Approval gates: plan, merge
lane        tmux lane operations (ensure/launch/status/capture/submit)
dispatch    Dispatch ready tasks; retry pending_lane tasks
advance     Advance verified tasks; release dependency successors
loop        One long-horizon loop tick: verify → auto-fix → advance → dispatch
task        Task operations (status, set-verify)
followup    Write a follow-up artifact/message for a task
nudge       Send/record a short nudge for a task
verify      Run verification gates on dispatched tasks
fix         Open a bounded fix-loop attempt for a task
close       Close a track; requires merge approval
reconcile   Reconstruct/report track state from artifacts
operator    Chat/operator summaries, notifications, hooks
worker      Worker self-reporting: beat, complete
status      Operator status across all tracks
message     Message bus operations
lock        File lock operations
doctor      State-root health check
```

Every command supports JSON output using `--json` before or after the subcommand:

```bash
python -m conductor --json status
python -m conductor status --json
```

---

## 5. Lifecycle: From Goal to Close

### Step 1 — initialize state

```bash
python -m conductor init
```

### Step 2 — create a planned track

```bash
TRACK=$(python -m conductor go --plan-only "Build a small dashboard" --json | python -c 'import json,sys; print(json.load(sys.stdin)["track_id"])')
```

Optional: `--task-workflow-mode stage|full` (default `stage`). `full` embeds the
complete per-task workflow contract into each task description.

This writes:

```text
.conductor/tracks/<track_id>/metadata.json
.conductor/tracks/<track_id>/spec.md
.conductor/tracks/<track_id>/plan.md
.conductor/tracks/<track_id>/definition_of_done.md
.conductor/tracks/<track_id>/quality_gates.json
```

### Step 3 — review and approve the plan

```bash
python -m conductor plan review --track "$TRACK" --json
python -m conductor approve plan --track "$TRACK" --json
```

Plan approval is required before dispatch.

### Step 4 — configure verification commands and file scope (recommended)

By default verification only checks that artifacts exist. Give it teeth:

```bash
python -m conductor task set-verify --track "$TRACK" --task "$TASK" \
  --command "python -m pytest -q" --json

python -m conductor task set-scope --track "$TRACK" --task "$TASK" \
  --path 'src/**' --json
```

**Commands** (`set-verify`):

- `--command` is repeatable; `--clear` resets first.
- Commands are **allowlisted by first token** (python, pytest, npm, node, go,
  cargo, make, ruff, mypy, …). Extend via `conductor.json`:
  `{"verification_allowed_commands": ["mytool"]}`.
- No shell is ever used: commands run as argument arrays; unquoted shell
  metacharacters (`;`, `|`, `&&`, `>`) are rejected loudly. Quoted ones are fine
  (`python -c 'import sys; sys.exit(0)'`).
- Each command becomes a check with exit code + output evidence, persisted to
  `tasks/<task_id>/verification-output.txt`.

**File scope** (`set-scope`) — powers two deterministic integrity gates that run
on every verify when the workspace is a git repo (dispatch records the HEAD
commit as the diff baseline):

- **Diff scope:** any file changed outside the declared globs fails
  verification. With no scope declared, the changed-file list is still reported
  as evidence (informational). `.conductor/` and `.hermes/` protocol writes are
  always exempt.
- **Test integrity:** a non-`test`-method task that modifies test files
  (`tests/**`, `test_*`, `*_test.*`, `*.test.*`, `*.spec.*`; override via
  `conductor.json {"test_file_patterns": [...]}`) fails verification unless its
  scope explicitly grants those paths. This closes the "worker weakened the
  tests so pytest passes" hole.
- Non-git workspaces skip both gates with an explicit "skipped" note — a gate
  that cannot measure says so rather than failing work it has no evidence
  against.

### Step 5 — dispatch ready task(s)

```bash
python -m conductor dispatch --track "$TRACK" --json
```

Dispatch writes per-task artifacts:

```text
.conductor/tracks/<track_id>/tasks/<task_id>/task.md
.conductor/tracks/<track_id>/tasks/<task_id>/route.json
.conductor/tracks/<track_id>/tasks/<task_id>/status.json
```

Behavior worth knowing:

- **Lane pool.** Parallel same-provider tasks get distinct panes: `claude`,
  `claude-2`, … up to `lane_pool_size` (default 3, config in `conductor.json`).
  Occupancy is global across tracks. If every pool slot is busy, the task is
  **queued** (`lane_target: null`, blocker `lane pool exhausted`) rather than
  double-submitted into an occupied pane.
- **Pending retry.** Tasks stuck in `pending_lane` are re-attempted on every
  dispatch (or loop) tick — when the lane comes up `provider_ready`, they are
  submitted automatically.
- If a lane is absent/busy/blocked, dispatch degrades to `pending_lane` /
  `blocked_lane`. It never pastes into the wrong prompt.

### Step 6 — the worker does the work and self-reports

The dispatched `task.md` instructs the worker to run these itself:

```bash
# heartbeat every few minutes (keeps stale-risk accurate)
python -m conductor worker beat --track "$TRACK" --task "$TASK" --worker w1 --note "halfway"

# after writing result.md, record a completion CLAIM
python -m conductor worker complete --track "$TRACK" --task "$TASK" --worker w1
```

`worker complete` requires the result artifact at
`tasks/<task_id>/result.md`, sets the task to `ready_for_review`, and posts a
structured `TASK_COMPLETE` message. **It never completes the task** —
verification still gates.

**Review tasks additionally record a verdict** (their `task.md` instructs this):

```bash
python -m conductor worker verdict --track "$TRACK" --task "$TASK" --worker w1 \
  --verdict approve            # or: --verdict reject --blocker "missing error handling"
```

This writes `tasks/<task_id>/verdict.json`. A review task **fails verification
without a valid verdict**, and a `reject` (or missing) verdict **blocks
`approve merge`** with the blockers as evidence — the reviewer's judgment is
structural, not advisory. `--force` on merge remains the operator override.

For smoke testing you can simulate the worker:

```bash
printf 'TASK_COMPLETE\nworker says done\n' > ".conductor/tracks/$TRACK/tasks/$TASK/result.md"
```

### Step 7 — run Conductor verification

```bash
python -m conductor verify --track "$TRACK" --json
```

Verification writes a conductor-authored verdict, independent of the claim:

```text
tasks/<task_id>/verification.json
tasks/<task_id>/verification.md
tasks/<task_id>/verification-output.txt   # command evidence, if commands configured
```

Pass → `ready_for_merge`. Fail (missing artifact, failing configured command,
non-allowlisted command) → `needs_fix`.

### Step 8 — advance the DAG

```bash
python -m conductor advance --track "$TRACK" --json
```

Verified (`ready_for_merge`) tasks become `complete` and their dependents become
`ready` for the next dispatch. (The loop does this for you — see §6.)

### Step 9 — approve merge

```bash
python -m conductor operator approval --track "$TRACK" --kind merge --json
python -m conductor approve merge --track "$TRACK" --json
```

Merge approval is independent from plan approval, requires all dispatched tasks
verified **and** all plan tasks finalized, and is idempotent.

### Step 10 — close and reconcile

```bash
python -m conductor close --track "$TRACK" --json        # writes summary.json/.md
python -m conductor reconcile --track "$TRACK" --json    # writes reconciliation.json/.md
```

Reconcile reconstructs track truth from artifacts and flags gaps: worker claims
without verification, missing routes/status, missing merge approval, missing
definition-of-done/quality gates, etc.

---

## 6. The Loop: Long-Horizon Autonomous Operation

`conductor loop` is one idempotent supervision tick:

```text
verify available results → auto-fix failures → advance DAG → dispatch/retry lanes
```

```bash
# single tick
python -m conductor loop --track "$TRACK" --json

# keep supervising: poll every 30s, react to provider approval prompts fast
python -m conductor loop --track "$TRACK" --watch --max-cycles 100 \
  --poll-interval 30 --stop-on-blocked-prompt --json
```

Key flags:

| Flag | Behavior |
|---|---|
| `--watch` | Keep polling instead of exiting on the first no-progress cycle. |
| `--max-cycles N` | Upper bound on cycles this invocation. |
| `--poll-interval S` | Sleep between watch cycles (default 30s). |
| `--stop-on-blocked-prompt` | Exit quickly when a worker lane is waiting on a provider approval prompt, scanning every `--prompt-poll-interval` (default 3s) during sleeps. |
| `--no-auto-fix` | Disable automatic fix routing for failed verifications. |
| `--auto-finalize` | Let the loop approve merge + close when all tasks complete (see below). |
| `--force` | Override lane readiness gate on submit and the requires-operator finalize gate. |

**Verification in the loop is non-blocking:** only tasks with a result artifact
are verified (`verify_ready_results`); still-working tasks are skipped, not
failed.

**The auto-fix cycle (default on):** when a verification fails, the loop

1. archives the failing result to `result-attempt-N.md` (so the same stale
   result is never re-verified — attempts aren't burned; only a *fresh* worker
   result re-enters verification),
2. opens a bounded fix (`fixes/fix-N.md` + FOLLOWUP message; max 3 attempts),
3. best-effort delivers a short fix reference to the lane (readiness-gated),
4. escalates when attempts are exhausted: blocker set on the task +
   `fix_attempts_exhausted` event — operator intervention required.

**Finalization is an operator gate by default.** When all tasks complete, the
loop stops with `stop_reason: awaiting_operator` and prints the exact
`approve merge` / `close` commands. Opting in with `--auto-finalize` still
refuses if any task has `autonomy_policy: requires_operator` (the default
plan's review task does) unless `--force` is also given.

---

## 7. tmux Lane Operations

### Ensure + launch

```bash
# create the tmux window only (bare shell)
python -m conductor lane ensure --target Conductor:claude --json

# also start the provider CLI — tiered model policy picks the model
python -m conductor lane ensure --target Conductor:claude --launch --method build --json

# explicit model wins over the policy
python -m conductor lane ensure --target Conductor:claude --launch --model claude-fable-5 --json
python -m conductor lane ensure --target Conductor:codex  --launch --model gpt-5.1-codex --json
```

Launch safety: the launch command is typed **only into a pane classified
`shell`**. `provider_ready` is a no-op (never restarts a running agent);
`busy`/`blocked_prompt`/`absent`/`unknown` refuse. After launching, Conductor
waits up to `--launch-wait` seconds (default 15) for `provider_ready` and
records the model on the lane record.

### Tiered model policy (claude lanes)

| `--method` | Model launched |
|---|---|
| `plan`, `build`, `review` | `claude-fable-5` |
| `spec`, `test` | `claude-sonnet-4-6` |
| `ship` / no method | `claude-opus-4-8` |

Codex/gemini/grok launch **bare** by default (their CLIs use their own
configured default model) unless you set a per-provider map in
`conductor.json`:

```json
"lane_models": {
  "claude": {"build": "claude-fable-5", "test": "claude-sonnet-4-6"},
  "codex":  {"default": "gpt-5.1-codex"},
  "grok":   {"default": "grok-4"}
}
```

The policy is provider-scoped — claude tiers can never leak into a codex/grok
launch command.

### Status / capture / submit

```bash
python -m conductor lane status  --target Conductor:claude --json
python -m conductor lane capture --target Conductor:claude --json
python -m conductor lane submit  --target Conductor:claude --task-file /path/to/task.md --json
```

Readiness states: `absent`, `shell`, `provider_ready`, `busy`,
`blocked_prompt`, `unknown`. Submission is refused unless `provider_ready`.
Pool windows (`claude-2`, `codex-3`) classify with the base provider's profile.

---

## 8. Follow-up, Nudge, Fix

### Follow-up (artifact-reference, never pastes the body)

```bash
python -m conductor followup --track "$TRACK" --task "$TASK" --body-file /tmp/followup.md --json
```

### Nudge (respects lane readiness)

```bash
python -m conductor nudge --track "$TRACK" --task "$TASK" --json
```

### Fix loop (bounded)

```bash
python -m conductor fix --track "$TRACK" --task "$TASK" --json      # attempts 1..3
python -m conductor fix --track "$TRACK" --task "$TASK" --force --json  # override the cap
```

The loop calls `fix` automatically for failed verifications (§6); the manual
command exists for operator-driven fixes with a custom `--body-file`.

---

## 9. Full Smoke Test Script

```bash
set -euo pipefail

rm -rf /tmp/conductor-user-full-test
mkdir -p /tmp/conductor-user-full-test
cd /tmp/conductor-user-full-test

export PYTHONPATH=/home/alhanaei/projects/Conductor/src

python -m conductor init

TRACK=$(python -m conductor go --plan-only "Build a small dashboard" --json | python -c 'import json,sys; print(json.load(sys.stdin)["track_id"])')
echo "TRACK=$TRACK"

python -m conductor operator summary --track "$TRACK" --format telegram
python -m conductor approve plan --track "$TRACK" --json

python -m conductor dispatch --track "$TRACK" --json > /tmp/conductor-dispatch.json
TASK=$(python -c 'import json; print(json.load(open("/tmp/conductor-dispatch.json"))["dispatched"][0]["task_id"])')
echo "TASK=$TASK"

# Real verification command (passes trivially here; use your test suite in practice)
python -m conductor task set-verify --track "$TRACK" --task "$TASK" \
  --command "python -c 'import sys; sys.exit(0)'" --json

# Simulate the worker: result + structured completion claim.
printf 'TASK_COMPLETE\nworker says done\n' > ".conductor/tracks/$TRACK/tasks/$TASK/result.md"
python -m conductor worker beat --track "$TRACK" --task "$TASK" --worker w1 --note "working" --json
python -m conductor worker complete --track "$TRACK" --task "$TASK" --worker w1 --json

# Gates: close/merge refuse before verification.
python -m conductor close --track "$TRACK" --json || echo "close refused (expected)"
python -m conductor approve merge --track "$TRACK" --json || echo "merge refused (expected)"

# One loop tick verifies + advances; without --auto-finalize it awaits the operator.
python -m conductor loop --track "$TRACK" --max-cycles 10 --json | tail -40

# Finish remaining tasks the same way, or finalize explicitly once complete:
python -m conductor verify --track "$TRACK" --json
python -m conductor task status --track "$TRACK" --task "$TASK" --json
python -m conductor operator notify --track "$TRACK" --json
```

Expected highlights:

```text
summary before approval: signal needs_approval
dispatch: first task pending_lane (no live lane in the sandbox) or submitted
worker complete: task_state ready_for_review, note "verification still gates"
close/merge before verify: refused, exit 1
verify with passing command: task_state ready_for_merge, verification-output.txt written
loop with all tasks complete (no --auto-finalize): stop_reason awaiting_operator
```

---

## 10. Artifact Layout

```text
.conductor/
  conductor.json                  # config: lane_pool_size, lane_models,
                                  # verification_allowed_commands, ...
  events.jsonl                    # global append-only event log
  lanes/
    <escaped_target>.json         # lane record (state, model, heartbeats)
    <escaped_target>.transcript.txt
  tracks/
    <track_id>/
      metadata.json               # track + plan + tasks + approvals (mutex-guarded)
      .metadata_mutex
      spec.md
      plan.md
      definition_of_done.md
      quality_gates.json
      summary.json / summary.md               # written by close
      reconciliation.json / reconciliation.md # written by reconcile
      operator/
        heartbeat.json            # operator-heartbeat dedupe memo
      tasks/
        <task_id>/
          task.md                 # dispatched work spec (incl. worker protocol, file scope)
          route.json              # route decision record
          status.json             # dispatch record (state, lane, scope, baseline, verification, fixes)
          result.md               # worker claim
          result-attempt-N.md     # archived failing results (auto-fix)
          verdict.json            # review task's approve/reject (gates the merge)
          verification.json / verification.md
          verification-output.txt # command evidence
          fixes/fix-N.md
          followups/followup-N.md
      .message-bus/
        queue.jsonl
        locks.json
        worker-status.json
        events/
```

Not all files exist at the start; they appear as the lifecycle progresses.

---

## 11. Status and Health

```bash
python -m conductor status --json     # tracks, tasks, lanes, messages, locks
python -m conductor doctor --json     # state-root health
```

Message bus and file locks (used by workers to coordinate):

```bash
python -m conductor message send --track "$TRACK" --type PROGRESS --body "working" --worker w1 --json
python -m conductor message list --track "$TRACK" --json
python -m conductor lock acquire --track "$TRACK" --file src/example.py --worker w1 --json
python -m conductor lock release --track "$TRACK" --file src/example.py --worker w1 --json
```

---

## 12. Operator / Hermes / Telegram Surfaces

A pure projection layer — no Telegram API, no daemons; it renders payloads a
bridge can send.

```bash
python -m conductor operator summary    --track "$TRACK" --format telegram
python -m conductor operator notify     --track "$TRACK" --json
python -m conductor operator heartbeat  --track "$TRACK" [--now ISO] [--force] --json
python -m conductor operator approval   --track "$TRACK" --kind plan|merge --json
python -m conductor operator artifacts  --track "$TRACK" --json
python -m conductor operator verify-hook --track "$TRACK" --json
```

- `notify` returns `{signal, severity, next_action, next_command, artifact_refs,
  telegram_text, dedupe_key}`. Signals: `needs_approval`, `needs_dispatch`,
  `needs_verification`, `needs_fix`, `blocked`, `ready_for_merge`,
  `ready_to_close`, `closed`.
- `heartbeat` is deterministic (5-minute cadence, terminal tracks suppressed,
  body `no change` when the state fingerprint is unchanged).
- `verify-hook` tells Hermes exactly which commands to run next, with
  `expected` conditions and `auto_run` flags (merge/close are suggestions,
  never auto-run).

---

## 13. Current Boundaries and Caveats

### Git

The project **is a git repository** (initialized 2026-07-06) with ruff linting
and a GitHub Actions test matrix. Worktree allocation inside a git repo plans
`conductor/<track>/<task>-<slug>` branches (`git_planned`) and only creates
worktrees with `dispatch --create-worktree`. Tracks operated in non-git
directories still degrade safely (`not_git_repo`); `git init` is never run by
Conductor itself.

### No direct model/API calls

Conductor manages lanes and artifacts. It does not call LLM APIs directly —
models are chosen at lane launch (`--launch`) and run inside the provider CLIs.

### No real Telegram API yet

Operator surfaces render Telegram-safe payloads; delivery is Hermes-pull.

### Verification depth

Verification = artifact checks (result present, definition-of-done present)
**plus** whatever commands you configure per task via `task set-verify`. A task
with no configured commands passes on artifacts alone — configure real commands
for anything that matters.

### Codex/gemini/grok model names

`--model` flag mechanics are wired for all providers, but verify exact model
ids against your installed CLIs — their lineups change frequently. Unconfigured,
they launch bare and use their own defaults.

### Dispatch readiness is conservative

Absent/busy/blocked/ambiguous lanes are never pasted into. Work queues as
`pending_lane` and is retried automatically on later ticks.

### Fable 5 lanes think longer

Single Fable turns can run 10+ minutes, so lanes sit `busy` longer. Worker
`beat` calls keep the stale-risk classifier honest during long thinking.

---

## 14. Common Troubleshooting

### Lane won't accept work

```bash
python -m conductor lane status  --target Conductor:claude --json
python -m conductor lane capture --target Conductor:claude --json
# if state is "shell", launch the provider:
python -m conductor lane ensure --target Conductor:claude --launch --method build --json
```

### `refusing to launch into lane ...: state is 'busy'`

Something is already running in the pane. Attach to tmux and check; launch only
targets bare shells by design.

### `cannot approve merge: task(s) not verified`

```bash
python -m conductor verify --track "$TRACK" --json
```

### `cannot approve final merge: plan still has uncompleted task(s)`

Earlier DAG tasks are unfinished. Run the loop (or `advance` + `dispatch`) until
all plan tasks complete:

```bash
python -m conductor loop --track "$TRACK" --max-cycles 10 --json
```

### `max fix attempts (3) reached`

The auto-fix loop escalated. Inspect the evidence, then either fix manually and
re-verify, or force one more attempt:

```bash
cat ".conductor/tracks/$TRACK/tasks/$TASK/verification.md"
python -m conductor fix --track "$TRACK" --task "$TASK" --force --json
```

### `rejected: ... is not on the verification allowlist`

Add the tool to `conductor.json`:

```json
"verification_allowed_commands": ["mytool"]
```

### `verification failed: diff_scope` / `test_integrity`

The worker changed files outside its declared scope, or a non-test task
modified test files. Inspect the evidence, then either fix the work or widen
the scope deliberately:

```bash
cat ".conductor/tracks/$TRACK/tasks/$TASK/verification.md"
python -m conductor task set-scope --track "$TRACK" --task "$TASK" --path 'tests/**' --json
```

### `cannot approve merge: review verdict gate failed`

The reviewer rejected (blockers are listed in the error) or never recorded a
verdict. Resolve the blockers and have the reviewer re-verdict, or override
deliberately:

```bash
python -m conductor worker verdict --track "$TRACK" --task "$REVIEW_TASK" --worker w1 --verdict approve --json
# or, operator override:
python -m conductor approve merge --track "$TRACK" --force --json
```

### `loop ... stop_reason: awaiting_operator`

All tasks are complete; the loop is waiting for you (by design):

```bash
python -m conductor approve merge --track "$TRACK" --json
python -m conductor close --track "$TRACK" --json
```

### Need to know the next action

```bash
python -m conductor operator notify --track "$TRACK" --json
python -m conductor operator verify-hook --track "$TRACK" --json
```

---

## 15. Recommended Manual Test Order

1. Run the Quick Start Sandbox.
2. Approve plan; dispatch; confirm `pending_lane` (sandbox has no live lane).
3. Set a real verification command with `task set-verify`.
4. Simulate the worker: write `result.md`, run `worker complete` — confirm
   `ready_for_review`, not complete.
5. Confirm `close`/`approve merge` refuse before verification.
6. Run one `loop` tick — confirm it verifies, advances, and dispatches the next
   task.
7. Break the verification command (exit 1) and confirm the auto-fix cycle:
   result archived, `fixes/fix-1.md` created, attempts bounded at 3.
8. Complete all tasks; confirm the loop stops `awaiting_operator`.
9. Approve merge; close; reconcile — confirm `consistent: true`.
10. Check closed-track operator surfaces (`notify` → `closed`, heartbeat
    suppressed).

---

## 16. Developer Verification

From the project root:

```bash
cd /home/alhanaei/projects/Conductor
python -m ruff check src tests
python -m pytest -q
```

Current baseline: **267 tests passing**, lint clean. CI (GitHub Actions) runs
lint + tests on Python 3.9/3.11/3.12 when a remote is added. Use
`git log --oneline` for the change history since the verified Phase 1–6
baseline.

---

## 17. Mental Model

Think of Conductor as seven layers, each adding one gate that writes evidence:

```text
Phase 1: state kernel + message bus + locks
Phase 2: goal intake + plan approval
Phase 3: tmux lane adapter + readiness gate (+ provider launch, model tiers)
Phase 4: dispatch/worktree/task artifacts (+ lane pool, pending retry)
Phase 5: verification-gated completion (+ real commands, bounded auto-fix)
Phase 6: operator/Hermes/Telegram-safe projection layer
Loop:    one supervisor tick composing all of the above, safely re-runnable
```

Trust boundaries, in one line each:

- Plans don't dispatch until an operator approves them.
- Lanes don't receive text unless the classifier proves they're ready for it.
- Worker claims never advance state; conductor-run verification does.
- Workers can't step outside their declared file scope or quietly rewrite the
  tests that judge them (diff-scope + test-integrity gates).
- A reviewer's reject is structural: merge approval refuses until it's resolved.
- Merges and closes belong to the operator unless explicitly delegated
  (`--auto-finalize`), and even then `requires_operator` tasks refuse.
