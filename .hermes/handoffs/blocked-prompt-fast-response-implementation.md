# Handoff — Conductor blocked-prompt fast response

Status: implemented and verified in `/home/alhanaei/projects/Conductor`.
Date: 2026-07-01
Owner for next session: no implementation owner needed; monitor live tracks with the new blocked-prompt flags.

## Implementation update — 2026-07-01

Implemented in this session.

Changed files:

```text
/home/alhanaei/projects/Conductor/src/conductor/blocked_prompts.py
/home/alhanaei/projects/Conductor/src/conductor/cli.py
/home/alhanaei/projects/Conductor/src/conductor/operator.py
/home/alhanaei/projects/Conductor/tests/test_cli_phase5.py
/home/alhanaei/projects/Conductor/tests/test_operator.py
```

Implemented behavior:

- Added `active_blocked_prompts(store, track_id)` helper.
- Added `conductor loop --stop-on-blocked-prompt`.
- Added `conductor loop --prompt-poll-interval <seconds>`.
- Added `conductor lane blocked --track <track> --json` diagnostic command.
- Updated loop output to include `blocked: []` or blocked task/lane details.
- Updated operator signal derivation so active blocked provider prompts surface as `signal: blocked_prompt` with error severity.
- Updated operator verify-hook / next-command loop recommendations to include `--stop-on-blocked-prompt`.

Verification passed:

```bash
cd /home/alhanaei/projects/Conductor
python -m pytest tests/test_lanes.py tests/test_cli_phase5.py -q
python -m pytest tests/test_operator.py tests/test_cli_phase6.py -q
python -m pytest -q
```

Observed results:

```text
tests/test_lanes.py tests/test_cli_phase5.py: 50 passed
tests/test_operator.py tests/test_cli_phase6.py: 28 passed
full suite: 195 passed
```

Git note: `/home/alhanaei/projects/Conductor` still did not report as a git repository during verification.

## User request

Ahmed noticed that when a provider chat/lane is blocked on an approval prompt, Conductor takes too long to respond. Current watch loops can burn many cycles reporting only `result_artifact_missing` before Hermes/operator realizes that the real blocker is an approval prompt in tmux.

Goal: make Conductor detect and surface blocked provider prompts quickly.

## Observed evidence from live TERNARY run

Project:

```text
/home/alhanaei/projects/TERNARY
```

Conductor source:

```text
/home/alhanaei/projects/Conductor/src
```

Track:

```text
track_f78bdaa8
```

Watch commands that repeatedly hit max cycles while a lane was actually waiting on an approval prompt:

```bash
cd /home/alhanaei/projects/TERNARY
export PYTHONPATH=/home/alhanaei/projects/Conductor/src
python -m conductor loop --track track_f78bdaa8 --lane-session conductor-test --watch --max-cycles 180 --poll-interval 30 --json
python -m conductor loop --track track_f78bdaa8 --lane-session conductor-test --watch --max-cycles 120 --poll-interval 20 --json
```

Representative loop output while blocked:

```json
{
  "reason": "result_artifact_missing",
  "task_id": "task_32138d5c"
}
```

Actual tmux pane state at the same time was a Codex/Claude approval prompt, e.g.:

```text
Would you like to run the following command?
Reason: Allow writing TERNARY task result/evidence artifacts outside the conductor-test workspace root.
Press enter to confirm or esc to cancel
```

After manual approval, the worker wrote `result.md`, and a short foreground loop immediately advanced/verified the task.

Conclusion: Conductor already has enough classifier machinery to identify `blocked_prompt`, but `loop --watch` is not using it aggressively while waiting for worker result artifacts.

## Current relevant code

### Loop command

File:

```text
/home/alhanaei/projects/Conductor/src/conductor/cli.py
```

Relevant region:

```text
cmd_loop: lines ~405-463
```

Current loop shape:

```text
verify_ready_results
→ advance_verified
→ dispatch
→ if watch: sleep(args.poll_interval)
```

It does not scan working/dispatched tasks for current lane prompt state before sleeping.

### Lane classifier

File:

```text
/home/alhanaei/projects/Conductor/src/conductor/lanes.py
```

Relevant region:

```text
classify: lines ~188-220
LaneAdapter.status/capture/submit: lines ~317-453
```

Existing `LaneState` values include:

```text
blocked_prompt
busy
provider_ready
shell
unknown
absent
```

