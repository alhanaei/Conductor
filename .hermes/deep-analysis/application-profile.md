# Conductor — Application Profile

## Status

- stage: intake / architecture draft
- evidence_level: user-stated + inferred
- implementation_authorized: false
- project_root: `/home/alhanaei/projects/Conductor`

## Product Intent

Conductor is a dispatcher-style orchestration agent that runs above multiple tmux-backed AI agent lanes. It manages many tasks at once, coordinates agents through a unified messaging layer, and acts as the top-level control plane for planning, dispatch, monitoring, follow-up injection, and completion verification.

## Primary Users

| User | Need |
|---|---|
| Operator / Ahmed | Submit goals, inspect progress, intervene when blocked, receive concise task updates |
| Conductor agent | Decompose goals, route tasks, coordinate workers, enforce state transitions |
| Worker agents | Receive scoped assignments, report status/results, request help/input |
| Verifier / reviewer lane | Validate outputs against task acceptance criteria |

## Core Capabilities

1. **Task intake**
   - Accept high-level goals.
   - Convert goals into a workflow/task graph.
   - Track tasks, dependencies, priority, and ownership.

2. **Lane management**
   - Use tmux as the visible process fabric.
   - Maintain stable provider lanes such as `claude`, `codex`, `gemini`, `grok`, `review`, `run`, and `ops`.
   - Know whether a lane is ready, busy, blocked, stale, or complete.

3. **Unified messaging**
   - Use one message envelope format across operator→conductor, conductor→worker, worker→conductor, worker→worker, system events, and verifier outputs.
   - Preserve run/task identity on every message.
   - Support directed, broadcast, and task-scoped messages.

4. **Coordination / conductor loop**
   - Maintain the task graph.
   - Route work to agents.
   - Watch events/results.
   - Inject follow-ups when needed.
   - Avoid duplicate/conflicting work.

5. **Verification and closeout**
   - Require result artifacts from workers.
   - Run or request verification commands.
   - Track evidence level: worker-reported, tool-verified, Hermes/browser-verified, or unverified.
   - Notify the operator only when state is grounded.

## Non-Goals for MVP

- No distributed cloud scheduler in the first slice.
- No full web UI required in MVP.
- No long-term autonomous memory beyond local task/run history initially.
- No hidden background agent swarm without visible tmux/run artifacts.

## Quality Attributes

| Attribute | Requirement |
|---|---|
| Observability | Every run has durable state, event log, message log, and result artifact |
| Recoverability | Conductor can restart and rehydrate active runs from disk |
| Safety | Destructive actions require explicit authorization gates |
| Routing clarity | Every route decision is explainable and saved |
| Concurrency | Multi-agent tasks use run/task IDs, not lane names alone |
| Operator control | Human can inspect, pause, resume, or inject follow-up at task/run scope |

## Initial Known Risks

1. **Message bus ambiguity** — if messages are just pasted into tmux, identity and causality will be weak.
2. **State split-brain** — tmux pane state, JSON files, and agent claims may disagree.
3. **Over-orchestration** — conductor can become too heavy before the worker loop is reliable.
4. **Verification gap** — worker completion must not equal true completion without independent checks.
5. **Context bleed** — agents may act on stale goals unless task/run scoping is strict.
