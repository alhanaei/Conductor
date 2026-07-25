# Feature Spec — Conductor Native tmux Runtime

- **status:** approved
- **approved_by:** Ahmed
- **approved_at:** 2026-07-18T12:36:08Z
- **implementation authorization:** authorized for Phase A; later phases require their preceding checkpoint to pass
- **source analysis:** `conductor-native-runtime-direction.md`; `herdr-inspiration-native-gap-analysis.md`

## Problem

Conductor has safe tmux lane controls, task artifacts, worktree records, events, blocked-prompt detection, and verification gates, but lacks a Conductor-owned runtime contract and task-correlated observation model. Stale lane projections can disagree with live panes and task worktree provenance.

## Users

- Ahmed: local operator supervising Conductor tracks through tmux and Telegram.
- Hermes: independent verifier and operator reporter.
- Coding workers: provider CLIs running in formally assigned Conductor lanes.

## Scope

Phase A only:

1. Extract a Conductor-native internal `LaneRuntime` contract and behaviorally identical `TmuxLaneRuntime` wrapper over `LaneAdapter`.
2. Add additive runtime metadata with legacy deserialization defaults.
3. Add TDD contract, safe-refusal, and persistence compatibility tests.
4. Keep current tmux CLI/JSON behavior compatible.

## Non-Goals

- Herdr integration, installation, invocation, dependency, source reuse, or API/client code.
- A generic external runtime/plugin system.
- A control panel, observation ledger, monitor redesign, or live profile changes; those are later gated phases.
- Altering task/verification/merge authority.

## Acceptance Criteria

1. All current safe submission semantics remain unchanged: only `provider_ready` accepts a task artifact reference.
2. `shell`, `busy`, `blocked_prompt`, `absent`, and `unknown` states refuse delivery.
3. Existing persisted lane/dispatch records that lack runtime fields load as tmux with empty adapter metadata.
4. `TmuxLaneRuntime` normalizes existing status/capture/delivery behavior without changing the public lane CLI contract.
5. New behavior is developed test-first and is covered by targeted tests.
6. The full Conductor suite and `git diff --check` pass.
7. No protected main-checkout WIP is modified or attributed to this task.

## Constraints

- Work must use a formally allocated Conductor worktree.
- Claude Fable is the selected implementation provider for this phase.
- A terminal signal remains non-authoritative; Conductor verification remains the sole promotion gate.
- Any mismatch between assigned worktree and actual edits is a blocker, not a reconciled success.

## Open Questions

- None block Phase A. The native observation ledger, panel, and recovery phases start only after Phase A verification.
