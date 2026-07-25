# Herdr Inspiration Review → Native Conductor Implementation Gap Analysis

- **status:** reviewed
- **date:** 2026-07-18
- **decision:** implement Conductor-native capabilities inspired by observable Herdr product concepts; do not integrate, install, invoke, depend on, or copy Herdr.
- **source boundary:** Herdr capability claims in the superseded integration plan are externally sourced and were not live-verified in this review because the configured web search/extract backend returned authentication failures. Conductor code claims below were inspected locally.

## 1. Authority Boundary (retained)

```text
Conductor artifacts + verification are the only authority for task/track state.
tmux observations are telemetry/hints.
A terminal "done" or idle pane can trigger inspection only; it cannot advance a task.
```

This aligns with current Conductor behavior: task verification uses task artifacts, verification commands, diff integrity, and valid status enums (`src/conductor/completion.py`; `src/conductor/models.py`).

## 2. Current Capability Inventory

| Capability | Current Conductor evidence | Gap |
|---|---|---|
| Safe tmux delivery | `LaneAdapter.submit()` refuses non-`provider_ready` states (`src/conductor/lanes.py:559+`) | Keep; expose through a runtime-neutral contract |
| Lane inspection/capture | `LaneAdapter.status()` and `capture()` (`lanes.py:515+`) | Output is a mutable lane projection, not a normalized observation ledger |
| Lane lifecycle events | Global append-only `events.jsonl`; per-lane last event (`store.py:280+`, `lanes.py`) | No task-correlated runtime observation/event model or replayable projection |
| Worktree assignment | Dispatch records workspace/worktree fields (`dispatch.py:477+`; `worktree.py`) | Runtime capture is not bound/reconciled against those paths |
| Blocked prompt detection | `blocked_prompts.py`; operator summary emits exact operator action (`operator.py:175+`) | Improve stale-scrollback resistance, capture provenance, and material-change dedupe |
| Operator summaries/heartbeats | `operator.py` has summaries, notifications, heartbeat and loop guidance | No terminal control-panel projection/layout |
| Reconciliation | `completion.py`, `integrity.py`, `operator.py` reconcile task artifacts/diffs | Does not reconcile task identity against live tmux pane/workspace evidence |
| Method/DoD gates | planner/dispatch/completion create and enforce method contracts, DoD, quality gates | Already sufficient; runtime work must not weaken these gates |

## 3. Native Features Worth Implementing

### A. Runtime contract — implement first

Create `src/conductor/runtime/` as an internal Conductor-owned interface:

- `LaneBinding`: stable `lane_target`, provider, runtime=`tmux`, assigned workspace/worktree, opaque adapter reference.
- `RuntimeObservation`: observed timestamp, normalized lane state, evidence reference, capture identity, reason, confidence.
- `DeliveryReceipt`: task artifact reference, state before delivery, timestamp, lane binding.
- `TmuxLaneRuntime`: delegates to the existing `LaneAdapter`; preserves its safe refusal behavior exactly.

**Do not add a Herdr adapter or generic external-runtime plug-in path.** The abstraction is for Conductor code locality and future internal adapters only.

### B. Runtime observation ledger

Add durable, additive evidence:

```text
.conductor/runtime/
  bindings/<track_id>/<task_id>.json
  observations/<track_id>/<task_id>.jsonl
  unresolved/<event_id>.json
```

Correlation must require all applicable signals:

```text
recorded task ID + stable lane_target + assigned workspace/worktree
```

If they do not agree, record `unresolved_event`; never infer ownership from a provider name, pane title, or stale scrollback.

### C. Terminal operator panel

Implement a Conductor-native tmux projection, not a second state store:

- overview: `conductor operator summary --format json` projection;
- track pane: task/method/provider/worktree/verification state;
- lane pane: current capture plus the most recent normalized observation;
- events pane: runtime observations and Conductor message-bus projection.

Panel creation must be explicit and idempotent. Pane operations must not mutate task state.

### D. Monitor and recovery improvements

Build on the existing loop and blocked prompt helper:

- notify only on material state changes;
- retain recent-tail semantics and capture evidence hashes to prevent stale prompt false positives;
- on restart: load `.conductor` artifacts first, then compare live pane state;
- classify a mismatch as `workspace_provenance_mismatch` or `unresolved_event`, not a silently recovered ownership assignment;
- preserve poll/reconcile as the final fallback.

### E. Controlled Conductor-only pilot

Use one disposable repository, one track, one Fable lane, and one explicit worktree. Prove:

1. provider-ready artifact delivery;
2. busy and approval-prompt refusal;
3. result artifact then independent Conductor verification;
4. restart/reconcile from artifacts;
5. wrong-worktree detection;
6. panel evidence compared against task artifacts;
7. merge/close only after all gates pass.

## 4. Explicitly Do Not Implement

- Herdr binary, CLI, package, source, plugin, socket API, event subscription, service, or configuration.
- A terminal `done` → task completion bridge.
- Automatic fallback/rerouting based only on provider name or pane title.
- A web dashboard, remote control plane, or Hermes profile change as part of this work.
- Direct source reuse or copy/paste from Herdr.

## 5. Dependency Order

```text
A: tmux runtime contract + tests
  ↓
B: task-correlated observation ledger + replay tests
  ↓
C: explicit, read-only terminal panel
  ↓
D: monitor/recovery/provenance hardening
  ↓
E: disposable end-to-end proof
```

## 6. First Executable Slice

A new, clean Conductor track should implement only **A**:

- protect existing main-checkout WIP in `CONDUCTOR_USER_GUIDE.md`, `src/conductor/lanes.py`, and `tests/test_lane_launch.py`;
- use a formally assigned worktree;
- retain byte-compatible existing lane CLI behavior;
- add contract, legacy persistence, and safe-refusal tests;
- run relevant suites plus the full suite and `git diff --check`.

Do not resume the superseded `track_7a4f4081`; its implementation task has an unresolved worktree-provenance mismatch.
