# Conductor × Herdr Runtime Integration — Design and Implementation Plan

> **Status:** approved for phased execution; Phase 0 and Phase 1 are authorized first.
>
> **Feature-spec gate:** `approved` by Ahmed on 2026-07-17. Subsequent phases remain separately gated by the completion checkpoints in this plan.
>
> **Implementation authorization**: `authorized-for-phases-0-and-1`
>
> **Definition of Done:** Any later execution handoff must link the Conductor track's generated `definition_of_done.md` and retain Conductor's independent verification/merge/close gates.

## 1. Decision Summary

### Goal

Add an optional **Herdr lane runtime** to Conductor so an operator has a persistent terminal control panel for all Conductor sessions, while preserving Conductor as the authoritative delivery control plane for plans, task DAGs, quality gates, artifacts, verification, merge approval, and track closure.

### Product position

```text
Conductor owns semantic delivery state.
Herdr owns live terminal runtime state.
Hermes owns final browser/UI and operator-facing verification.
```

Herdr is not a replacement for Conductor or its `.conductor/` artifacts. It is an additional implementation of the lane-runtime boundary currently backed by tmux.

### User outcomes

1. An operator can see each Conductor lane as a real agent terminal, grouped by project/track/task and rendered in a terminal control-panel style.
2. Conductor can receive prompt/provider lifecycle changes promptly through a runtime event bridge instead of relying only on periodic pane capture.
3. A Conductor task may bind to an isolated Git worktree and a matching Herdr workspace/pane without changing the task/verification contract.
4. Provider-native hooks may enrich lane telemetry and session recovery where Herdr supports them, but never override Conductor task state or verification.
5. tmux remains a production fallback until a Herdr pilot proves contract parity and recovery safety.

## 2. Scope and Boundaries

### In scope

- A runtime-neutral lane interface in Conductor.
- Existing tmux behavior preserved behind `TmuxLaneRuntime`.
- A Herdr-backed observer and eventually a `HerdrLaneRuntime`.
- Runtime identity persistence: session/workspace/tab/pane/agent identifiers.
- Event-assisted monitor wakeups with durable event reconciliation.
- Terminal control-panel layouts, project/track/task labels, and operator linking.
- Worktree-to-workspace mapping.
- Contract tests and a disposable local integration harness.

### Explicitly out of scope

- Replacing `.conductor/` with Herdr session persistence.
- Letting Herdr `done` imply Conductor `ready_for_merge`, `complete`, or `verified_complete`.
- Rewriting Conductor planning, methods, DoD, quality gates, message bus, verification, or merge/close gates.
- Adding a web dashboard, cloud control plane, or network service.
- Automatic modification of `~/.hermes/config.yaml` or installation of Herdr's Hermes integration.
- Automatic migration of existing tmux sessions.
- Direct reuse of Herdr source code; architecture/interface learning only pending licensing review.

## 3. Evidence Base

### Conductor: verified current implementation

| Claim | Evidence |
|---|---|
| Conductor's product is a tmux-backed multi-agent control plane with a unified messaging/state layer. | `README.md:1-10` |
| Lane state is currently `absent`, `shell`, `provider_ready`, `busy`, `blocked_prompt`, or `unknown`. | `src/conductor/models.py:113-119`; `src/conductor/lanes.py:299-338` |
| `LaneAdapter` is a tmux-specific seam that persists lane records and gates prompt submission on `provider_ready`. | `src/conductor/lanes.py:1-14`, `361-400`; `tests/test_lanes.py:223-260` |
| Dispatch already owns task artifacts, lane routing, worktree allocation, safe submission, message-bus notifications, and dispatch records. | `src/conductor/dispatch.py:253-513` |
| Worktrees are planned by default and only created after explicit opt-in. | `src/conductor/worktree.py:1-11`, `123-161` |
| Worker completion is intentionally non-authoritative; Conductor independently verifies artifacts and configured commands. | `src/conductor/completion.py:1-22`, `182-247` |
| Conductor's message bus is append-only JSONL plus event files and rebuildable worker-status projections. | `src/conductor/message_bus.py:1-14`, `47-139` |

### Herdr: externally sourced, not installed or runtime-tested in this plan

