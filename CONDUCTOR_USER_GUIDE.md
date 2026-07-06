# Conductor User Guide

**Project:** `/home/alhanaei/projects/Conductor`  
**Status:** Phase 6 implemented and Hermes-verified  
**Purpose:** Local-first control plane for coordinating tmux-backed coding-agent lanes through durable plans, task artifacts, approvals, verification gates, and operator-safe summaries.

---

## 1. What Conductor Is

Conductor is a dispatcher-style agent control plane. It manages the *workflow around* coding agents rather than calling model APIs directly.

It provides:

- local file-backed state under `.conductor/`
- goal intake into `spec.md`, `plan.md`, and task DAGs
- explicit plan approval before dispatch
- tmux lane readiness checks before submission
- safe artifact-reference dispatch instead of pasting large prompts
- worktree/branch planning that degrades safely outside git
- worker result handling
- independent verification gates
- bounded fix loops
- explicit merge approval
- close/final-summary semantics
- Hermes/Telegram-style operator summaries and notifications

Core principle:

```text
worker says done ≠ task complete
```

A task only moves through completion by evidence:

```text
worker result/result.md
→ conductor verify
→ ready_for_merge
→ approve merge
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

Request approval payload:

```bash
python -m conductor operator approval --track "$TRACK" --kind plan --json
```

Approve the plan:

```bash
python -m conductor approve plan --track "$TRACK" --json
```

Dispatch the first ready task:

```bash
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

Good for testing the current local repo without installing:

```bash
cd /tmp/conductor-user-test
export PYTHONPATH=/home/alhanaei/projects/Conductor/src
python -m conductor --help
```

### Option B — editable install

From the project root:

```bash
cd /home/alhanaei/projects/Conductor
python -m pip install -e .
conductor --help
```

If using the source checkout during development, prefer `python -m conductor` so you know exactly which code path is running.

---

## 4. Core CLI Commands

Top-level command groups:

