# Conductor — Corrected Similar Implementation Review

- review_date: 2026-06-28
- correction: The relevant comparison set is **not** general agent frameworks such as LangGraph, CrewAI, or OpenAI Agents SDK. Conductor is closer to **local-first mission control for real CLI coding agents**: tmux panes, worktrees, message/inbox files, heartbeats, task queues, visible supervision, and verification/merge gates.
- method: GitHub Search API + GitHub repo metadata + raw README inspection.

## What Conductor Is Actually Adjacent To

Conductor is closest to systems that do this:

1. Run real agent CLIs such as Claude Code, Codex, Gemini, Cursor, OpenCode, Grok, etc.
2. Keep agents visible in tmux/terminal/workspace surfaces.
3. Fan out work across multiple workers/tasks.
4. Coordinate through files, mailboxes, queues, dashboards, or typed message stores.
5. Preserve operator control: inspect, nudge, approve, verify, merge, resume.
6. Prefer local-first execution over cloud-hosted black-box agents.

## Top 6 Most Relevant Implementations

| Rank | Project | Repo | Stars at review | Why it is relevant |
|---:|---|---|---:|---|
| 1 | CCB / Claude Codex Bridge | `SeemSeam/claude_codex_bridge` | 3,118 | Visible controllable multi-agent TUI workspace. Real panes, many CLI providers, internal communication, role packs, `/ask` delegation, mobile controller. |
| 2 | multi-agent-shogun | `yohey-w/multi-agent-shogun` | 1,355 | tmux-native hierarchy: Shogun → Karo → Ashigaru. YAML + tmux coordination, visible panes, dashboard, many workers. Very close to “conductor over agents.” |
| 3 | Overstory | `jayminwest/overstory` | 1,327 | Coordinator + workers in isolated worktrees, custom SQLite mail system, persistent orchestrator, inbox, traces, costs, nudge, merge, monitor. Archived, but architecturally important. |
| 4 | ultraswarm | `fubak/ultraswarm` | 55 | Durable multi-worker coding orchestrator. Standalone runner owns decomposition, routing, process supervision, isolated worktrees, adaptive review, approvals, recovery, reporting. |
| 5 | agencycli | `chenhg5/agencycli` | 143 | Self-managing AI agent teams. Markdown/YAML org chart, heartbeat scheduler, task queue, async inbox, confirmation gates, web console, Docker isolation. |
| 6 | Groundcrew | `ClipboardHealth/groundcrew` | 52 | Dispatch task backlog to local interactive agents. One worktree per task, real CLI panes, task-source routing, sandboxing, Linear/Jira/local source support. |

## 1. CCB / Claude Codex Bridge

- Source: https://github.com/SeemSeam/claude_codex_bridge
- Description: “Visible multi-agent CLI workspace for mixing Codex, Claude, Gemini, Kimi, Qwen, Cursor, Copilot, Pi, OpenCode, and other AI coding agents.”
- Language: Python
- Core ideas from README:
  - Designed around **agent parity**.
  - “Visible, controllable multi-agent cooperative TUI workspace.”
  - Every agent is a real terminal with layout control.
  - Runs multiple CLIs concurrently from one command.
  - Stable background communication for multi-line task orchestration.
  - Config defines tmux windows and agent groups.
  - Supports worktree-tagged workers, e.g. `worker1:codex(worktree), worker2:claude(worktree)`.
  - Agents can call `/ask` from workflow orchestration to delegate and hand off work automatically.
  - Sidebar shows windows, agents, internal communication state, and hot-reloadable tips.
  - Mobile app can switch windows/agents, render transcripts, send pane-native input, and upload/download attachments.
  - Role Packs package skills, memory, and dependencies into portable specialist agents.

### Lessons for Conductor

CCB is the strongest “visible multi-agent workspace” reference.

Borrow:

- Provider parity as a design principle.
- A topology config for windows/groups/agents.
- Real terminals, not fake wrapped agent APIs.
- Communication area/message state visible in the UI.
- Role packs as portable lane/persona packages.
- Mobile/remote controller as later operator surface.

Improve:

