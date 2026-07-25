# Conductor Native Runtime Direction

- **status:** active direction
- **decided_by:** Ahmed
- **decided_at:** 2026-07-18
- **supersedes:** the Herdr-integration implementation direction in `feature-spec-herdr-runtime.md` and `herdr-runtime-integration-plan.md`
- **implementation authorization:** Phase A authorized by Ahmed on 2026-07-18T12:36:08Z; later phases remain checkpoint-gated

## Decision

Conductor will **not integrate, install, invoke, embed, or depend on Herdr**.

Herdr is reference material only. Conductor may learn product and operational ideas from public behavioral observation and documentation, but its implementation must be independently designed and written in Conductor's own codebase. No source-code copying, vendoring, API dependency, plugin installation, socket connection, runtime process, or persistence dependency is permitted.

## Product Intent

Improve Conductor's own tmux-backed runtime experience while preserving its existing artifact-first authority model:

```text
Conductor owns task state, evidence, verification, merge/close, and reconciliation.
Conductor-native runtime surfaces own lane observation, terminal layout, event history, and recovery hints.
Hermes owns final browser/UI verification and operator reporting.
```

## Ideas to Adapt Independently

1. Persistent named workspaces, tabs, and panes for project/track/task visibility.
2. A structured lane registry: stable lane identity, provider, workspace/worktree, state, current task, and last observation.
3. Append-only runtime observations/events with rebuildable projections and explicit unresolved ownership.
4. An operator control panel that projects Conductor artifacts and tmux state, without becoming a second state authority.
5. Event-assisted monitoring as the steady-state runtime model: tmux/control-mode output and lifecycle events plus filesystem events for Conductor artifacts trigger observation, classification, verification, and operator updates. Periodic pane polling is prohibited; reconciliation is limited to startup/restart and explicit event-stream-gap recovery.
6. Safe lifecycle/recovery actions: inspect, capture, restore hints, and explicit operator prompts.

## Non-Negotiable Boundaries

- No Herdr binary, CLI, package, source tree, plugin, socket API, or runtime service.
- No copying source code or reproducing undocumented proprietary/internal implementation details.
- No external runtime state may promote Conductor task state.
- `done`/idle pane signals remain hints; only Conductor verification can advance a task.
- Task-to-lane attribution requires stable lane target plus matching task/worktree evidence; otherwise record `unresolved_event`.
- tmux remains the only runtime substrate for this initiative.

## Replacement Delivery Sequence

### Phase A — Native runtime contract
Extract a Conductor-owned `LaneRuntime` interface and a behaviorally identical `TmuxLaneRuntime`; add contract, persistence-migration, and safety refusal tests.

### Phase B — Native observation ledger
Add normalized tmux observations and append-only events under `.conductor/runtime/`, with deterministic lane/worktree correlation and rebuildable projections.

### Phase C — Native operator panel
Create explicit terminal layout/projection commands from `.conductor` state and live tmux capture. It must be idempotent, read-only with respect to task state, and evidence-labeled.

### Phase D — Event-assisted monitor/recovery improvements
Add a durable event bridge, material-change deduplication, blocked-prompt action surfacing, restart reconciliation, and workspace-provenance checks. Replace the watch loop's periodic pane capture with event-driven processing; reconcile only after restart, explicit operator refresh, or detected event-stream loss.

### Phase E — Disposable end-to-end proof
Run a Conductor-only pilot: formal dispatch, busy/blocked safety cases, result artifact, verification, restart/reconcile, panel-to-artifact comparison, and merge/close gates.

## Required Evidence

- Unit/contract tests for every runtime state and unsafe-delivery refusal.
- Full Conductor suite and `git diff --check`.
- Real tmux smoke evidence in a disposable track/worktree.
- Hermes-owned terminal/UI readback for the operator panel.
- No Herdr executable, API, or dependency present in commands, configuration, lockfiles, or task artifacts.
