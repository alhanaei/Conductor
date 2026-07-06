# Conductor — Deep Comparative Analysis of Referenced Implementations

- Date: 2026-06-28T22:44:29+04:00
- Scope: Sakana Fugu, ethersphere/swarm-cli, ruvnet/ruflo, Yeachan-Heo/oh-my-claudecode, Ibrahim-3d/orchestrator-supaconductor
- Method: shallow cloned all repositories to `/tmp/conductor-research`, inspected README/config/docs/skills/source tree, read Fugu technical report text with `pdftotext`, captured GitHub metadata via GitHub API.
- Implementation status for Conductor: planning only; no build authorization assumed.

## Executive Finding

Ahmed's Conductor should not copy generic orchestration frameworks. The successful systems here converge on a different pattern:

> **A conductor is a practical control plane over real agent runtimes.** It decomposes goals, chooses topology, dispatches workers, constrains worker visibility, coordinates through durable messages/files, monitors heartbeats, gates approvals, verifies outputs, and preserves operator control.

The strongest implementation evidence comes from:

1. **Sakana Fugu** — learned/query-adaptive orchestration and access-list-controlled communication topology.
2. **SupaConductor** — file-based track system, evaluate-loop, message bus, workers, quality gates, board decision protocol.
3. **oh-my-claudecode** — productionized Claude Code plugin/CLI with team pipeline, tmux CLI workers, HUD, sessions, `.omc` state, multiple execution modes.
4. **Ruflo** — full meta-harness: hooks, MCP server, swarms, memory, federation, plugins, GOAP planner, background workers, observability.
5. **swarm-cli** — not an AI-agent orchestrator, but a strong CLI UX/reference for automation modes, local config, prompts, quiet output, history, and composable command design.

## Repository Evidence Snapshot

| Repo | Stars | Language | License | Relevant Shape |
|---|---:|---|---|---|
| `SakanaAI/fugu` | 597 | Shell/config + report | none detected | Model-as-orchestrator delivered through Codex profile; learned multi-agent scaffolds, communication topology, access lists, agent isolation |
| `ethersphere/swarm-cli` | 48 | TypeScript | BSD-3-Clause | Decentralized storage CLI, not AI; useful CLI architecture and automation UX |
| `ruvnet/ruflo` | 61,883 | TypeScript + Rust components | MIT | Agent meta-harness for Claude Code/Codex: MCP, hooks, daemon, 100+ agents, swarms, memory, federation, plugins, GOAP UI |
| `Yeachan-Heo/oh-my-claudecode` | 37,110 | TypeScript | MIT | Teams-first Claude Code orchestration: Team pipeline, tmux CLI workers, HUD, skills, `.omc` state, replay/session artifacts |
| `Ibrahim-3d/orchestrator-supaconductor` | 360 | Python/Markdown plugin | GitHub API says AGPL-3.0; README badge says MIT — verify before reuse | Claude Code plugin: Evaluate-Loop, tracks, message bus, board, parallel dispatcher, evaluators, knowledge |

## 1. Sakana Fugu

### What it is

Fugu is a multi-agent system exposed as one model/API/profile. The repo mostly ships Codex integration, config, installer, demos, and a technical report. The README says Fugu dynamically orchestrates frontier models for complex multi-step tasks and can be installed into Codex via `codex-fugu`.

### Evidence

- README: “multi-agent system delivered as one model.”
- README: Fugu dynamically coordinates a diverse pool of powerful models.
- `docs/commands_details.md`: installer pins Codex, deploys Fugu config, stores API key, backs up/restores Codex config, forwards arguments to `codex -p fugu`.
- `configs/files/fugu.json`: exposes `fugu` and `fugu-ultra` with 1M context window, reasoning levels, parallel tool call support, shell-command environment safety instructions.
- Technical report: Fugu models are orchestrator models that dynamically devise agentic scaffolds.
- Technical report: Fugu-Ultra builds on “Conductor,” where the Conductor outputs workflows as natural language, divides tasks, assigns subtasks, and defines targeted communication strategies.
- Technical report: each workflow step includes a subtask string, assigned worker id, and an access list describing which prior outputs enter that worker's context.
- Technical report: it tracks selected models, communication topology, and assigned subtasks throughout the interaction.
- Technical report: intra-workflow agent isolation prevents orchestration collapse, where the first tool-using agent steers all future agents into redundant trajectories.

### Design lessons for Conductor

**Adopt directly:**