| Capability | Source |
|---|---|
| Persistent workspace → tab → pane → agent terminal model with semantic agent state. | [Herdr Concepts](https://herdr.dev/docs/concepts/) |
| Local socket API/CLI for panes, agents, layouts, events, waits, worktrees, and plugins. | [Herdr Socket API](https://herdr.dev/docs/socket-api/) |
| Provider integrations plus an optional Hermes integration reporting lifecycle/tool/approval/session state. | [Herdr Integrations](https://herdr.dev/docs/integrations/) |
| Detach/reattach, named sessions, remote attach, and direct terminal attach. | [Herdr Persistence and Remote Access](https://herdr.dev/docs/persistence-remote/) |
| Plugin extension surface. | [Herdr Plugins](https://herdr.dev/docs/plugins/) |
| License is dual: AGPL-3.0-or-later OSS path or commercial license. | [Herdr README](https://github.com/ogulcancelik/herdr) |

### Existing constraints

- `README.md:29-45`: Conductor verification, merge approval, and close remain independent gates.
- `src/conductor/dispatch.py:446-470`: Conductor must never submit into an unready lane.
- `tests/test_lanes.py:142-179`: stale prompt text and MCP authentication warnings already have observed classifier pitfalls; a runtime bridge must not regress these cases.
- `CONDUCTOR_USER_GUIDE.md` and the active worktree contain local WIP. This plan must be executed in a clean, approved track/worktree rather than by mixing runtime work into unrelated changes.

## 4. Target Architecture

```text
                          Operator
           Telegram / CLI / local terminal / SSH
                              |
                              v
+-----------------------------------------------------------+
| Conductor semantic control plane                          |
|  track, DAG, method contracts, DoD, task artifacts        |
|  routing policy, verification, merge/close, reconciliation|
+-------------------------+---------------------------------+
                          |
                          | Runtime-neutral LaneRuntime API
                          v
+-------------------------+---------------------------------+
| Runtime adapters                                         |
|  TmuxLaneRuntime (existing baseline)                     |
|  HerdrLaneRuntime (new optional adapter)                 |
+------------+---------------------------+------------------+
             |                           |
             v                           v
       tmux session/window       Herdr session/workspace/tab/pane/agent
             |                           |
             +----------- real provider CLIs --------------+
                         Claude / Codex / Gemini / Grok

                     Herdr runtime events
                              |
                              v
+-----------------------------------------------------------+
| Conductor runtime event bridge                            |
| dedupe, append durable observation, trigger monitor tick  |
| never advances task state without artifact verification    |
+-----------------------------------------------------------+
```

### Authority model

| Question | Authoritative owner | Other inputs are only |
|---|---|---|
| Is the terminal process alive or provider asking for input? | Herdr runtime when selected; tmux capture fallback | telemetry/hints |
| Is a task dispatched, blocked, verified, merge-ready, complete? | Conductor artifacts + state machine | runtime correlation signals |
| Does a worker claim completion? | Worker result/message | unverified claim |
| Does a visible UI meet acceptance criteria? | Hermes browser verification | worker-reported evidence |
| Is a track finalizable? | Conductor verify/advance/merge/close chain | never Herdr agent state |

### Required state mapping

Do not collapse the two domains:

```text
Herdr agent lifecycle                  Conductor consequence
--------------------------------------------------------------------
working                                update runtime observation only
blocked                                record runtime blocker candidate; inspect task/lane evidence
idle / done                            emit worker-terminal signal; schedule artifact verification
unknown                                retain/retry observation; do not guess a task blocker
session/pane disappears                update lane runtime; assess stale/blocked risk
```

The only allowed automatic transition triggered by a Herdr `done` signal is:

```text
schedule `verify_ready_results` / monitor reconciliation
```

It must not modify a task into `ready_for_merge` or `complete` directly.

## 5. Contract-First Runtime Interface

### 5.1 Stable Conductor types

Create a runtime-neutral public interface before any Herdr-specific implementation. Proposed types:

```python
class RuntimeKind(str, Enum):
    TMUX = "tmux"
    HERDR = "herdr"

class RuntimeAvailability(str, Enum):
    AVAILABLE = "available"
    UNAVAILABLE = "unavailable"
    DEGRADED = "degraded"

@dataclass(frozen=True)
class LaneBinding:
    lane_target: str                 # stable operator label: <project>:<provider[-n]>
    runtime: RuntimeKind
    runtime_ref: dict[str, str]      # adapter-owned opaque stable ids
    workspace_path: str | None
    provider: str | None

@dataclass(frozen=True)
class RuntimeObservation:
    observed_at: str
    lane_target: str
    runtime: RuntimeKind
    availability: RuntimeAvailability
    state: str                       # normalized runtime state; not TaskState
    reason: str | None
    transcript_ref: str | None
    native_agent_id: str | None
    native_session_id: str | None
    source_event_id: str | None
    raw_ref: str | None
```

### 5.2 Operations

```python
class LaneRuntime(Protocol):
    def ensure(self, request: EnsureLaneRequest) -> LaneBinding: ...
    def inspect(self, binding: LaneBinding) -> RuntimeObservation: ...
    def submit_artifact_reference(self, binding: LaneBinding, task_ref: Path) -> DeliveryReceipt: ...
    def capture(self, binding: LaneBinding, lines: int = 200) -> CaptureResult: ...
    def followup_artifact_reference(self, binding: LaneBinding, followup_ref: Path) -> DeliveryReceipt: ...
    def subscribe(self, bindings: Iterable[LaneBinding]) -> EventSubscription: ...
    def restore_hint(self, binding: LaneBinding) -> RestorePlan: ...
```

**Compatibility rule:** all consumers outside the runtime package use `LaneBinding` and `RuntimeObservation`; only adapters read/write `runtime_ref` fields.

### 5.3 Failure contract

- `ensure`: returns an unavailable/degraded result with evidence; does not silently create a fallback tmux lane when Herdr was explicitly requested.
- `submit_artifact_reference`: refuses non-ready/untrusted runtime input and returns a structured reason; never pastes task bodies.
- `subscribe`: optional best-effort enhancement. Its absence or failure may not stop Conductor's artifact-based monitor.
- malformed/unknown runtime event: append `runtime_event_unresolved`, preserve raw evidence reference, do not attribute it to a task by provider name alone.
- runtime identity changed after recovery: mark binding `degraded`, request correlation/reconciliation; never silently attach the new pane to an existing active task.

### 5.4 Versioning rule

- The initial runtime contract is internal `v1` but has contract tests.
- All runtime metadata is additive in persistence. Existing `DispatchRecord` files must deserialize without Herdr fields.
- Existing tmux CLI commands and JSON response fields remain byte-compatible where practical; add a `runtime` field rather than changing current `lane_target` semantics.

## 6. Phased Delivery Plan

## Phase 0 — Decision lock and read-only compatibility spike

**Purpose:** Validate Herdr availability and API shape without changing Conductor dispatch behavior or Hermes configuration.

### Tasks

1. Create a dedicated Conductor track/spec for this work; keep its plan approval and implementation authorization separate from this document.
2. Install/run Herdr only in a disposable sandbox or a non-production named session after approval; record binary version, `herdr api schema --json`, supported provider integrations, and platform constraints.
3. Confirm whether the installed Herdr version exposes every required operation: workspace create/list, pane run/read/send, agent state, `events.subscribe`/`events.wait`, worktree API, session snapshot, and restore capability.
4. Create a minimal probe script outside `src/conductor/` that only reads a Herdr snapshot and prints normalized observations; no writes to `.conductor/`.
5. Run the probe against a disposable Claude/Codex terminal and record observed state transitions, including provider-ready, busy, a real approval prompt, done/idle, and stale transcript conditions.
6. Perform a licensing decision: architecture-only integration vs. commercial arrangement if implementation reuse is ever proposed.

### Acceptance criteria

- A pinned Herdr version and socket schema capture are stored as evidence.
- Required operations are classified as verified / unavailable / version-dependent.
- The probe does not mutate Conductor state, provider configuration, or Hermes profiles.
- A decision record selects `proceed`, `defer`, or `reject` based on concrete capability gaps.

### Verification

```bash
cd /home/alhanaei/projects/Conductor
python -m pytest -q
# In approved disposable Herdr environment only:
herdr --version
herdr api schema --json > /tmp/herdr-api-schema.json
herdr api snapshot
```

**Checkpoint:** Do not create a runtime adapter unless the probe proves a stable local API path and native state signals are materially better than current tmux capture for the selected providers.

---

## Phase 1 — Extract the tmux runtime behind a stable interface

**Purpose:** Make runtime selection explicit without functional change.

### Planned file changes

| Action | Path | Responsibility |
|---|---|---|
| Create | `src/conductor/runtime/__init__.py` | public runtime types/protocol and adapter factory |
| Create | `src/conductor/runtime/base.py` | `LaneRuntime`, binding, observation, delivery, error contracts |
| Create | `src/conductor/runtime/tmux.py` | adapter wrapping the current tmux operations |
| Modify | `src/conductor/lanes.py` | retain compatibility facade or move pure provider classifier/types only |
| Modify | `src/conductor/dispatch.py` | depend on `LaneRuntime`, preserve scheduling/ownership policy |
| Modify | `src/conductor/completion.py` | receive runtime observations only through the interface |
| Modify | `src/conductor/models.py` | additive runtime fields on dispatch/lane records |
| Modify | `src/conductor/store.py` | additive persistence projection helpers if required |
| Create | `tests/test_runtime_contract.py` | shared adapter contract suite |
| Create | `tests/test_runtime_tmux.py` | baseline parity suite |
| Modify | existing `tests/test_lanes.py` | preserve legacy command behavior and classifier regression cases |

### Required behavior

- `TmuxLaneRuntime` delegates to the existing classifier and existing safe artifact-reference submission behavior.
- A `runtime: tmux` field is persisted additively on new dispatch records.
- Existing persisted records without the field load as tmux by default.
- The current CLI is unchanged unless an explicit optional `--runtime tmux|herdr` is added later.
- Lane pool allocation continues to use stable `lane_target`; it must not depend on a tmux pane ID.

### TDD sequence

1. Add contract fixtures for ready/busy/blocked/shell/absent runtime outcomes.
2. Add a failing test proving a legacy `LaneAdapter.status()` result normalizes into `RuntimeObservation` with exact state semantics.
3. Implement the protocol and tmux wrapper.
4. Add dispatch serialization tests proving two active task records still reserve the same stable lane targets.
5. Add persistence migration tests for records without runtime metadata.
6. Run full existing lane/dispatch/completion tests before proceeding.

### Acceptance criteria

- No behavior regression in current tmux commands or safe submission checks.
- No existing `.conductor` record is invalidated.
- Tests prove bare shell and blocked prompt still refuse task submission.
- `LaneAdapter` becomes a compatibility facade or is removed only after all callers use the contract.

### Verification

```bash
cd /home/alhanaei/projects/Conductor
python -m pytest tests/test_lanes.py tests/test_dispatch.py tests/test_completion.py tests/test_runtime_contract.py tests/test_runtime_tmux.py -q
python -m pytest -q
git diff --check
```

**Checkpoint:** Only a behaviorally identical tmux implementation may pass this phase.

---

## Phase 2 — Herdr read-only observer adapter

**Purpose:** Integrate Herdr telemetry without using it to create lanes or submit work.

### Planned file changes

| Action | Path | Responsibility |
|---|---|---|
| Create | `src/conductor/runtime/herdr_client.py` | narrow CLI/socket client, schema validation, no policy |
| Create | `src/conductor/runtime/herdr_observer.py` | snapshot/event-to-observation translation |
| Create | `src/conductor/runtime/herdr.py` | read-only `HerdrLaneRuntime` methods; mutation methods return unsupported |
| Create | `src/conductor/runtime/event_bridge.py` | dedupe/correlation/persistence of runtime observations |
| Modify | `src/conductor/models.py` | additive `RuntimeObservationRecord` or equivalent schema |
| Modify | `src/conductor/store.py` | append-only runtime observation/event paths |
| Modify | `src/conductor/operator.py` | optional compact runtime section, clearly labeled telemetry |
| Create | `tests/test_runtime_herdr_client.py` | client response/error fixtures |
| Create | `tests/test_runtime_herdr_observer.py` | event translation and correlation tests |
| Create | `tests/fixtures/herdr/` | captured schema/snapshot/event fixtures |

### Correlation rule

A Herdr event may be attached to a Conductor task only if all required correlation checks pass:

1. `runtime_ref` identifies the same Herdr pane or agent recorded in the dispatch record; and
2. `lane_target` or explicit binding agrees; and
3. observed workspace path equals the task workspace/worktree path when one is assigned.

Otherwise append a track- or project-scoped `runtime_event_unresolved` record. Never infer task ownership from only `claude`, `codex`, or a pane title.

### Acceptance criteria

- `session.snapshot` can be normalized into observations using recorded fixtures.
- Event processing is idempotent by source event ID/content hash.
- Unknown or mismatched events are visible as unresolved instead of silently misattributed.
- No Conductor `TaskState`, verification status, or merge eligibility changes as a result of observer events.

### Verification

```bash
cd /home/alhanaei/projects/Conductor
python -m pytest tests/test_runtime_herdr_client.py tests/test_runtime_herdr_observer.py tests/test_runtime_contract.py -q
python -m pytest -q
```

**Checkpoint:** Run a live disposable observer comparison for one provider. Compare the latest Herdr observation, tmux classifier result, task result artifact state, and actual pane state. Document every disagreement before moving to runtime mutation.

---

## Phase 3 — Terminal control-panel layout and operator visibility

**Purpose:** Deliver the user-visible benefit without making Herdr a source of task truth.

### Control-panel design

```text
Herdr named session: conductor
  Workspace: <project>
    Tab: overview
      Pane: conductor operator/status (read-only)
      Pane: active task / track summary (read-only)
    Tab: <track_id>
      Pane: <task-id> • <provider> • <worktree>
      Pane: tests/runtime (optional, task-owned)
      Pane: review/verifier (optional, operator-owned)
    Tab: events
      Pane: runtime event bridge tail
      Pane: Conductor message-bus projection
```

### Planned file changes

| Action | Path | Responsibility |
|---|---|---|
| Create | `src/conductor/runtime/layouts.py` | declarative Herdr layout generation from track/dispatch records |
| Create | `src/conductor/runtime/control_panel.py` | idempotent workspace/tab/pane reconciliation |
| Modify | `src/conductor/operator.py` | render stable links/identifiers and a compact runtime status section |
| Modify | `src/conductor/cli.py` | add explicit opt-in control-panel commands |
| Create | `tests/test_control_panel.py` | pure declarative-layout and idempotence tests |
| Create | `docs/herdr-runtime.md` | operator instructions, recovery, limitations |

### Rules

- Conductor creates layouts only on explicit command or explicit plan policy; no surprise panes.
- A control panel must use project/track/task metadata to label panes, never scrape provider transcript for identity.
- Closing/rearranging an operator pane must not modify Conductor task state.
- The overview pane is a projection of `conductor operator summary --format json`, not a second state store.
- Telegram remains compact; it should link/report `lane_target`, runtime kind, and concise blocker/verification status, not dump terminal output.

### Acceptance criteria

- Given a recorded track, generated layout has deterministic labels and worktree cwd values.
- Re-running the command does not duplicate panes or create additional lanes.
- A terminal control panel displays active sessions and correlates each pane to a track/task or marks it unassigned.
- Terminal layout operations cannot change a task state.

### Verification

```bash
cd /home/alhanaei/projects/Conductor
python -m pytest tests/test_control_panel.py tests/test_runtime_herdr_observer.py -q
python -m pytest -q
# Approved disposable runtime smoke:
python -m conductor runtime panel --track <sandbox-track> --runtime herdr --json
python -m conductor runtime status --track <sandbox-track> --json
```

**Checkpoint:** Hermes captures a screenshot/readback from the real terminal control panel and verifies the displayed state against `.conductor` artifacts. It must report mismatches rather than treating the visual panel as proof.

---

## Phase 4 — Herdr lane creation and artifact-reference delivery

**Purpose:** Allow one explicitly selected lane to run under Herdr while preserving the same submission safeguards as tmux.

### Planned file changes

| Action | Path | Responsibility |
|---|---|---|
| Modify | `src/conductor/runtime/herdr.py` | implement `ensure`, `capture`, and safe artifact-reference submission |
| Modify | `src/conductor/runtime/herdr_client.py` | explicit pane/agent creation and input operations |
| Modify | `src/conductor/dispatch.py` | select runtime through approved configuration/CLI parameter |
| Modify | `src/conductor/lanes.py` | remove runtime-specific orchestration from shared call sites only after parity |
| Modify | `src/conductor/models.py` | persist binding and delivery receipt fields additively |
| Modify | `src/conductor/doctor.py` | report runtime availability/version/socket access without starting services |
| Create | `tests/test_runtime_herdr_delivery.py` | refuses unready / sends artifact reference / records receipt |
| Create | `tests/test_runtime_parity.py` | same behavior contract for tmux and Herdr adapters |

### Required submission sequence

```text
approved Conductor task
  → task.md written by Conductor
  → Herdr workspace/pane binding created or reconciled
  → provider readiness obtained from Herdr native telemetry plus recent pane evidence
  → short instruction references task.md
  → actual provider activity observed
  → delivery receipt persisted
```

### Non-negotiable safeguards

- Do not submit into a bare shell merely because a Herdr pane exists.
- Do not mistake prompt echo for delivery/completion.
- Do not send task body text if the artifact reference can be sent.
- Do not use Herdr `done` as terminal verification.
- If a provider prompt/onboarding/authentication state is unclear, report `blocked_prompt` or `runtime_unknown` and require operator action.
- If Herdr is unavailable, fail the explicit Herdr request safely; do not silently submit via tmux.

### Acceptance criteria

- A disposable approved task can be submitted to exactly one Herdr-backed provider pane.
- The persisted binding allows the same pane/agent to be inspected after a Conductor process restart.
- All non-ready state tests reject delivery.
- Tmux and Herdr adapters pass the common contract suite.

### Verification

```bash
cd /home/alhanaei/projects/Conductor
python -m pytest tests/test_runtime_contract.py tests/test_runtime_parity.py tests/test_runtime_herdr_delivery.py -q
python -m pytest -q
# Live, approved sandbox only:
python -m conductor lane ensure --target conductor-test:claude --runtime herdr --launch --json
python -m conductor lane submit --target conductor-test:claude --runtime herdr --task-file <artifact> --json
python -m conductor lane capture --target conductor-test:claude --runtime herdr --json
```

**Checkpoint:** A worker result must still traverse `verify → advance → merge/close` before Phase 4 is considered proven.

---

## Phase 5 — Authoritative provider hooks and event-assisted monitoring

**Purpose:** Use Herdr-supported hooks to improve state latency and session recovery while retaining Conductor reconciliation.

### Planned file changes

| Action | Path | Responsibility |
|---|---|---|
| Create | `src/conductor/runtime/telemetry.py` | confidence-ranked observation fusion |
| Modify | `src/conductor/runtime/event_bridge.py` | subscription lifecycle, cursor/checkpoint, recovery replay |
| Modify | `src/conductor/dispatch.py` | monitor wakeup integration only |
| Modify | `src/conductor/completion.py` | schedule `verify_ready_results`, never direct promotion |
| Modify | `src/conductor/operator.py` | distinguish native hook, pane observation, artifact, and verification evidence |
| Create | `tests/test_runtime_telemetry.py` | precedence/conflict/replay cases |
| Create | `tests/test_monitor_event_assist.py` | wakeup, duplicate, missed-event fallback tests |
| Modify | `docs/herdr-runtime.md` | hook install/rollback and privacy/operator-consent guide |

### Evidence precedence

```text
1. Conductor persisted task/verification/approval artifacts
2. Explicit Conductor worker message or result artifact
3. Herdr native provider hook / session identity
4. Herdr pane/process observation
5. tmux transcript heuristic
6. model-assisted classification for unresolved conflicts only
```

### Monitoring semantics

- The event bridge may request an immediate Conductor monitor tick.
- A monitor tick reads durable task artifacts before changing its report.
- If an event is missed, Conductor's existing watch/poll/reconcile behavior remains sufficient to recover.
- Runtime events are appended/referenced durably so an operator can explain why a monitor woke up.
- Repeated identical events must be deduped and must not spam Telegram.

### Hook policy

Herdr provider integrations are an **opt-in runtime enhancement**. Installing Herdr's Hermes plugin writes to `~/.hermes/plugins/` and `~/.hermes/config.yaml`; do this only in a separately authorized profile-change task with backup, rollback, and restart verification. The initial Conductor integration must work without the Hermes plugin.

### Acceptance criteria

- Provider hook telemetry can improve `working`/`blocked`/session identity confidence where installed.
- A hook outage or absent event subscription never blocks artifact-based Conductor recovery.
- Hook-reported `done` wakes verification but cannot bypass it.
- Telegram output reports only material lifecycle changes and labels evidence source.

### Verification

```bash
cd /home/alhanaei/projects/Conductor
python -m pytest tests/test_runtime_telemetry.py tests/test_monitor_event_assist.py -q
python -m pytest -q
```

**Checkpoint:** Force a restart/reconnect and prove that Conductor reconstructs state from `.conductor` before accepting Herdr session data as telemetry.

---

## Phase 6 — Controlled pilot, recovery drill, and promotion decision

**Purpose:** Prove the system end-to-end before making Herdr a selectable production runtime.

### Pilot scope

- One disposable project.
- One approved Conductor track.
- One provider lane at a time.
- One created worktree.
- No live Hermes profile modifications unless separately approved.
- No production deployment tasks.

### Required scenarios

1. Normal flow: task dispatch → worker changes → result artifact → verification → advance → close.
2. Provider is busy at delivery: task is queued/deferred, no unsafe paste.
3. Provider approval/auth prompt: operator sees a concrete `blocked_prompt` action.
4. Agent reports done with missing result: Conductor remains non-terminal and reports missing evidence.
5. Herdr event duplicated/out of order: no duplicate task advancement or notification.
6. Herdr process/session unavailable: Conductor reports runtime degradation and falls back only if operator explicitly selects tmux.
7. Conductor restart: task/runtime binding and artifact state reconcile without ownership guessing.
8. Worktree mapping: pane cwd, recorded worktree, branch, and changed-file scope agree.
9. Terminal panel review: visible status matches Conductor artifact projections; discrepancies are shown as unresolved.

### Promotion criteria

- All common runtime contract tests pass.
- Full Conductor suite passes.
- No unsafe submission in negative scenarios.
- No false completion/merge eligibility from Herdr state.
- One recovery drill passes using artifacts as the starting point.
- Operator reports show stable task/lane attribution and no repeated heartbeat noise.
- The user explicitly approves widening runtime availability beyond the pilot.

## 7. Dependency Graph

```text
Phase 0 → Phase 1 → Phase 2
Phase 2 → Phase 3
Phase 2 → Phase 4
Phase 4 → Phase 5
Phase 3 + Phase 5 → Phase 6
```

- Phase 3 control-panel work may begin after read-only observation is proven because it does not deliver task instructions.
- Phase 4 mutating lane operations must wait for the adapter contract and observer correlation model.
- Phase 5 must wait for actual Herdr lane delivery so hooks/events have a known binding to enrich.
- Phase 6 must wait for both the control-panel and telemetry paths.

## 8. Data and Artifact Layout

Keep `.conductor/` authoritative. Add runtime observations as additive evidence:

```text
.conductor/
  lanes/
    <stable-lane-target>.json                 # current lane projection; add runtime/binding fields
  runtime/
    bindings/
      <track_id>/<task_id>.json                # immutable/reconciled runtime binding
    observations/
      <track_id>/<task_id>.jsonl               # append-only normalized runtime telemetry
    events/
      <source>/<event-id>.json                 # optional raw event evidence/cursor support
  tracks/<track_id>/
    tasks/<task_id>/
      route.json                               # retains task/worktree/lane semantic state
      status.json                              # retains valid Conductor enum fields only
      verification.json                        # remains verification authority
```

### Persistence rules

- Add fields; never make existing required fields optional/renamed without a migration.
- Treat raw Herdr payloads as external input; validate/redact before persistence.
- Persist an artifact reference or normalized summary, not secret-bearing environment/prompt bodies.
- State projections must remain rebuildable from append-only observation/event records.
- `reconcile` must flag conflicting runtime bindings rather than choosing the newest record silently.

## 9. CLI and Operator Experience Proposal

Do not expose broad commands until parity is proven. Proposed staged surface:

```bash
# Read-only after Phase 2
conductor runtime doctor --runtime herdr --json
conductor runtime status --track <track> --runtime herdr --json
conductor runtime observe --track <track> --runtime herdr --json

# Explicit panel after Phase 3
conductor runtime panel --track <track> --runtime herdr --json

# Explicit lane runtime selection after Phase 4
conductor lane ensure --target <session:window> --runtime herdr --launch --json
conductor lane status --target <session:window> --runtime herdr --json
conductor lane capture --target <session:window> --runtime herdr --json
conductor lane submit --target <session:window> --runtime herdr --task-file <path> --json

# Event-assist after Phase 5
conductor runtime watch --track <track> --runtime herdr --json
```

### Telegram rendering rules

```text
[PROGRESS] <track>/<task>
Runtime: herdr · <lane_target> · working (native provider hook)
Evidence: pane=<id> · workspace=<worktree> · artifact heartbeat=<timestamp>
Next: monitoring; no verification result yet
```

- State source must be stated when useful: `artifact`, `native_hook`, `pane_observation`, or `unresolved`.
- Do not include raw terminal transcript or task body by default.
- Never issue a final success message unless Conductor verification and terminal gates agree.

## 10. Risks and Mitigations

| Risk | Impact | Mitigation / gate |
|---|---|---|
| Herdr API/version drift | adapter breaks or contracts are guessed | Phase 0 schema capture, pinned compatibility matrix, fixtures from installed version |
| Herdr `done` mistaken for product completion | false merge/close | hard authority model; tests that prove no direct task promotion |
| Lost/misordered events | stale or incorrect operator view | append-only observations, source event ID dedupe, polling/reconcile fallback |
| Event-to-task misattribution | wrong task appears active/blocked | binding requires runtime ID + lane target + workspace correlation; otherwise `runtime_event_unresolved` |
| Terminal control panel becomes a second state store | split-brain | panel is a projection only; artifacts remain authoritative |
| Provider prompt detector regressions | unsafe paste / blocked work | reuse current negative transcript fixtures and add native-hook conflict cases |
| Worktree/pane mismatch | edits in wrong checkout | binding stores workspace path; enforce equality on dispatch/inspect/reconcile |
| Live Hermes profile mutation | broken gateway/profile configuration | separate approved task, backup/rollback, never part of initial integration |
| Licensing confusion | inappropriate code reuse | source-level boundary: contract inspiration only; legal decision before copying code |
| Control-panel noise | operator cannot find real blockers | dedupe events, material-change notifications only, compact Telegram status |

## 11. Open Decisions Required Before Implementation Authorization

1. **Runtime selection policy:** opt-in per lane, per track, or per project configuration? Recommendation: explicit per-track/pilot opt-in first.
2. **Herdr acquisition policy:** package install vs. source build vs. separate host. Recommendation: pinned released binary in a disposable sandbox first.
3. **Provider pilot order:** Claude, Codex, Gemini, or Grok. Recommendation: Claude first because current Conductor classifier coverage and operational experience are strongest.
4. **Control-panel scope:** overview-only first vs. automatic task-pane creation. Recommendation: overview plus explicit panel creation; no automatic task-panes until Phase 4.
5. **Herdr Hermes plugin:** install in the coding profile or defer. Recommendation: defer; assess the base socket/runtime path first.
6. **Worktree policy:** require a new worktree for all Herdr pilot tasks. Recommendation: yes, for code-writing pilot tasks; use a disposable repository and explicit `--create-worktree`.
7. **Remote/mobile operation:** include remote Herdr attach in the initial pilot. Recommendation: no; validate local recovery first, then separately test SSH/iPad attach.

## 12. Definition of Done for This Integration Track

A future execution track is complete only when:

- [ ] The current tmux runtime passes existing tests and behavior-parity tests after extraction.
- [ ] Herdr runtime interface is contract-tested against a pinned observed API/schema version.
- [ ] Existing task/track states, DoD checks, verification, merge approval, and close semantics are unchanged.
- [ ] Every Herdr-backed task has a durable lane binding and worktree/workspace correlation.
- [ ] Runtime events are additive telemetry; unresolved events are explicit and no event can self-promote a task.
- [ ] Negative tests prove non-ready panes cannot receive a task and `done` cannot bypass verification.
- [ ] At least one approved disposable end-to-end track has passed Conductor verification and recovery/reconciliation after a restart.
- [ ] The terminal control panel has Hermes-verified visual/readback evidence against `.conductor` artifacts.
- [ ] Operator reports remain compact, causal, and deduplicated.
- [ ] No live Hermes config/plugin changes occur without a separately authorized, rollback-tested task.

## 13. Authorization Handoff

This plan is **not executable** until Ahmed explicitly authorizes implementation and the corresponding Conductor feature spec/track records approval in-band.

When authorized, the first implementation run must be a new Conductor track whose first dispatchable slice is **Phase 0 + Phase 1 only**. The worker handoff must quote this plan's authorization line and link the generated track `definition_of_done.md`; the lane must not start Herdr installation or profile integration outside the selected approved scope.