Important historical pitfall: do not regress classifier fixes. Ahmed previously fixed false `blocked_prompt` caused by scanning stale tmux scrollback. `classify()` intentionally checks blocker/busy patterns against recent visible tail, not full transcript. Preserve this behavior.

### Existing tests

Files:

```text
/home/alhanaei/projects/Conductor/tests/test_cli_phase5.py
/home/alhanaei/projects/Conductor/tests/test_lanes.py
/home/alhanaei/projects/Conductor/tests/test_operator.py
/home/alhanaei/projects/Conductor/tests/test_cli_phase6.py
```

Useful existing tests:

```text
tests/test_cli_phase5.py::test_loop_watch_keeps_polling_when_worker_result_is_not_ready
tests/test_lanes.py classifier tests around blocked_prompt / stale prompt text
tests/test_operator.py verify-hook / loop command tests
```

## Desired behavior

When an active dispatched/working task has no `result.md`, Conductor should check the current lane state. If the lane is `blocked_prompt`, do not silently keep sleeping until `max_cycles`.

Target output should include enough operator data to act immediately:

```json
{
  "ok": true,
  "track_id": "track_x",
  "stop_reason": "blocked_prompt",
  "blocked": [
    {
      "task_id": "task_y",
      "title": "Add tests and verify behavior",
      "lane_target": "conductor-test:codex",
      "provider": "codex",
      "lane_state": "blocked_prompt",
      "result_artifact_ref": "/path/to/result.md",
      "operator_action": "approve the prompt in the tmux pane or move this lane to the project-root session"
    }
  ]
}
```

## Implementation plan

### Phase 1 — Minimal fast stop on blocked prompt

Add a helper used by `cmd_loop` after `dispatch()` and before sleeping.

Suggested helper location options:

1. `src/conductor/cli.py` private helper for fast minimal implementation.
2. Better: `src/conductor/operator.py` or a small new helper module if reuse is needed.

Pseudo-code:

```python
def _active_blocked_prompts(store, track_id):
    adapter = LaneAdapter(store)
    out = []
    for drec in store.list_dispatch_records(track_id):
        if drec.task_state not in {TaskState.WORKING, TaskState.DISPATCHED}:
            continue
        if drec.result_artifact_ref and Path(drec.result_artifact_ref).exists():
            continue
        if not drec.lane_target:
            continue
        lane = adapter.status(drec.lane_target)
        if lane.get("state") == LaneState.BLOCKED_PROMPT.value:
            out.append({
                "task_id": drec.task_id,
                "title": drec.title,
                "lane_target": drec.lane_target,
                "provider": drec.provider,
                "lane_state": lane.get("state"),
                "result_artifact_ref": drec.result_artifact_ref,
                "operator_action": "approve the prompt in the tmux pane",
            })
    return out
```

Integrate into `cmd_loop`:

```python
blocked = []
...
blocked_now = _active_blocked_prompts(store, args.track)
if blocked_now:
    blocked = blocked_now
    stop_reason = "blocked_prompt"
    if args.stop_on_blocked_prompt:
        break
```

For first cut, default should probably stop on blocked prompt in `--watch`, because Hermes background process completion is how Ahmed gets immediate Telegram alerts. If you want backward-compatible default, add a flag first and use it in operator verify-hook.

Recommended CLI flag:

```bash
--stop-on-blocked-prompt
```

Default options:

- Conservative: default false, but operator verify-hook emits it.
- Stronger/faster: default true for `--watch`; allow `--no-stop-on-blocked-prompt` later if needed.

Given Ahmed's request, start with explicit flag to minimize regression risk, then update operator hook to include it.

### Phase 2 — Add prompt poll interval

Current `--poll-interval` controls everything. Add:

```bash
--prompt-poll-interval 3
```

Simpler implementation for next session:

- Do not create a separate event loop yet.
- Instead, when watch is idle and active tasks exist, sleep in small chunks up to `poll_interval`, checking lane states every `prompt_poll_interval`.
- If a blocked prompt appears during the sleep window, break early and return `stop_reason=blocked_prompt`.

Pseudo-code:

```python
def _sleep_with_prompt_scan(store, track_id, poll_interval, prompt_poll_interval):
    deadline = time.monotonic() + poll_interval
    while time.monotonic() < deadline:
        sleep_for = min(prompt_poll_interval, max(0, deadline - time.monotonic()))
        time.sleep(sleep_for)
        blocked = _active_blocked_prompts(store, track_id)
        if blocked:
            return blocked
    return []
```