1. **Access-list communication topology**
   - Workers should not automatically see all other worker transcripts.
   - Every task/subtask should declare exactly which prior outputs are visible.

2. **Agent isolation as a quality feature**
   - Conductor should isolate worktrees, transcripts, and tool trajectories by default.
   - Shared context should be a deliberate message/reference, not a global paste.

3. **Adaptive scaffold generation**
   - A conductor can output a plan/topology, not just a task list.
   - The scaffold should include worker roles, dependencies, allowed context, verification gates, and merge policy.

4. **One interface over many workers**
   - Operator talks to Conductor; Conductor chooses worker structure.

**Do not copy blindly:**

- Fugu is model/API-centric; Ahmed’s Conductor is local-first runtime/control-plane-centric.
- Fugu's learned coordinator is not needed for MVP. Start deterministic; add model-assisted topology proposals later.

## 2. ethersphere/swarm-cli

### What it is

This is not an AI multi-agent orchestrator. It is a TypeScript CLI for managing a Bee node and interacting with the Ethereum Swarm decentralized storage network.

### Why it still matters

It is useful as a mature CLI product pattern:

- Many command groups with consistent help.
- Interactive prompts for missing required inputs.
- `--quiet` mode for automation and parseable output.
- Local config directory under `~/.swarm-cli`.
- Environment-variable override conventions.
- Local upload history with privacy notice and opt-out.
- Autocomplete generation/installation.
- Examples of automating CLI tasks in CI/terminal.

### Design lessons for Conductor

**Adopt:**

1. **Interactive + automation duality**
   - Every command should support human-friendly mode and machine-readable mode.
   - Conductor CLI should have `--json` / `--quiet` for scripts and Telegram bridge.

2. **Config precedence contract**
   - CLI args > env vars > config file > defaults.
   - Document this from Phase 1.

3. **History/privacy transparency**
   - Conductor stores prompts/transcripts/messages. It needs explicit history policy and opt-out/redaction controls.

4. **Shell composability**
   - Status/check commands should exit non-zero on failure and print parsable one-line results in quiet mode.

**Do not treat as competitor:**

- It has no coding-agent conductor logic. Its value is CLI UX, config, history, and automation conventions.

## 3. Ruflo

### What it is

Ruflo describes itself as an agent meta-harness for Claude Code and Codex. It is a large TypeScript/Rust ecosystem with plugins, MCP server, hooks, daemon, agents, memory, federation, and UIs.

### Evidence

- README: “Agent = Model + Harness.”
- README: harness gives the model tools, memory, loops, sandboxes, and controls.
- README: `npx ruflo init` installs a full loop: 98 agents, 60+ commands, 30 skills, MCP server, hooks, daemon.
- Plugin list includes core, swarm, autopilot, loop-workers, workflows, federation, agentdb, RAG memory, RVF memory save/restore, knowledge graph, intelligence, graph-intelligence, DAA, local LLM routing, goals, testgen, browser, security, observability, cost tracker.
- README: full system has comms layer, swarm coordination, self-learning, vector memory, background workers, plugin marketplace, multi-provider support, security, agent federation.
- README: GOAP planner UI decomposes plain-English goals into preconditions/actions/A* path, then dispatches work to live agents.
- README: federation uses identity, PII stripping, signed/encrypted channels, trust scoring, compliance audit trail.

### Design lessons for Conductor

**Adopt:**

1. **Harness framing**
   - Conductor is not “the model.” It is the harness: tools, memory, loops, sandboxes, controls, messaging, verification.

2. **Plugin architecture, but later**
   - Keep Phase 1/2 simple, but design extension points for runtime adapters, memory adapters, notification adapters, verifier adapters.

3. **Hooks and daemon**
   - Conductor needs event hooks: lane started, task assigned, message received, heartbeat stale, approval needed, verification failed, task complete.

4. **Memory separation**
   - Use local run memory, project knowledge, and curated reusable patterns as different layers.

5. **Federation as long-term track**
   - Remote agent collaboration is not MVP, but the message envelope should not preclude cross-machine peers later.

6. **MetaHarness idea**
   - Conductor should have `doctor`/`audit` to grade project readiness, lane health, auth, dangerous configs, stale state, and unverified claims.

**Risks to avoid:**

- Ruflo is broad; Conductor should not become a 35-plugin platform before the core lane/message loop works.
- Avoid too many agents/commands early. Build a narrow, inspectable kernel first.

## 4. oh-my-claudecode