- Add stronger run/task identity and verification gates.
- Make message envelopes typed and durable from Phase 1.
- Make Conductor’s top-level task graph explicit, not only pane/group topology.

## 2. multi-agent-shogun

- Source: https://github.com/yohey-w/multi-agent-shogun
- Description: “Samurai-inspired multi-agent system for Claude Code. Orchestrate parallel AI tasks via tmux with shogun → karo → ashigaru hierarchy.”
- Language: Shell
- License: MIT
- Core ideas from README:
  - Runs up to 10 AI coding agents in parallel.
  - Supports Claude Code, Codex, Copilot, Kimi, OpenCode, Cursor, Antigravity.
  - One Shogun receives command and delegates.
  - Karo breaks down/distributes tasks.
  - Ashigaru workers execute in parallel.
  - Coordination uses YAML + tmux.
  - Claims “zero coordination overhead” because agents talk through YAML files on disk.
  - Every instruction, report, and decision is a plain YAML file.
  - Live tmux panes + dashboard for observability.
  - Hierarchy prevents conflicts through clear ownership and dedicated files per agent.

### Lessons for Conductor

Shogun is closest to the user’s words: **a conductor on top managing tasks**.

Borrow:

- Explicit command hierarchy.
- Files-on-disk as coordination substrate.
- Manager/worker separation.
- Visible panes as observability.
- Dedicated per-agent files to reduce conflict.

Improve:

- Replace theme-specific roles with neutral `conductor / scheduler / worker / verifier` roles.
- Use JSON/JSONL/Markdown envelopes instead of only YAML task files.
- Add restartable state machine, verification gates, and run-scoped events.

## 3. Overstory

- Source: https://github.com/jayminwest/overstory
- Description: “Multi-agent orchestration for AI coding agents — pluggable runtime adapters for Claude Code, Pi, and more.”
- Status: README says no longer maintained / archived, but the architecture is highly relevant.
- Language: TypeScript
- License: MIT
- Core ideas from README:
  - Turns a single coding session into a multi-agent team.
  - Spawns worker agents in isolated git worktrees.
  - Coordinates through a custom SQLite mail system.
  - Merges work back with tiered conflict handling.
  - Persistent coordinator/orchestrator commands.
  - `ov mail send/check/list/read` for inbox messaging.
  - `ov nudge` sends follow-up to stalled agents.
  - Live dashboard, inspect, trace, errors, replay, feed, logs, costs.
  - Runtime-agnostic `AgentRuntime` adapter handles spawning, config deployment, guard enforcement, readiness detection, transcript parsing.
  - `tmux` optional for attaching directly; headless subprocess workers are default.

### Lessons for Conductor

Overstory is the most important **messaging architecture** precedent.

Borrow:

- SQLite mail/inbox system as alternative to pure file JSONL.
- Coordinator and worker separation.
- Nudge/follow-up primitive.
- Trace/replay/cost/event feeds as first-class operations.
- Runtime adapter interface: spawn, readiness, transcript, guard enforcement.

Improve:

- Keep tmux visible as the default for Ahmed’s workflow, not optional.
- Avoid over-swarming by requiring implementation slices and verification gates.
- Keep project state readable in repo-local artifacts even if SQLite is added.

## 4. ultraswarm

- Source: https://github.com/fubak/ultraswarm
- Description: “Multi-CLI agent swarm orchestrated by Claude Code: external AI CLIs code in isolated worktrees, Claude verifies and merges.”
- Language: JavaScript
- License: MIT
- Core ideas from README:
  - Durable multi-worker coding orchestrator for Codex, Claude Code, Cursor Agent, Grok, and shell usage.
  - One standalone Node runner owns:
    - decomposition
    - worker routing
    - process supervision
    - isolated Git worktrees
    - adaptive review
    - transactional integration
    - approvals
    - recovery
    - reporting
  - Streams per-agent dispatch lines and gate results.
  - Periodic active/idle heartbeat keeps workers visible.
  - Repo-local worktrees under `.ultraswarm/worktrees`.
  - Plan and merge approvals are separate.
  - Executable task contracts and forbidden-path policy.
  - Per-task effort levels.
  - Per-CLI token/cost accounting.
  - Resume judges liveness from persisted orchestrator identity.

