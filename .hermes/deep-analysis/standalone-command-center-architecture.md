# Conductor Standalone Command Center — Architecture Refinement

- **status:** draft
- **evidence_level:** inferred from inspected Conductor CLI/operator code and approved native-runtime direction
- **implementation_authorization:** authorized by Ahmed at 2026-07-19T12:01:50+04:00, dependency-gated
- **feature-spec:** `feature-spec-standalone-command-center.md`

## Current-State Evidence

| Existing surface | Local evidence | Reuse decision |
|---|---|---|
| Artifact-first state | `src/conductor/store.py`, track/task artifacts under `.conductor/` | Authoritative foundation; do not duplicate it. |
| Job orchestration | `dispatch.py`, `completion.py`, CLI `loop/verify/advance/close` | Preserve; command center delegates into these gates. |
| tmux lane safety | `src/conductor/lanes.py`, lane CLI commands | Preserve; control session must not be classified or used as a provider lane. |
| Blocked-prompt logic | `blocked_prompts.py`, `operator.py` | Reuse through normalized observations; avoid stale-scrollback false positives. |
| Operator projection | `src/conductor/operator.py` | Evolve into shared view-model layer for CLI, command center, and Hermes. |
| Hermes/Telegram boundary | README + operator output | Hermes remains caller/reporter; no Telegram/network implementation inside Conductor. |
| Active runtime direction | `conductor-native-runtime-direction.md` | Command center starts only after runtime contract + observation prerequisites. |

## Target Boundary

```text
┌──────────────────────────────── Hermes ─────────────────────────────────┐
│ operator intent • Deep Analysis invocation • Telegram rendering • UI QA  │
└──────────────────────────────────┬──────────────────────────────────────┘
                                   │ structured commands / artifact refs
┌──────────────────────────────────▼──────────────────────────────────────┐
│               Conductor standalone command center (control session)      │
│  View model: tracks • tasks • lanes • event observations • actions • evidence │
│  Command facade: inspect/select/refresh + guarded delegation             │
└──────────────────────────────────┬──────────────────────────────────────┘
                                   │ only Conductor-owned APIs/policies
┌──────────────────────────────────▼──────────────────────────────────────┐
│                 Conductor authoritative control plane                    │
│ .conductor artifacts • routing • dispatch • verify • advance • close     │
└───────────────┬─────────────────────────────────────────────┬────────────┘
                │ formal dispatch / telemetry                 │ artifacts
┌───────────────▼────────────────┐                 ┌───────────▼──────────┐
│ Worker tmux lane sessions      │                 │ Assigned worktrees    │
│ provider CLIs only             │                 │ source, tests, result │
└────────────────────────────────┘                 └──────────────────────┘
```

## State and Authority Model

| Data class | Writer | Authority | Consumer |
|---|---|---|---|
| Track/task/route/verification artifacts | Conductor | authoritative | command center, Hermes, workers |
| Runtime event/observation ledger | tmux control-mode + filesystem event bridge | telemetry/evidence only | command center, Hermes |
| Command-center view projection | command center | derived; rebuildable | Hermes/operator |
| Control action audit record | command center/Conductor | audit only; not task state | operator/reconciliation |
| Provider pane text | tmux/provider | non-authoritative hint | runtime adapter only |
| Telegram text | Hermes | delivery projection only | Ahmed |

## New-Project / New-Task Analysis Flow

```text
Ahmed request in Telegram
  → Hermes validates project binding and invokes Deep Analysis method
  → project-local feature spec (draft → approved) and implementation plan (not-authorized → authorized)
  → Hermes registers artifact references with a Conductor track
  → Conductor approval gate + formal dispatch to a worker lane session
  → command center projects progress/evidence/actions
  → Hermes verifies browser/UI where relevant and reports outcome
```

Hard rule: a Deep Analysis artifact explains and scopes a job. It does not authorize dispatch until its feature-spec and implementation-plan gates are satisfied.

## Event-Assisted Monitoring Contract

The command center replaces periodic pane polling with a durable event bridge:

```text
tmux control-mode pane output / lifecycle event ─┐
.conductor artifact filesystem event             ├→ append normalized event
explicit Hermes/operator refresh                 ┘   → correlate task/lane/worktree
                                                       → refresh affected projection
                                                       → schedule gated verify/reconcile work
```

- A pane capture is triggered by a relevant event, not a timer.
- The bridge deduplicates source event IDs/content hashes and persists a cursor/checkpoint.
- Provider prompt classification runs only on fresh pane-output events.
- A missing cursor, tmux control-client disconnect, filesystem watcher overflow, or restart produces `event_stream_gap`; it triggers one bounded reconciliation sweep with evidence.
- Reconciliation remains non-authoritative: it can discover evidence or schedule verification, but it cannot advance task state.

## Required Internal Interfaces

```python
class ControlViewService:
    def overview(self) -> ControlOverview: ...
    def track_view(self, track_id: str) -> ControlTrackView: ...
    def action_availability(self, track_id: str) -> list[ControlAction]: ...

class ControlSessionGuard:
    def validate_control_target(self, target: str) -> ControlTarget: ...
    def reject_worker_lane_or_worktree(self, target: str) -> None: ...

class ControlActionFacade:
    def inspect(self, request: ControlRequest) -> ControlResponse: ...
    def run_guarded(self, request: ControlActionRequest) -> ControlActionResult: ...
```

These are Conductor-owned boundaries, not provider or Herdr abstractions. `ControlActionFacade` must call the existing command/service policy logic, not reconstruct lifecycle rules in a parallel implementation.

## View Model Requirements

The initial JSON projection must contain:

```json
{
  "schema_version": 1,
  "generated_at": "ISO-8601",
  "control_session": {"target": "...", "state": "ready|absent|invalid"},
  "tracks": [{"track_id": "...", "signal": "...", "counts": {}}],
  "selected_track": {
    "tasks": [],
    "lanes": [],
    "observations": [],
    "blocked_prompts": [],
    "actions": [],
    "artifact_refs": []
  },
  "evidence_freshness": {"artifacts_at": "...", "observations_at": "..."}
}
```

Each action contains its command name, whether it is allowed, refusal reason when blocked, policy source, and target artifact refs. No output may contain a provider credential or unbounded pane transcript.

## Risks / Mitigations

| Risk | Impact | Mitigation |
|---|---|---|
| Parallel authority in a new UI | false task advancement | derived projection only; action delegation to existing policy tests |
| Control session accidentally a worker lane | unsafe delivery/workspace contamination | session guard + negative tests before start |
| Stale pane history looks blocked | loops waste time | recent-tail capture hash, explicit freshness, observation ledger |
| Timer-driven pane polling | unnecessary load, stale-state loops, slow response | tmux control-mode + filesystem event bridge; bounded recovery reconciliation only |
| Main-checkout WIP conflicts with active Phase A | incorrect attribution and merge risk | new worktree only after Phase A checkpoint; record baseline snapshot |
| Embedded LLM/Deep Analysis dependency creates a hidden service | nondeterminism, secret surface | Hermes adapter calls the existing method; Conductor stores only artifact refs |
| Scope turns into a web dashboard | avoidable service complexity | terminal-first non-goal; separate feature spec required for web UI |

## Build-Readiness Assessment

- **Ready now:** feature refinement and design review.
- **Blocked dependency:** the active Phase A native runtime implementation remains unverified, while the command center depends on Phase A and Phase B interfaces.
- **Authorized next actions:** recover and verify Phase A; create the concrete Phase B event-assisted monitoring plan/track; dispatch Phase B only after Phase A verification and Phase B plan approval.