```text
init        Create .conductor/ state layout
track       Track operations
go          Intake a goal into a track and generate a plan
plan        Plan operations
approve     Approval gates: plan, merge
lane        tmux lane operations
dispatch    Dispatch ready tasks of an approved track
task        Task operations
followup    Write a follow-up artifact/message for a task
nudge       Send/record a short nudge for a task
verify      Run verification gates on dispatched tasks
fix         Open a bounded fix-loop attempt for a task
close       Close a track; requires merge approval
reconcile   Reconstruct/report track state from artifacts
operator    Chat/operator summaries, notifications, hooks
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

Creates `.conductor/` in the current directory.

### Step 2 — create a planned track

```bash
TRACK=$(python -m conductor go --plan-only "Build a small dashboard" --json | python -c 'import json,sys; print(json.load(sys.stdin)["track_id"])')
```

This writes:

```text
.conductor/tracks/<track_id>/metadata.json
.conductor/tracks/<track_id>/spec.md
.conductor/tracks/<track_id>/plan.md
```

### Step 3 — review the plan

```bash
python -m conductor plan review --track "$TRACK" --json
python -m conductor operator summary --track "$TRACK" --format telegram
```

### Step 4 — approve the plan

```bash
python -m conductor operator approval --track "$TRACK" --kind plan --json
python -m conductor approve plan --track "$TRACK" --json
```

Plan approval is required before dispatch.

### Step 5 — dispatch ready task(s)

```bash
python -m conductor dispatch --track "$TRACK" --json
```

Dispatch writes per-task artifacts under:

```text
.conductor/tracks/<track_id>/tasks/<task_id>/task.md
.conductor/tracks/<track_id>/tasks/<task_id>/route.json
.conductor/tracks/<track_id>/tasks/<task_id>/status.json
```

If the tmux lane is absent, busy, or otherwise not ready, dispatch degrades safely to `pending_lane` / `blocked_lane` instead of pasting into the wrong prompt.

### Step 6 — inspect task status

```bash
TASK=<task_id>
python -m conductor task status --track "$TRACK" --task "$TASK" --json
```

### Step 7 — worker writes result

A worker result is normally written at:

```text
.conductor/tracks/<track_id>/tasks/<task_id>/result.md
```

For smoke testing, you can simulate this:

```bash
printf 'TASK_COMPLETE\nworker says done\n' > ".conductor/tracks/$TRACK/tasks/$TASK/result.md"
```

Important: this does **not** complete the task. It is only a worker claim.

### Step 8 — run Conductor verification

```bash
python -m conductor verify --track "$TRACK" --json
```

Verification writes:

```text
.conductor/tracks/<track_id>/tasks/<task_id>/verification.json
.conductor/tracks/<track_id>/tasks/<task_id>/verification.md
```

If verification passes, the task becomes `ready_for_merge`. If it fails, the task becomes `needs_fix`.

### Step 9 — approve merge

```bash
python -m conductor operator approval --track "$TRACK" --kind merge --json
python -m conductor approve merge --track "$TRACK" --json
```

Merge approval is independent from plan approval and requires verified tasks.

### Step 10 — close the track

```bash
python -m conductor close --track "$TRACK" --json
```

Close writes:

```text
.conductor/tracks/<track_id>/summary.json
.conductor/tracks/<track_id>/summary.md
```

### Step 11 — reconcile final state

```bash
python -m conductor reconcile --track "$TRACK" --json
```

Reconcile writes:

```text
.conductor/tracks/<track_id>/reconciliation.json
.conductor/tracks/<track_id>/reconciliation.md
```

It reconstructs track truth from artifacts and flags missing proof, missing routes/status files, worker claims without verification, missing merge approval, etc.

---

## 6. Operator / Hermes / Telegram Surfaces

Phase 6 adds a pure projection layer. It does not call Telegram or modify Hermes config. It renders safe payloads that Hermes or a Telegram bridge can send.

### Summary

```bash
python -m conductor operator summary --track "$TRACK" --format telegram
python -m conductor operator summary --track "$TRACK" --json
python -m conductor operator summary --json
```

Use this for human-readable chat updates.

It includes:

- goal
- track ID
- track state
- plan status
- current signal
- dispatched/verified/needs-fix counts
- next action
- exact command to run next
- bounded artifact refs

### Notify

```bash
python -m conductor operator notify --track "$TRACK" --json
```

Returns a deterministic terminal-state/operator-state payload:

```json
{
  "signal": "needs_verification",
  "severity": "info",
  "track_id": "track_xxx",
  "summary": "...",
  "next_action": "run verification",
  "next_command": "python -m conductor verify --track track_xxx --json",
  "artifact_refs": ["..."],
  "telegram_text": "...",
  "dedupe_key": "..."
}
```

Signals include states such as:

```text
needs_approval
needs_dispatch
needs_verification
needs_fix
blocked
ready_for_merge
ready_to_close
closed
```

### Heartbeat

```bash
python -m conductor operator heartbeat --track "$TRACK" --json
python -m conductor operator heartbeat --track "$TRACK" --now 2026-06-29T12:00:00Z --json
python -m conductor operator heartbeat --track "$TRACK" --force --json
```

Behavior:

- deterministic 5-minute cadence
- first heartbeat is due
- terminal tracks do not heartbeat unless forced
- body says `no change` when the track fingerprint is unchanged
- persists a small dedupe memo at:

```text
.conductor/tracks/<track_id>/operator/heartbeat.json
```

### Approval payloads

Plan approval:

```bash
python -m conductor operator approval --track "$TRACK" --kind plan --json
```

Merge approval:

```bash
python -m conductor operator approval --track "$TRACK" --kind merge --json
```

These return:

- whether approval is needed
- whether it is ready
- exact command to run
- risk/context summary
- artifact references
- verification evidence for merge approval

### Artifact links

```bash
python -m conductor operator artifacts --track "$TRACK" --json
```

Returns only known existing Conductor artifacts, such as:

```text
metadata.json
spec.md
plan.md
summary.md
reconciliation.md
tasks/<task_id>/task.md
tasks/<task_id>/route.json
tasks/<task_id>/status.json
tasks/<task_id>/result.md
tasks/<task_id>/verification.json
tasks/<task_id>/verification.md
```

It does not expose raw logs or arbitrary files.

### Hermes verification hook

```bash
python -m conductor operator verify-hook --track "$TRACK" --json
```

Returns commands Hermes should run next, with `purpose`, `expected`, and `auto_run` metadata.

Examples:

- before verification: `python -m conductor verify --track <id> --json`
- always useful: `python -m conductor reconcile --track <id> --json`
- after close: `reconcile` and `operator summary`
- merge approval suggestions are marked as operator actions, not blindly auto-run

---

## 7. tmux Lane Operations

Conductor can inspect and address tmux-backed agent lanes.

```bash
python -m conductor lane ensure  --target Conductor:claude --json
python -m conductor lane status  --target Conductor:claude --json
python -m conductor lane capture --target Conductor:claude --json
python -m conductor lane submit  --target Conductor:claude --task-file /path/to/task.md --json
```

Readiness states include:

```text
absent
shell
provider_ready
busy
blocked_prompt
unknown
```

Submission is gated: Conductor refuses to submit unless the lane is classified as provider-ready.

Provider profiles currently include:

```text
claude
codex
gemini
grok
```

---

## 8. Follow-up, Nudge, and Fix Loops

### Follow-up

```bash
cat > /tmp/followup.md <<'EOF'
Please retry with the verifier evidence attached and update result.md.
EOF