### What it is

OMC is a multi-agent orchestration system for Claude Code with both plugin/in-session skills and a terminal CLI. It has “Team” as its canonical orchestration surface and supports tmux CLI workers for Codex, Gemini, Antigravity, Grok, Cursor, and Claude.

### Evidence

- README: “Multi-agent orchestration for Claude Code. Zero learning curve.”
- Quick start: install as Claude Code plugin or npm CLI (`omc`).
- Table: terminal CLI vs in-session skills.
- `omc ask` / `/ask` route to provider advisor flows.
- `omc team N:provider` launches tmux CLI workers; `/team` uses Claude Code native team workflow.
- Team pipeline: `team-plan → team-prd → team-exec → team-verify → team-fix`.
- Workers spawn on demand and die when done.
- Features include Team, ccg advisor synthesis, Autopilot, Ultrawork, Ralph verify/fix loops, UltraQA repeated quality gates, Artifact-only Ultragoal.
- `.omc/` stores runtime state, session data, plans, logs, handoffs, research notes, local artifacts; `.omc/skills/**` can be committed.
- Multi-repo workspace support via `.omc-workspace` marker.
- Monitoring includes HUD, session summaries, replay logs, friction reports.
- Native Team worktrees are behind opt-in/config gate.

### Design lessons for Conductor

**Adopt:**

1. **Explicit loop authority**
   - OMC warns to use only one primary loop authority in a session. Conductor needs the same rule.
   - Avoid `/goal`, Ralph, Team, dispatcher, and Conductor all simultaneously claiming completion.

2. **Mode taxonomy**
   - Separate Team, single-agent verify loop, QA loop, artifact-only handoff, advisor synthesis.
   - Conductor can define fewer canonical modes:
     - `plan-only`
     - `dispatch`
     - `verify-loop`
     - `artifact-only`
     - `status/recovery`

3. **State-root contract**
   - `.omc/` and `.omc-workspace` show how important state root resolution is.
   - Conductor needs `.conductor/` plus optional workspace marker for multi-repo state.

4. **HUD/session/replay artifacts**
   - Conductor should store replayable event logs and summaries from the start.

5. **Provider advisor pattern**
   - `/ask codex`, `/ask gemini`, etc. can map to Conductor’s advisor workers before full dispatch.

**Divergence:**

- OMC is Claude Code/plugin-first. Ahmed’s Conductor should be Hermes/tmux/control-plane-first, with Claude/Codex/Gemini/Grok as lanes.
- OMC workers die when done; Ahmed may prefer persistent visible lanes for some providers. Conductor should support both ephemeral task lanes and persistent project lanes.

## 5. orchestrator-supaconductor

### What it is

SupaConductor is a Claude Code plugin that converts a goal into a track/spec/plan, evaluates the plan, executes tasks in parallel, evaluates execution, fixes failures, and completes only when quality gates pass. It also includes a Board of Directors deliberation mechanism and file-based message bus.

### Evidence

- README: one command `/go <goal>` plans, executes, checks, fixes, and marks complete.
- Evaluate-Loop: Plan → Evaluate Plan → Execute → Evaluate Execution → Fix/Complete.
- Parallel execution uses dependency graph.
- Two modes: `agentic` and `human-in-the-loop` in `conductor/config.json`.
- Board of Directors for high-stakes decisions: architect/product/security/operations/experience perspectives, discussion, vote, written rationale.
- Project structure: `conductor/tracks.md`, `config.json`, `workflow.md`, `authority-matrix.md`, `decision-log.md`, `product.md`, `tech-stack.md`, `knowledge/patterns.md`, `knowledge/errors.json`, `tracks/<track>/{spec.md,plan.md,metadata.json}`.
- Message bus skill:
  - `conductor/tracks/{track}/.message-bus/queue.jsonl`
  - `.lock_mutex` with OS-level `fcntl`
  - `locks.json`
  - `worker-status.json`
  - `events/` signal files
  - board session artifacts
- Message types: `PROGRESS`, `TASK_COMPLETE`, `TASK_FAILED`, `FILE_LOCK`, `FILE_UNLOCK`, `BLOCKED`, `BOARD_ASSESS`, `BOARD_DISCUSS`, `BOARD_VOTE`, `BOARD_RESOLVE`.
- Heartbeats every 5 minutes.
- Recent release notes include plan revision guard, execution state reconciliation, atomic file locks, bounded knowledge injection.

### Design lessons for Conductor

