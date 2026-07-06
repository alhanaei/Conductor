# Conductor — Revised Next Build Plan

## Status

- implementation_authorized: false
- plan_stage: revised after successful-implementation review
- target_root: `/home/alhanaei/projects/Conductor`
- source analysis: `.hermes/deep-analysis/comparative-analysis-successful-implementations.md`

## Revised Product Positioning

Conductor is **not** a LangGraph/OpenAI Agents/CrewAI clone.

Conductor is:

> A local-first, tmux-visible, artifact-driven conductor for real coding-agent CLIs. It turns a goal into a track, builds an access-controlled task topology, dispatches workers into isolated lanes/worktrees, coordinates via a durable message bus, monitors heartbeats, gates approvals, verifies outputs, and reports through Hermes/Telegram.

## Design Sources Incorporated

| Source | Adopted Idea |
|---|---|
| Sakana Fugu | Access-list communication topology; worker trajectory isolation; adaptive scaffold/topology design |
| SupaConductor | Evaluate-loop, tracks, file message bus, OS-level file locks, worker heartbeats, board/decision protocol |
| oh-my-claudecode | Loop authority discipline, team pipeline, tmux CLI workers, `.omc`-style state-root contract, replay/HUD artifacts |
| Ruflo | Harness framing, plugin seams, hooks/daemon, memory layers, federation as future track, metaharness/doctor concept |
| swarm-cli | CLI UX: interactive + automation modes, config precedence, history/privacy notices, quiet/JSON output |

## Phase 0 — Decision Lock

Before coding, confirm:

1. **State root:** `.conductor/` under project root.
2. **Workspace marker:** defer `.conductor-workspace` until multi-repo support.
3. **Implementation language:** Python.
4. **Persistence:** file-first JSON/JSONL/Markdown; SQLite optional later.
5. **Runtime:** support both persistent tmux lanes and ephemeral task lanes later.
6. **Default approvals:** plan approval and merge approval are separate gates.
7. **Default mode:** human-in-the-loop for plan/merge approval; agentic execution inside approved slices.

## Phase 1 — Conductor Kernel: State, Tracks, Message Bus

Goal: build the durable substrate before any tmux automation.

### Deliverables

- Python package skeleton
- `.conductor/` state-root resolver
- `Track` schema
- `Task` schema
- `TaskAttempt` schema
- `WorkerLane` schema
- `MessageEnvelope` schema
- `AccessList` schema
- `FileLock` schema
- `HeartbeatState` schema
- `ApprovalRequest` schema
- `VerificationGate` schema
- `RouteDecision` schema
- `OperatorNotification` schema
- append-only message bus: `tracks/<track_id>/.message-bus/queue.jsonl`
- event files: `tracks/<track_id>/.message-bus/events/*.event`
- status projection: `worker-status.json`
- file lock projection: `locks.json`
- OS-level mutex file: `.lock_mutex` using `fcntl`
- atomic JSON/JSONL write utilities

### CLI Commands

```bash
conductor init
conductor track new "<goal>"
conductor status --json
conductor message send --track <id> --type PROGRESS --body ...
conductor message list --track <id> --json
conductor lock acquire --track <id> --file <path> --worker <id>
conductor lock release --track <id> --file <path> --worker <id>
conductor doctor --json
```

### Acceptance Criteria

- Can create `.conductor/` and a track.
- Can append/read messages from `queue.jsonl`.
- Can recover status after process restart.
- Concurrent lock acquisition is atomic and tested.
- `status --json` produces parseable operator output.
- No tmux, provider, or worker dispatch yet.

### Verification

```bash
cd /home/alhanaei/projects/Conductor
python -m pytest -q
python -m conductor init --dry-run
python -m conductor status --json
```

## Phase 2 — Goal Intake and Topology/Plan Artifacts

Goal: convert a goal into a track/spec/plan/topology without dispatching workers.

### Deliverables