python -m conductor followup --track "$TRACK" --task "$TASK" --body-file /tmp/followup.md --json
```

Follow-up stores the body as an artifact and sends/records only an artifact reference.

### Nudge

```bash
python -m conductor nudge --track "$TRACK" --task "$TASK" --json
```

Nudge sends or records a short prompt depending on lane readiness.

### Fix loop

```bash
python -m conductor fix --track "$TRACK" --task "$TASK" --json
```

Fix attempts are bounded. Default max is 3. The 4th attempt is refused unless forced:

```bash
python -m conductor fix --track "$TRACK" --task "$TASK" --force --json
```

---

## 9. Full Smoke Test Script

Copy-paste this end-to-end test.

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
python -m conductor operator approval --track "$TRACK" --kind plan --json
python -m conductor approve plan --track "$TRACK" --json

python -m conductor dispatch --track "$TRACK" --json > /tmp/conductor-dispatch.json
TASK=$(python -c 'import json; print(json.load(open("/tmp/conductor-dispatch.json"))["dispatched"][0]["task_id"])')
echo "TASK=$TASK"

python -m conductor operator notify --track "$TRACK" --json
python -m conductor operator verify-hook --track "$TRACK" --json
python -m conductor operator heartbeat --track "$TRACK" --now 2026-06-29T12:00:00Z --json
python -m conductor operator artifacts --track "$TRACK" --json

# Simulate worker claim/result.
printf 'TASK_COMPLETE\nworker says done\n' > ".conductor/tracks/$TRACK/tasks/$TASK/result.md"

# These should show merge not ready before verification.
python -m conductor operator approval --track "$TRACK" --kind merge --json

# Verify and close.
python -m conductor verify --track "$TRACK" --json
python -m conductor operator approval --track "$TRACK" --kind merge --json
python -m conductor approve merge --track "$TRACK" --json
python -m conductor close --track "$TRACK" --json
python -m conductor reconcile --track "$TRACK" --json

# Closed-track operator surfaces.
python -m conductor operator notify --track "$TRACK" --json
python -m conductor operator verify-hook --track "$TRACK" --json
python -m conductor operator heartbeat --track "$TRACK" --now 2026-06-29T12:10:00Z --json
python -m conductor operator summary --track "$TRACK" --format telegram
```

Expected highlights:

```text
summary includes signal: needs_approval
notify after dispatch includes signal: needs_verification
heartbeat before close has due=true terminal=false
merge approval before verify has ready=false
verify creates verification.json/verification.md
close creates summary.json/summary.md
reconcile consistent=true
notify after close includes signal=closed severity=success
heartbeat after close has due=false terminal=true
```

---

## 10. Artifact Layout

After running a track, expect this shape:

