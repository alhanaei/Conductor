# Feature Spec — Optional Herdr Runtime for Conductor

- **status:** superseded
- **superseded_by:** `conductor-native-runtime-direction.md`
- **superseded_at:** 2026-07-18
- **reason:** Conductor will independently implement the useful runtime-control ideas without integrating, installing, invoking, or copying Herdr.
- **implementation authorization:** revoked for this Herdr-integration feature spec

## Problem

Conductor provides artifact-driven task governance, but its current tmux lane runtime has limited structured runtime telemetry and no rich terminal control-panel experience. An operator needs a persistent, project/track/task-correlated view of real agent terminals, better lifecycle visibility, and safer recovery without weakening Conductor verification gates.

## Users

- **Primary operator:** Ahmed, supervising multi-agent Conductor tracks locally and remotely.
- **Secondary operator surface:** Hermes, which reads Conductor artifacts, performs verification, and reports concise status through Telegram.
- **Workers:** coding-agent CLIs in a lane; workers are not decision authorities for task completion.

## Scope

- Add a runtime-neutral lane contract with tmux preserved as the baseline adapter.
- Add optional Herdr observation, a terminal control panel, and eventually Herdr-backed lane delivery.
- Record durable, additive mappings between Conductor task/lane identity and Herdr runtime identity.
- Use Herdr events/native provider hooks as telemetry that wakes Conductor monitoring.
- Preserve Conductor artifacts, quality gates, verification, merge, close, and reconciliation as semantic authority.

## Non-Goals

- Replace Conductor with Herdr.
- Replace `.conductor/` durable task state with Herdr persistence.
- Let Herdr lifecycle state directly advance a Conductor task or track.
- Automatically install or configure Herdr/Hermes plugins in the live coding profile.
- Deliver a web dashboard or cloud service.

## Acceptance Criteria

1. Existing tmux lane behavior remains compatible and passes its present safety/regression suite after extraction behind a common runtime contract.
2. Herdr-backed observations are stored as additive evidence and can be correlated to a task only through explicit runtime binding, stable lane target, and matching workspace/worktree.
3. Herdr `done`/`idle` can at most trigger a Conductor verification tick; it cannot make a task merge-ready or complete.
4. A terminal control panel shows real agent panes grouped by project/track/task, while Conductor artifacts remain the visible state source.
5. Herdr lane submission preserves artifact-reference-only delivery and refuses non-ready/bare-shell/ambiguous states.
6. Event subscription loss, runtime restart, or unknown event attribution leaves Conductor recoverable through existing artifacts and reconciliation.
7. A disposable end-to-end pilot proves dispatch, result, Conductor verification, restart/reconcile, and terminal-panel evidence before wider runtime selection is enabled.

## Open Questions

- Which provider is the first pilot lane? Proposed: Claude.
- Is Herdr selected per task, per track, or per project? Proposed: explicit pilot-track selection.
- Should Herdr's Hermes plugin be evaluated after base runtime parity? Proposed: defer.
- What Herdr version/API schema will be supported? Requires Phase 0 evidence.

## Approval Gate

Only setting `status: approved` with Ahmed as `approved_by` unblocks creation of an executable Conductor plan/track for this feature. Until then, this feature remains design-only.