**Adopt strongly:**

1. **Evaluate-loop as backbone**
   - Conductor should use: Intake → Plan → Plan Review → Dispatch → Verify → Fix → Complete.

2. **Track model**
   - Track = durable unit of work with spec, plan, metadata, messages, decisions, status.

3. **Message bus kernel**
   - Append-only `queue.jsonl` plus status projections and event files is exactly aligned with Ahmed’s artifact-driven workflow.

4. **Atomic file locks**
   - File lock protocol should be in Phase 1/2, not later.

5. **Bounded knowledge injection**
   - Keep context briefs capped and source-linked.

6. **Plan revision guard / fix loop limits**
   - Prevent infinite loops via max revisions/fix cycles.

7. **Execution state reconciliation**
   - On resume, derive state from plan checkboxes + metadata + messages + artifacts.

8. **Board/decision gate split**
   - This aligns with Ahmed’s synthesis-and-Go/No-Go pattern: synthesis combines evidence; decision gate issues recommendation.

**Divergence:**

- SupaConductor is Claude Code plugin-only. Ahmed’s Conductor should manage external tmux lanes and Telegram/Hermes verification.
- SupaConductor’s message bus examples are partly prompt/spec pseudocode; Conductor should implement it as real tested code.
- License ambiguity must be resolved before copying any code/content: GitHub API reports AGPL-3.0, README badge says MIT.

## Cross-System Convergence

| Pattern | Fugu | Ruflo | OMC | SupaConductor | Ground truth for Conductor |
|---|---|---|---|---|---|
| Goal → scaffold/plan | yes | yes | yes | yes | required |
| Access-controlled worker context | explicit access lists | partial via memory/tool scopes | partial via session/state | partial via track/message bus | required |
| Durable local state | Codex/session config | `.claude-flow`, MCP/DB | `.omc` | `conductor/` | required |
| Message bus/inbox | communication topology | federation/comms | artifacts/sessions | explicit `queue.jsonl` | required |
| Worker isolation | agent trajectory isolation | sandboxes/plugins | worktree mode emerging | file locks/worker state | required |
| Heartbeat/monitoring | orchestrator state | daemon/workers | HUD/session artifacts | worker heartbeats | required |
| Verification gates | benchmark/reward training | testgen/security/observability plugins | verify/fix loops | evaluate execution/fix | required |
| Human approval | not user-facing | security/federation policies | explicit mode discipline | human-in-loop mode/board | required |
| CLI automation UX | Codex launcher | CLI/MCP/plugin | CLI + plugin | slash commands | swarm-cli best practices |

## Recommended Conductor Architecture After This Analysis

### Product positioning

Conductor should be:

> A local-first, tmux-visible, artifact-driven conductor for real coding-agent CLIs. It turns a goal into a track, builds an access-controlled task topology, dispatches workers into isolated lanes/worktrees, coordinates via a durable message bus, monitors heartbeats, gates approvals, verifies outputs, and reports through Hermes/Telegram.

### Core architecture

```text
Operator / Hermes / Telegram / CLI
          |
          v
Conductor CLI + Service
  - goal intake
  - track creation/resume
  - scaffold/topology planner
  - dispatcher/scheduler
  - message bus
  - lane runtime adapters
  - verifier/evaluator loop
  - notification/recovery
          |
          v
.conductor/ workspace state
  tracks/<track_id>/spec.md
  tracks/<track_id>/plan.md
  tracks/<track_id>/metadata.json
  tracks/<track_id>/.message-bus/queue.jsonl
  tracks/<track_id>/tasks/<task_id>/...
  lanes/<lane_id>.json
  events.jsonl
          |
          v
tmux / worktree / CLI agents
  claude | codex | gemini | grok | cursor | opencode
```

### Essential domain objects

1. `Track`
2. `Task`
3. `TaskAttempt`
4. `WorkerLane`
5. `WorktreeState`
6. `MessageEnvelope`
7. `AccessList`
8. `FileLock`
9. `HeartbeatState`
10. `ApprovalRequest`
11. `VerificationGate`
12. `RouteDecision`
13. `OperatorNotification`
14. `KnowledgeBrief`
15. `ResumeReconciliationReport`

## Build Plan Proposal

### Phase 0 — Decision lock

Decide before coding:

1. State root: `.conductor/` recommended; support `.conductor-workspace` later.
2. Runtime: Python recommended for Ahmed/Hermes fit.
3. Persistence: file-first JSON/JSONL/Markdown; SQLite optional later for message indexes.
4. Lane model: support persistent tmux lanes and ephemeral task lanes.
5. Default mode: human-in-the-loop for plan approval and merge approval; agentic execution inside approved slices.

### Phase 1 — Real Conductor kernel, no tmux yet

Implement and test:

- state root resolver
- track creation/resume
- spec/plan artifact layout
- metadata schema
- message bus `queue.jsonl`
- event files
- atomic file locks with `fcntl`
- worker status/heartbeat projections
- access-list model
- route-decision records
- JSON/Markdown read/write utilities with atomic writes
- CLI commands:
  - `conductor init`
  - `conductor track new`
  - `conductor status --json`
  - `conductor message send/list`
  - `conductor lock acquire/release`
  - `conductor doctor`

Acceptance:

- Can create a track and append messages.
- Can recover status from artifacts after restart.
- Locks are atomic under concurrent writers.
- `status --json` is parseable for Telegram/Hermes.

### Phase 2 — Topology planner and evaluate-loop artifacts

Implement:

- goal intake
- spec scaffold
- plan scaffold with DAG/dependencies
- plan review gate
- max plan revision counter
- access-list assignment per task
- bounded knowledge brief, max 500 tokens by default
- CLI commands:
  - `conductor go --plan-only "goal"`
  - `conductor plan review`
  - `conductor approve plan`

Acceptance:

- A goal becomes a track with spec + plan + metadata.
- Plan includes dependencies and verification criteria.
- Plan approval is explicit and persisted.
- No worker dispatch occurs before approval.

### Phase 3 — tmux lane adapter

Implement:

- lane registry
- tmux session/window target parsing
- provider profiles: claude, codex, gemini, grok, cursor/opencode later
- classify readiness: absent, shell, provider_ready, busy, blocked_prompt, unknown
- submit artifact-based instruction
- transcript capture
- heartbeat watcher
- `conductor lane ensure/status/capture/submit`

Acceptance:

- Does not paste tasks into bare shell accidentally.
- Can submit a short instruction referencing task artifact.
- Captures pane output and marks delivery state.

### Phase 4 — Worktree + dispatch loop

Implement:

- one worktree per task/attempt
- branch naming policy
- task artifact writer
- lane assignment scheduler
- route-decision records
- worker status updates
- follow-up/nudge command
- `conductor dispatch <track>`
- `conductor followup <task>`

Acceptance:

- Independent tasks dispatch to separate lanes/worktrees.
- Messages and status update as workers progress.
- Blocked/stale tasks are visible.

### Phase 5 — Verification-gated completion

Implement:

- verification gate model
- command runner for approved verification commands
- evaluator result artifacts
- fix-loop counter
- merge approval gate
- resume reconciliation from plan + metadata + messages + worktree state
- `conductor verify`, `conductor fix`, `conductor close`

Acceptance:

- Worker completion does not equal task completion.
- Verification failure returns task to fix/blocked state with evidence.
- Completion report includes evidence and remaining risks.

### Phase 6 — Hermes/Telegram operator integration

Implement:

- status summary renderer
- operator notifications for terminal states only by default
- approval prompts as Telegram actions later
- heartbeat summary every 5 minutes only for active long runs
- artifact links in messages

Acceptance:

- Ahmed can submit, monitor, approve, nudge, and verify from Hermes/Telegram without reading raw files.

## Immediate Updates Needed to Existing Conductor Plan

1. Replace generic `workflow/task/message/lane/event` Phase 1 with the richer domain objects above.
2. Add access-list controlled context visibility from Fugu.
3. Add SupaConductor-style message bus and lock files.
4. Add OMC-style loop-authority rule.
5. Add Ruflo-style harness framing and extension seams.
6. Add swarm-cli-style CLI contract: interactive by default, `--json`/`--quiet` for automation.
7. Add plan approval and merge approval as separate gates.
8. Add bounded knowledge injection as a first-class design rule.

## Decision Recommendation

Proceed with a **file-first Python Conductor kernel**. Do not start with tmux automation. The most successful systems all have a durable state/messaging substrate; tmux/agents should attach to that substrate, not define it.

Recommended first implementation slice after approval:

> Phase 1: `.conductor/` state root + tracks + message bus + locks + heartbeat/status projections + CLI JSON status.

This gives Ahmed a real foundation that can later host tmux, worktrees, Telegram, and provider lanes without rewriting the state model.
