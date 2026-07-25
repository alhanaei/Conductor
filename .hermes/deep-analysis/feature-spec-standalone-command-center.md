# Feature Spec — Conductor Standalone Command Center

- **status:** approved
- **created_at:** 2026-07-19T11:44:33+04:00
- **operator:** Ahmed
- **approved_by:** Ahmed
- **approved_at:** 2026-07-19T12:01:50+04:00
- **implementation_authorization:** authorized by Ahmed at 2026-07-19T12:01:50+04:00; execute in dependency order and retain existing Conductor gates
- **supersedes:** none; refines Phase C of `conductor-native-runtime-direction.md`
- **depends_on:** verified Phase A runtime contract; Phase B task-correlated observation ledger

## Problem

Conductor already orchestrates jobs through durable tracks, task artifacts, worktrees, tmux lanes, verification gates, and Hermes/Telegram-safe summaries. Its operator surface is command-by-command and chat-projected, not a coherent standalone command center. An operator cannot inspect the global job topology, active lanes, task provenance, blocked prompts, and evidence from one dedicated control surface without manually hopping between tmux sessions and CLI commands.

## Product Intent

Build a **Conductor-native standalone terminal command center** inspired only by the product-level workflow of persistent workspace/pane control:

```text
Hermes Agent / operator intent
          │
          ▼
Conductor command center (dedicated control session)
          │  artifact-backed commands and projections
          ▼
Conductor control plane (.conductor state, verification, routing)
          │
          ▼
separate project/task lane sessions and assigned worktrees
```

The command center is a projection and command gateway over Conductor's own state. It is not a provider runtime, task workspace, second task-state store, dashboard service, or replacement for Conductor verification.

## Users and Roles

| Role | Responsibility | Allowed actions |
|---|---|---|
| Ahmed | Operator and approval authority | inspect, approve/reject plans and merges, initiate/stop approved tracks, resolve concrete blockers |
| Hermes Agent | Control-plane interface and independent verifier | invoke the command-center interface, render grounded Telegram updates, inspect terminal/browser evidence, execute authorized operator actions |
| Conductor | Authoritative orchestrator | persist artifacts, route/dispatch jobs, verify claims, reconcile runs, advance/close tracks only through gates |
| Workers | Task executors | work only in assigned worktree/lane, write result evidence; cannot self-promote task state |

## Scope

### Initial standalone command-center wedge

1. A dedicated, named tmux **control session** separate from all worker/project lane sessions.
2. A deterministic command-center entrypoint that renders only Conductor-owned projections:
   - all-track overview and active-run counts;
   - selected-track task DAG, method, provider, assigned worktree, dispatch/verification state;
   - lane observation/provenance view with evidence timestamps and explicit confidence;
   - message/event and blocked-prompt action view;
   - exact artifact-backed next action.
3. Explicit control commands that delegate to existing Conductor gates, never bypass them:
   - inspect/select track;
   - inspect task/lane/evidence;
   - request plan/merge approval payloads;
   - invoke only already-authorized lifecycle actions (`loop`, `verify`, `advance`, `reconcile`, `close`) with their existing policy checks.
4. A Hermes adapter contract: Hermes interacts through documented machine-readable command-center output and artifact references rather than parsing raw tmux scrollback.
5. Session separation guarantees: control UI cannot launch a provider in a control pane, cannot become a worker target, and does not edit a task worktree.
6. Restart/recovery: rebuild the visible control projection from `.conductor/` state and fresh runtime observations; display disagreements as `unresolved_event` or `workspace_provenance_mismatch`.
7. Event-assisted monitoring replaces periodic pane polling: consume tmux control-mode output/lifecycle events and filesystem changes beneath `.conductor/`, then classify only affected lane/task projections. Reconciliation is an explicit recovery operation, not a recurring monitor tick.

### Explicit non-goals

- Herdr integration, executable/API/package/plugin dependency, installation, invocation, source reuse, or protocol emulation.
- A web dashboard, remote network service, database migration, or Hermes profile/gateway change.
- A terminal "done" signal that promotes task or track state.
- Direct task-file or code editing from the command-center session.
- A second scheduler, second event authority, or task state duplicated outside `.conductor/`.
- Automatic provider approval or unsafe prompt submission.
- A steady-state `capture-pane` polling loop for lane, blocked-prompt, result-artifact, or status detection.

## Functional Requirements

1. **Dedicated control target.** The command center has an explicit control-session target and rejects any target that is registered as a provider lane or assigned task worktree.
2. **Artifact-first authority.** Every displayed task/track state is traceable to a Conductor artifact; live pane observations are visibly marked as telemetry.
3. **Safe controls.** Lifecycle commands call existing Conductor APIs/commands and preserve all plan, worktree, diff-scope, verification, review-verdict, merge, and close gates.
4. **Task correlation.** A live observation belongs to a task only when task ID, stable lane target, and assigned workspace/worktree agree; otherwise it is unresolved.
5. **Hermes contract.** A JSON projection exposes a stable schema for command-center status, selected track, panes/views, action availability, artifact refs, and evidence freshness.
6. **Operator clarity.** Each blocked state includes the responsible task/lane, evidence reference, and the bounded operator action. Stale historical prompt text must not create an active blocker.
7. **Idempotent lifecycle.** Starting, refreshing, selecting a track, and rendering the control view are idempotent and never mutate task lifecycle state.
8. **No secret leakage.** Output excludes provider credentials, full pane history by default, and arbitrary paths outside the track/task artifact boundary.
9. **Event-first monitoring.** Runtime output, pane lifecycle, and `.conductor` artifact changes enter a durable, deduplicated event stream. Only the affected task/lane is reclassified; a full pane sweep is reserved for restart or a detected event-stream gap.