### Lessons for Conductor

ultraswarm is closest to the **durable runner** side of Conductor.

Borrow:

- One standalone runner owns the whole outer loop.
- Separate plan approval from merge approval.
- Worker routing + supervision + recovery in one control plane.
- Active/idle heartbeats for every worker.
- Repo-local worktree directories.
- Task contracts and forbidden-path policies.
- Token/cost accounting by worker.

Improve:

- Use tmux/pane state as first-class runtime evidence.
- Add unified messaging as a separate subsystem, not only runner output.
- Keep Telegram/operator notification as a core path.

## 5. agencycli

- Source: https://github.com/chenhg5/agencycli
- Description: “Lightweight CLI to build self-managing AI agent teams... agents run autonomously on a heartbeat schedule, talk to each other via inbox, and delegate tasks.”
- Language: Go
- Core ideas from README:
  - Define org chart once: teams, roles, projects, skills.
  - Agents assemble context, pick up tasks, and run autonomously.
  - Agents can hire, message, and coordinate with each other.
  - PM agent can create tasks for dev agent; dev can ask human for confirmation before merging; QA wakes on schedule.
  - Context composes from agency → team → role → project.
  - Autonomous heartbeat + wakeup routine.
  - Every participant, human or agent, has an inbox.
  - Messages are non-blocking and async.
  - Unread messages are injected at top of every wakeup prompt.
  - `confirm-request` creates blocking gate; task pauses until decision.
  - Agents run inside isolated Docker containers.
  - Web console includes messages, tasks, teams, roles, projects, schedules, run history, costs, session management, prompt editing, skills.
  - It positions itself as infrastructure, not an SDK.

### Lessons for Conductor

agencycli is the best reference for **agent inbox + heartbeat + human gates**.

Borrow:

- Every participant has inbox/outbox.
- Async messages injected at wakeup/next run.
- Blocking confirmation gates as task state.
- Heartbeat scheduler as normal operation mode.
- Context composition across role/project/team layers.
- Web console concepts for later.

Improve:

- Conductor should stay tmux/lane-centric and visible.
- Avoid giving agents full autonomy to invent work too early.
- Keep task graph and verification gates stronger than generic self-management.

## 6. Groundcrew

- Source: https://github.com/ClipboardHealth/groundcrew
- Description: “Dispatch your task backlog to local, interactive AI coding agents. One git worktree per task, sandboxed by default.”
- Language: TypeScript
- License: MIT
- Core ideas from README:
  - Watches assigned tasks.
  - Creates isolated worktrees.
  - Launches agent CLIs in dedicated terminals.
  - Leaves each task on its own PR-ready branch.
  - Runs locally with the operator’s tools, shell, and credentials.
  - Each task launches the real `claude` or `codex` CLI in its own terminal pane.
  - One worktree per task.
  - Sandboxed by default through Safehouse or Docker Sandboxes.
  - Pluggable task sources: Linear by default; Jira and local files supported.
  - Multi-agent routing via labels like `agent-claude`, `agent-codex`, `agent-any`.
  - Skips tasks blocked by non-terminal blockers.
  - Task description is the prompt; vague task gives vague PR.

### Lessons for Conductor

Groundcrew is a clean implementation of **task-source → worktree → real terminal agent → PR-ready branch**.

Borrow:

- Task source adapters.
- Label/routing-based agent selection.
- `agent-any` chooses a lane with headroom.
- Blocked-task skipping.
- Real CLI terminal panes instead of wrappers.
- Sandbox mode from the beginning.

Improve:

- Add conductor-controlled multi-task workflow graph, not only backlog scanning.
- Add richer messaging between workers and conductor.
- Add Hermes/Telegram operator feedback and verification evidence.

## Operator Cockpit References

These are not the core architecture, but they show the product surface Conductor may want later.

### Vibe Kanban

- Source: https://github.com/BloopAI/vibe-kanban
- Stars: 27,196
- Status: README says Vibe Kanban is sunsetting.
- Important ideas:
  - Kanban issues for planning work.
  - Workspaces where coding agents execute.
  - Each workspace gives an agent a branch, terminal, and dev server.
  - Diff review and inline comments sent back to agent.
  - Built-in browser/devtools/device emulation.
  - Supports many coding agents.