```text
.conductor/
  tracks/
    <track_id>/
      metadata.json
      spec.md
      plan.md
      summary.json
      summary.md
      reconciliation.json
      reconciliation.md
      operator/
        heartbeat.json
      tasks/
        <task_id>/
          task.md
          route.json
          status.json
          result.md
          verification.json
          verification.md
      .message-bus/
        queue.jsonl
        locks.json
        worker-status.json
        events/
```

Not all files exist at the start. They appear as the lifecycle progresses.

---

## 11. Status and Health

Global status:

```bash
python -m conductor status --json
```

Health check:

```bash
python -m conductor doctor --json
```

Message bus:

```bash
python -m conductor message send --track "$TRACK" --type PROGRESS --body "working" --worker w1 --json
python -m conductor message list --track "$TRACK" --json
```

Locks:

```bash
python -m conductor lock acquire --track "$TRACK" --file src/example.py --worker w1 --json
python -m conductor lock release --track "$TRACK" --file src/example.py --worker w1 --json
```

---

## 12. Current Boundaries and Caveats

### Non-git mode

The current project checkout is not a git repo. Conductor degrades safely and does **not** run `git init` automatically.

This is intentional.

### No direct model/API calls

Conductor manages lanes and artifacts. It does not call LLM APIs directly.

### No real Telegram API yet

Phase 6 renders Telegram-safe/operator-safe payloads. It does not send messages through Telegram itself.

### Verification MVP

Current verification is deterministic/artifact-based by default:

- worker result artifact exists
- result is non-empty
- Conductor writes a separate verifier verdict

Future work can extend this with configured safe verification commands per task.

### Dispatch readiness is conservative

If a lane is absent, busy, blocked, or ambiguous, dispatch does not paste into it. It records pending/blocked state and artifacts instead.

This is safer than corrupting a provider prompt.

---

## 13. Common Troubleshooting

### `lane_runtime ... is not agent_ready`

The target tmux lane is not recognized as ready.

Check:

```bash
python -m conductor lane status --target Conductor:claude --json
python -m conductor lane capture --target Conductor:claude --json
```

Then start/repair the provider lane manually if needed.

### `cannot approve merge: task(s) not verified`

Run:

```bash
python -m conductor verify --track "$TRACK" --json
```

Then re-check:

```bash
python -m conductor operator approval --track "$TRACK" --kind merge --json
```

### `cannot close track: merge approval required first`

Run:

```bash
python -m conductor approve merge --track "$TRACK" --json
python -m conductor close --track "$TRACK" --json
```

### Need to know the next action

Use:

```bash
python -m conductor operator notify --track "$TRACK" --json
python -m conductor operator verify-hook --track "$TRACK" --json
```

### Need a human-readable update

Use:

```bash
python -m conductor operator summary --track "$TRACK" --format telegram
```

---

## 14. Recommended Manual Test Order

1. Run the Quick Start Sandbox.
2. Verify `operator summary` and `operator approval` before approving.
3. Approve plan.
4. Dispatch.
5. Confirm `operator notify` says `needs_verification`.
6. Simulate worker result.
7. Confirm merge approval is not ready before verification.
8. Run `verify`.
9. Confirm merge approval is ready.
10. Approve merge.
11. Close.
12. Reconcile.
13. Confirm closed-track operator surfaces.

---

## 15. Developer Verification

From the project root:

```bash
cd /home/alhanaei/projects/Conductor
python -m compileall -q src/conductor tests
python -m pytest -q
```

Hermes last verified:

```text
compileall_ok
pytest reached 100%, exit code 0
worker-recorded suite: 177 passed
```

---

## 16. Mental Model

Think of Conductor as six layers:

```text
Phase 1: state kernel + message bus
Phase 2: goal intake + plan approval
Phase 3: tmux lane adapter + readiness gate
Phase 4: dispatch/worktree/task artifact loop
Phase 5: verification-gated completion + merge/close approval
Phase 6: operator/Hermes/Telegram-safe projection layer
```

Each layer adds one gate, and each gate writes evidence.

That is the core design.