## Quality Attributes

| Attribute | Requirement |
|---|---|
| Correctness | Control view must not claim a task completed without the existing verification evidence. |
| Recoverability | Recreating the control session recovers from artifacts + fresh observations, with no manual state repair. |
| Isolation | Control session, worker lane sessions, and assigned worktrees are distinct and validated. |
| Auditability | Every action has command, actor, timestamp, target, outcome, and artifact/evidence refs. |
| Determinism | Same artifacts + same observations yield the same JSON/text projection. |
| Safety | Non-authoritative telemetry cannot dispatch, advance, merge, or close work by itself. |

## Architecture Decisions

1. **Terminal-first, not web-first.** The first standalone app is a local terminal command center because Conductor is local-first and tmux-backed.
2. **Conductor-native only.** Product concepts may be learned from Herdr, but the application uses only Conductor code/artifacts and tmux; no external runtime integration exists.
3. **Control/session separation.** Use a named control session (name chosen by implementation/configuration), while worker lanes retain project-specific sessions and formal worktree provenance.
4. **Deep Analysis is a pre-dispatch method.** For a new project or substantial task, Hermes invokes the current Deep Analysis workflow to produce/refresh a project-local feature spec and implementation plan. The command center records the resulting artifact references and approval status; it does not treat an LLM response as a dispatch authorization.
5. **Hermes is the conversation adapter.** Hermes sends operator intent to the command center, reads structured output, delivers Telegram updates, and owns browser/UI verification. The command center does not call Telegram or mutate Hermes configuration.

## Proposed Command Model

```text
conductor control start [--session <control-session>]
conductor control status [--track <track-id>] --format json|text
conductor control select --track <track-id>
conductor control action list --track <track-id> --json
conductor control inspect track|task|lane|evidence ... --json
conductor control refresh [--track <track-id>] --json
```

Commands that cause task lifecycle changes remain explicit delegations to established authority:

```text
conductor control action run --track <track-id> --name verify|advance|reconcile|loop
```

The action layer must expose whether the command is currently allowed; it must execute the same underlying Conductor policy checks rather than duplicating or weakening them.

## Delivery Sequence

1. **Phase A checkpoint — runtime contract:** complete and independently verify the active native tmux runtime track before consuming its internal interfaces.
2. **Phase B — event-assisted observation ledger:** persist normalized, task-correlated runtime and artifact events; use tmux control-mode/lifecycle events plus filesystem notifications rather than periodic pane capture.
3. **Phase C1 — read-only command center:** dedicated session, structured projection, view layout, session/workspace refusal rules, and recovery from artifacts.
4. **Phase C2 — guarded command actions:** expose existing Conductor lifecycle actions through the command center with audit records and policy parity tests.
5. **Phase C3 — Hermes interface:** document JSON contract, artifact references, Telegram summary mapping, and Hermes-owned UI/browser evidence workflow.
6. **Phase D/E — hardening and disposable proof:** material-change dedupe, provenance recovery, blocked-prompt handling, then a full Conductor-only end-to-end pilot.

## Acceptance Criteria

- [ ] The control application runs in a dedicated non-worker tmux session and rejects provider/worktree targets.
- [ ] It presents all active tracks and a selected track with state, DAG/task metadata, route/worktree provenance, verification evidence, and exact next action.
- [ ] Its JSON schema is documented and tested for Hermes consumption.
- [ ] It can be restarted without losing state or creating a new state authority.
- [ ] It clearly labels terminal observations as telemetry and records unresolved mismatches without task-state promotion.
- [ ] Every lifecycle action preserves existing Conductor gate behavior in parity tests.
- [ ] A blocked provider prompt is surfaced from a fresh output/lifecycle event with evidence and an operator action, without periodic pane polling or stale-scrollback false positives.
- [ ] A monitor test proves that idle lanes receive no recurring `capture-pane` calls; only pane/artifact events, startup reconciliation, explicit refresh, or event-gap recovery may cause a capture.
- [ ] A disposable pilot proves formal dispatch in a worker session, control-session visibility, result verification, advance, merge/close, and restart reconciliation.
- [ ] No Herdr integration or dependency is introduced.

## Open Questions

1. Should the first control UI be a fixed tmux pane layout, an interactive terminal UI, or both? **Default proposed answer:** fixed tmux layout plus deterministic CLI/JSON, with interactive TUI deferred.
2. What control session name should be reserved globally? **Default proposed answer:** configurable, with no hard-coded session assumption.
3. Which commands may `control action run` invoke without a new confirmation? **Default proposed answer:** read-only/refresh/reconcile always; dispatch/verify/advance/loop only for already approved tracks; merge/close follow existing autonomy policy and evidence gates.
4. Does “new project analysis” require a dedicated `conductor analyze` wrapper around Deep Analysis or an initial Hermes-owned adapter contract only? **Default proposed answer:** Hermes-owned adapter first; no embedded model API in Conductor.

## Approval Gate

Approved by Ahmed on 2026-07-19T12:01:50+04:00. The defaults recorded above are accepted for the initial implementation: fixed tmux layout plus deterministic CLI/JSON; configurable control-session name; existing action-autonomy policy; and a Hermes-owned Deep Analysis adapter without an embedded model API. Execute only in dependency order and retain Conductor's plan, worktree, verification, review, merge, and close gates.