Then in `cmd_loop`, replace direct `time.sleep(args.poll_interval)` with this helper when `args.watch`.

### Phase 3 — Operator summary/signal

Update operator surfaces so an active blocked prompt shows as a first-class signal rather than generic `needs_verification`.

Target user-facing signal:

```text
signal: blocked_prompt
next: approve provider prompt in tmux lane conductor-test:codex
```

Likely file:

```text
src/conductor/operator.py
```

Search for signal selection and `needs_verification` logic. Ensure it looks at active dispatched records and fresh lane status, or at a persisted `lane_state=blocked_prompt` updated by the loop.

### Phase 4 — Optional helper command

Add a small diagnostic command:

```bash
python -m conductor lane blocked --track <track> --json
```

Output active blocked lanes/tasks only. This is useful for Hermes Telegram sessions because Ahmed prefers one small diagnostic command at a time.

Implementation can reuse `_active_blocked_prompts`.

## Test plan

Use TDD. Add tests before implementation.

### CLI loop test

File:

```text
tests/test_cli_phase5.py
```

Add test shape:

```python
def test_loop_watch_stops_on_blocked_prompt_for_working_task_without_result(...):
    # create approved + dispatched track/task using existing helpers
    # mark dispatch/status as working/submitted with lane_target test:codex
    # monkeypatch LaneAdapter.status to return {"state": "blocked_prompt", ...}
    # run: conductor loop --track tid --watch --max-cycles 3 --poll-interval 0.01 --stop-on-blocked-prompt --json
    # assert code == 0
    # assert data["stop_reason"] == "blocked_prompt"
    # assert data["blocked"][0]["task_id"] == task_id
```

### Non-regression test

Ensure existing behavior still polls when there is no blocked prompt:

```text
test_loop_watch_keeps_polling_when_worker_result_is_not_ready
```

May need to assert `stop_reason=max_cycles` remains when lane is busy/provider_ready and no result.

### Classifier non-regression

File:

```text
tests/test_lanes.py
```

Existing tests around stale approval/trust text should keep passing. If adding patterns, ensure blocked prompt checks still operate on recent tail only.

### Operator test

File:

```text
tests/test_operator.py
```

Add/adjust test so `OperatorView.summary` or equivalent reports `blocked_prompt` when active task/lane is blocked. If operator is not updated in first PR, skip this until Phase 3.

## Verification commands

From Conductor root:

```bash
cd /home/alhanaei/projects/Conductor
python -m pytest tests/test_lanes.py tests/test_cli_phase5.py -q
python -m pytest tests/test_operator.py tests/test_cli_phase6.py -q
python -m pytest -q
```

Note: this checkout currently did not report as a git repository when checked from `/home/alhanaei/projects/Conductor`:

```text
fatal: not a git repository (or any of the parent directories): .git
```

Do not rely on git status/diff unless a future session confirms repo metadata exists elsewhere.

## Acceptance criteria

1. A watch loop does not wait until max cycles when an active worker lane is at an approval prompt.
2. JSON result includes `stop_reason: blocked_prompt` and a `blocked` list with task/lane/action details.
3. Existing `result_artifact_missing` polling remains valid when the lane is genuinely busy or provider-ready with no result yet.
4. No regression to prior classifier fixes: stale scrollback text must not mark a ready lane as blocked.
5. Targeted tests and full test suite pass.

## Operational guidance after implementation

For Hermes-run tracks, prefer:

```bash
python -m conductor loop \
  --track "$TRACK" \
  --lane-session "$SESSION" \
  --watch \
  --max-cycles 120 \
  --poll-interval 20 \
  --prompt-poll-interval 3 \
  --stop-on-blocked-prompt \
  --json
```

This should make background process alerts arrive as soon as approval is needed.

## Longer-term operational fix

Many TERNARY prompts were caused by using lanes rooted in:

```text
/home/alhanaei/projects/conductor-test
```

while writing target artifacts under:

```text
/home/alhanaei/projects/TERNARY
```

Prefer project-root lanes:

```text
TERNARY:claude
TERNARY:codex
```

with pane cwd:

```text
/home/alhanaei/projects/TERNARY
```

This reduces approval prompts at the source. Still implement fast blocked-prompt detection because approvals can happen for other valid reasons.
