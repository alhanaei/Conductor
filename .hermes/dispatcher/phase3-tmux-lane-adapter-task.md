# Conductor Phase 3 — tmux Lane Adapter

## Objective
Implement Phase 3 from `.hermes/deep-analysis/next-build-plan.md`: safely interact with visible tmux agent lanes through Conductor. Build a minimal but robust lane adapter layer: target parsing, provider registry, readiness classification, transcript capture, artifact-based prompt submission, delivery events, and heartbeat/status records.

## Authorization
Ahmed said: “Proceed” after Hermes verified Phase 2. Treat Phase 3 implementation as authorized.

Already verified baseline:
- Phase 1: durable state/message substrate complete.
- Phase 2: goal intake + plan artifacts complete.
- Current tests: `python -m pytest -q` => 67 passed.

## Source documents
- `.hermes/deep-analysis/next-build-plan.md` lines 130-165
- `.hermes/deep-analysis/architecture-map.md` Lane Runtime Adapter section
- Existing implementation in `src/conductor/` and tests in `tests/`

## Required CLI surface
Implement these commands unless a minor equivalent shape is strongly justified:

```bash
python -m conductor lane ensure --target Conductor:claude --json
python -m conductor lane status --target Conductor:claude --json
python -m conductor lane capture --target Conductor:claude --json
python -m conductor lane submit --target Conductor:claude --task-file <path> --json
```

Use `python -m conductor` consistently in tests/smokes.

## Required behavior

### 1. Target parser
- Parse `session:window` / `project:provider` style lane targets.
- Validate non-empty session/project and window/provider segments.
- Persist escaped lane records under `.conductor/lanes/<escaped_target>.json` or equivalent Phase 1 state root location.
- Include raw target, session, window/provider, provider, and timestamps in lane status.

### 2. Provider profile registry
- Add provider profiles for: `claude`, `codex`, `gemini`, `grok`.
- Later providers (`cursor`, `opencode`) may be left as future extension points.
- Provider-specific classifier patterns belong at adapter edge, not in core business logic.

### 3. Lane readiness classifier
Classify tmux pane state into:
- `absent`
- `shell`
- `provider_ready`
- `busy`
- `blocked_prompt`
- `unknown`

Minimum classification expectations:
- Missing tmux session/window => `absent`.
- Shell prompt / bash / zsh / fish / sh with no provider UI => `shell`.
- Visible provider prompt ready for input => `provider_ready`.
- Provider thinking/working/incubating/running command => `busy`.
- Approval/auth/trust/rating/prompt requiring operator action => `blocked_prompt`.
- Anything else => `unknown`.

Keep classifier deterministic and testable. If tmux is unavailable, degrade cleanly with actionable error/status rather than crashing.

### 4. Transcript capture
- `lane capture` should capture recent pane transcript evidence.
- It must return JSON fields including target, readiness/classification, transcript text or transcript path, captured_at, and line count.
- If storing transcript artifacts, use `.conductor/lanes/` or `.conductor/events.jsonl` references.

### 5. Artifact-based prompt submission
- `lane submit --task-file <path>` must submit only a short artifact-reference instruction, not paste the full task file body.
- It must refuse to submit when readiness is `absent`, `shell`, `busy`, `blocked_prompt`, or `unknown`, unless you add an explicit safe override. Default behavior must be safe.
- Acceptance focus: **does not paste work into a bare shell**.
- Submitted instruction should be concise, e.g. `Read <task-file> and execute it. Write result artifacts when done.`

### 6. Delivery event records and heartbeat/status
- Record delivery attempts/events in `.conductor/events.jsonl` and/or lane-specific JSON.
- `lane status --json` should expose last readiness, last capture/submission, last event, and heartbeat/update timestamps where available.
- Heartbeat watcher can be minimal in this phase: record heartbeat timestamps/status projections. Do not build the Phase 4 dispatch loop.

## Non-goals
- No approved task dispatch scheduler.
- No worktree allocation.
- No branch naming policy.
- No worker result ingestion beyond lane status/events.
- No Telegram/Hermes integration.
- No model-assisted routing.
- Do not initialize git unless Ahmed explicitly asks.

## Tests
Add focused tests for:
- target parsing and escaped lane ID/path stability
- provider registry entries
- readiness classifier with sample pane transcripts for each state
- `lane status --json` for absent lane and/or mocked tmux output
- `lane submit` refuses absent/shell/busy/blocked/unknown
- `lane submit` sends only short artifact reference when provider_ready (mock tmux sender; do not require a real provider lane in unit tests)
- delivery event/heartbeat/status persistence

Use monkeypatch/fakes where needed; avoid tests that depend on a real Claude/Codex/Gemini/Grok UI.

## Verification commands
Run and record exact output:

```bash
cd /home/alhanaei/projects/Conductor
python -m pytest -q
rm -rf /tmp/conductor-phase3-smoke && mkdir -p /tmp/conductor-phase3-smoke
cd /tmp/conductor-phase3-smoke
PYTHONPATH=/home/alhanaei/projects/Conductor/src python -m conductor init
PYTHONPATH=/home/alhanaei/projects/Conductor/src python -m conductor lane status --target missing-session:claude --json
PYTHONPATH=/home/alhanaei/projects/Conductor/src python -m conductor lane capture --target missing-session:claude --json
PYTHONPATH=/home/alhanaei/projects/Conductor/src python -m conductor lane submit --target missing-session:claude --task-file /tmp/nonexistent-task.md --json ; test $? -ne 0
```

If a safe real tmux smoke is available, also test `lane status --target conductor:claude --json` and `lane capture --target conductor:claude --json`, but do not submit into the live lane during smoke unless the classifier says `provider_ready` and the task file is harmless.

Parse JSON outputs in Python during verification.

## Expected deliverables
When complete:
1. Update run-scoped `.hermes/dispatcher/runs/<run_id>/result.md` with summary, files changed, exact verification output, and limitations/non-goals.
2. Update run-scoped `.hermes/dispatcher/runs/<run_id>/checkpoint.json` with `state: "ready_for_review"` or `state: "blocked"`.
3. Mirror result/checkpoint to top-level `.hermes/dispatcher/result.md` and `.hermes/dispatcher/checkpoint.json` if current run pattern expects that.
4. Update README status/usage lightly if appropriate.
5. Print `TASK_COMPLETE` only after artifacts are written.