- goal intake command
- spec scaffold: `tracks/<track_id>/spec.md`
- plan scaffold: `tracks/<track_id>/plan.md`
- metadata: `tracks/<track_id>/metadata.json`
- task DAG model
- access-list assignment per task
- bounded knowledge brief, default max 500 tokens
- plan review gate
- max plan revision counter

### CLI Commands

```bash
conductor go --plan-only "<goal>"
conductor plan review --track <id>
conductor approve plan --track <id>
```

### Acceptance Criteria

- A goal produces a durable track.
- Plan includes dependencies, non-goals, files/surfaces, verification criteria.
- Each task has a context access list.
- Plan approval is explicit and persisted.
- No worker dispatch happens before approval.

## Phase 3 — tmux Lane Adapter

Goal: safely interact with visible agent lanes.

### Deliverables

- tmux target parser: `session:window` / `project:provider`
- provider profile registry: `claude`, `codex`, `gemini`, `grok`; later `cursor`, `opencode`
- lane readiness classifier:
  - absent
  - shell
  - provider_ready
  - busy
  - blocked_prompt
  - unknown
- transcript capture
- artifact-based prompt submission
- delivery event records
- heartbeat watcher

### CLI Commands

```bash
conductor lane ensure --target Conductor:claude
conductor lane status --target Conductor:claude --json
conductor lane capture --target Conductor:claude
conductor lane submit --target Conductor:claude --task-file <path>
```

### Acceptance Criteria

- Does not paste work into a bare shell.
- Detects absent/shell/provider-ready/busy states.
- Submits only short artifact references, not huge prompts.
- Captures transcript evidence.

## Phase 4 — Worktree and Dispatch Loop

Goal: approved tasks run in isolated worktrees/lanes.

### Deliverables

- worktree allocation policy
- branch naming policy
- task artifact writer
- lane scheduler
- route-decision records
- worker heartbeat updater
- follow-up/nudge command
- stale-risk classifier

### CLI Commands

```bash
conductor dispatch --track <id>
conductor task status --track <id> --task <task_id> --json
conductor followup --track <id> --task <task_id> --body-file <path>
conductor nudge --track <id> --task <task_id>
```

### Acceptance Criteria

- Independent approved tasks dispatch to separate lanes/worktrees.
- Worker state is visible through message bus and status projections.
- Blocked/stale tasks are detected from multiple signals.

## Phase 5 — Verification-Gated Completion

Goal: worker completion does not equal true completion.

### Deliverables

- verification gate runner
- evaluator result artifacts
- fix-loop counter
- merge approval gate
- resume reconciliation report
- final operator summary renderer

### CLI Commands

```bash
conductor verify --track <id>
conductor fix --track <id> --task <task_id>
conductor approve merge --track <id>
conductor close --track <id>
```

### Acceptance Criteria

- `TASK_COMPLETE` does not mark task complete until verification passes or is explicitly waived.
- Verification failure returns task to fix/blocked with concrete evidence.
- Merge requires separate approval.
- Resume reconstructs state from plan + metadata + messages + worktree/lane status.

## Phase 6 — Hermes / Telegram Operator Integration

Goal: Ahmed can operate Conductor from Hermes/Telegram.

### Deliverables

- Telegram-safe status summaries
- terminal-state notifications
- 5-minute heartbeat summaries for active long runs
- approval request payloads
- artifact links
- Hermes verification hook

### Acceptance Criteria

- Ahmed can submit, monitor, approve, nudge, verify, and close tracks without reading raw files manually.
- Telegram notifications are grounded in artifacts and verification evidence.

## First Implementation Slice After Approval

Build **Phase 1 only**.

Why:

- Every successful implementation reviewed depends on durable state before useful orchestration.
- tmux and agents should attach to the state/message substrate, not define it.
- Phase 1 is testable without external agent auth or active tmux sessions.

## Authorization State

Implementation is **not authorized** yet. This is a design-ready plan.