### dev-3.0

- Source: https://github.com/h0x91b/dev-3.0
- Stars: 204
- Important ideas:
  - “Mission control for the One Person Studio.”
  - Kanban cockpit for dozens of AI coding agents.
  - Each task gets git worktree + tmux session + agent.
  - Multiple agents per task via tmux split panes.
  - Live terminal previews, terminal bell alerts, one-click dev server.
  - Built-in code review and bug hunter packs.

## Design Patterns Conductor Should Adopt

### A. Conductor-owned task graph

Do not copy generic agent graphs. Use a practical coding-work graph:

```text
goal -> workflow -> tasks -> attempts -> lane sessions -> result -> verification -> merge/close
```

### B. Unified message envelope

Combine Overstory mail + agencycli inbox + Shogun YAML files:

```json
{
  "message_id": "msg_...",
  "workflow_id": "wf_...",
  "task_id": "task_...",
  "attempt_id": "attempt_...",
  "from": "conductor|worker:<id>|operator|verifier",
  "to": "conductor|worker:<id>|task:<id>|operator",
  "kind": "assignment|status|question|result|approval_request|verification|nudge|handoff",
  "body_ref": "messages/msg_....md",
  "requires_ack": false,
  "blocks_task": false,
  "causation_id": "msg_...",
  "created_at": "..."
}
```

### C. Lane runtime adapter

Conductor should not bind itself to only Claude or Codex. Use a provider adapter like Overstory/CCB:

```text
ensure_lane()
classify_readiness()
submit_artifact_instruction()
capture_transcript()
detect_blocked_prompt()
collect_usage()
terminate_or_resume()
```

### D. Worktree per task by default

This pattern appears repeatedly: CCB, Shogun, Overstory, ultraswarm, Groundcrew, Vibe Kanban, dev-3.0.

Conductor should treat worktrees as first-class state:

```json
{
  "task_id": "task_...",
  "worktree_path": ".conductor/worktrees/task_...",
  "base_branch": "main",
  "branch": "conductor/task_...",
  "merge_state": "not_ready|ready|approved|merged|rejected"
}
```

### E. Heartbeat and inbox as normal operation

agencycli and ultraswarm validate Ahmed’s existing instinct: heartbeat and inbox are not optional.

Conductor should include:

- lane heartbeat
- task heartbeat
- unread message count
- blocked approvals
- stale-risk classifier
- terminal state notifications

### F. Verification gates before completion

Conductor should improve on most tools by making this strict:

```text
worker_done != task_done
result_artifact_present != verified
verified != merged
```

### G. Operator control surface

Initial surface can be CLI + Telegram. Later UI can learn from Vibe Kanban/dev-3.0:

- board/list of workflows
- per-task live terminal preview
- message inbox
- approval queue
- diff/review panel
- verification evidence
- cost/usage display

## Revised Positioning

Conductor should be positioned as:

> A local-first conductor for real coding-agent CLIs: tmux-visible lanes, worktree-per-task isolation, typed inbox messaging, heartbeats, nudges, approvals, verification gates, and Telegram/CLI operator control.

Not:

- LangGraph clone
- OpenAI Agents SDK clone
- roleplay agent framework
- generic graph runtime

## Immediate Architecture Changes from This Review

Update Conductor’s Phase 1 schema to include:

1. `MessageEnvelope`
2. `InboxMessage`
3. `TaskAttempt`
4. `LaneSession`
5. `WorktreeState`
6. `ApprovalRequest`
7. `VerificationGate`
8. `HeartbeatState`
9. `RouteDecision`
10. `OperatorNotification`

Update Phase 2 to include:

1. tmux lane adapter
2. provider profile registry
3. artifact-based prompt submission
4. pane readiness classifier
5. blocked-prompt detector
6. transcript capture
7. heartbeat watcher

Update Phase 3 to include:

1. conductor scheduler loop
2. inbox drain/injection loop
3. nudge/follow-up command
4. stale-risk classifier
5. result ingestion
6. verification-gated completion
