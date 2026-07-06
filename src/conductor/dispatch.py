"""Phase 4 dispatch loop: route approved tasks to lanes/worktrees, safely.

Bridges Phase 2 (plan DAG) and Phase 3 (lane adapter). It is deterministic and
non-destructive: artifacts, route decisions, and worktree *plans* always
succeed; lane delivery is gated by Phase 3 readiness and degrades to a recorded
``pending_lane``/``blocked_lane`` state instead of failing or pasting unsafely.

It does NOT promote a task to complete and runs no verification — that is Phase 5.
"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from .lanes import LaneAdapter, LaneError
from .message_bus import MessageBus
from .methods import get_method
from .models import (
    DispatchRecord,
    DispatchState,
    LaneState,
    MessageType,
    PlanStatus,
    RecipientType,
    RouteDecision,
    SenderType,
    StaleRisk,
    Task,
    TaskState,
    TrackRecord,
    utc_now_iso,
)
from .store import ConductorStore, atomic_write_text
from .worktree import GitClient, allocate_worktree


class DispatchError(RuntimeError):
    """Raised on invalid dispatch operations (unapproved plan, unknown task...)."""


# --------------------------------------------------------------------------- #
# Routing policy (deterministic)
# --------------------------------------------------------------------------- #
# Task kind -> default provider. Provider quirks/launch are out of scope here.
KIND_PROVIDER = {
    "clarify": "claude",
    "design": "claude",
    "implement": "codex",
    "test": "codex",
    "review": "claude",
    "general": "claude",
}


def infer_kind(title: str) -> str:
    t = (title or "").lower()
    if "clarify" in t:
        return "clarify"
    if "design" in t:
        return "design"
    if "implement" in t:
        return "implement"
    if "test" in t or "verify" in t:
        return "test"
    if "review" in t:
        return "review"
    return "general"


def provider_for_kind(kind: str) -> str:
    return KIND_PROVIDER.get(kind, "claude")


# --------------------------------------------------------------------------- #
# Stale-risk classifier (deterministic)
# --------------------------------------------------------------------------- #
_RISK_ORDER = {StaleRisk.NONE: 0, StaleRisk.LOW: 1, StaleRisk.MEDIUM: 2, StaleRisk.HIGH: 3}


def _parse_iso(value: Optional[str]) -> Optional[datetime]:
    if not value:
        return None
    try:
        dt = datetime.fromisoformat(value)
    except ValueError:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt


def classify_stale_risk(heartbeat_at: Optional[str], now: Optional[str] = None,
                        dispatch_state: Optional[DispatchState] = None,
                        lane_state: Optional[LaneState] = None,
                        task_state: Optional[TaskState] = None) -> StaleRisk:
    """Deterministic stale-risk from heartbeat age + lane/dispatch signals.

    Terminal tasks are never stale. A blocked lane is at least ``medium``. An
    ``absent`` lane on a task believed to be running is ``high``. Otherwise risk
    grows with heartbeat age (60s/300s/900s → low/medium/high).
    """
    if task_state in (TaskState.COMPLETE, TaskState.CANCELLED, TaskState.FAILED):
        return StaleRisk.NONE

    risk = StaleRisk.NONE
    if dispatch_state is DispatchState.BLOCKED_LANE:
        risk = StaleRisk.MEDIUM

    now_dt = _parse_iso(now) or datetime.now(timezone.utc)
    hb_dt = _parse_iso(heartbeat_at)
    if hb_dt is not None:
        age = (now_dt - hb_dt).total_seconds()
        if age >= 900:
            age_risk = StaleRisk.HIGH
        elif age >= 300:
            age_risk = StaleRisk.MEDIUM
        elif age >= 60:
            age_risk = StaleRisk.LOW
        else:
            age_risk = StaleRisk.NONE
        if _RISK_ORDER[age_risk] > _RISK_ORDER[risk]:
            risk = age_risk

    if lane_state is LaneState.ABSENT and dispatch_state is DispatchState.SUBMITTED:
        risk = StaleRisk.HIGH

    return risk


# --------------------------------------------------------------------------- #
# Task artifact rendering
# --------------------------------------------------------------------------- #
def render_task_artifact(record: TrackRecord, task: Task, kind: str,
                         result_ref: str, status_ref: str) -> str:
    access = ", ".join(task.access_list.task_ids) or "_none (spec.md only)_"
    deps = ", ".join(task.dependencies) or "_none_"
    method = get_method(task.method_id)
    acceptance = "\n".join(f"- [ ] {item}" for item in task.acceptance_criteria) or "- [ ] Task objective is satisfied."
    anti_items = list(method.anti_rationalizations)
    if "Do not claim completion without command evidence." not in anti_items:
        anti_items.append("Do not claim completion without command evidence.")
    anti = "\n".join(f"- {item}" for item in anti_items)
    verification = "\n".join(f"- [ ] {item}" for item in task.verification_requirements) or "- [ ] Result artifact is present and non-empty."
    verify_cmds = ("\n".join(f"- `{c}`" for c in task.verification_commands)
                   or "- _none configured; conductor checks artifacts only_")
    dod_refs = ", ".join(task.definition_of_done_refs) or "definition_of_done.md"
    return f"""# Task — {task.title}

- task_id: {task.task_id}
- track_id: {task.track_id}
- kind: {kind}
- method: {task.method_id}
- autonomy_policy: {task.autonomy_policy}
- risk_class: {task.risk_class}
- state target: dispatched (worker should set working on pickup)

## Objective

{task.description}

## Method Contract

- method: {task.method_id}
- workflow: {method.workflow}
- description: {method.description}
- autonomy_policy: {task.autonomy_policy}
- risk_class: {task.risk_class}

## Acceptance Criteria

{acceptance}

## Anti-Rationalization Guardrails

{anti}

## Definition of Done

- standing artifact: ../../definition_of_done.md
- task refs: {dod_refs}
- Task acceptance criteria met.
- Standing quality bar met.
- Evidence listed in the result artifact.

## Scope / Access (do not exceed)

- dependencies: {deps}
- access_list.task_ids: {access}
- access_list.artifact_refs: {', '.join(task.access_list.artifact_refs)}

## Source references

- spec: ../../spec.md
- plan: ../../plan.md
- definition_of_done: ../../definition_of_done.md

## Expected outputs

- write your result artifact to: {result_ref}
- status/heartbeat projection: {status_ref}

## Worker protocol (run these yourself)

- heartbeat every few minutes:
  `python -m conductor worker beat --track {task.track_id} --task {task.task_id} --worker <your-id> --note "<progress>"`
- after writing your result artifact, record your completion claim:
  `python -m conductor worker complete --track {task.track_id} --task {task.task_id} --worker <your-id>`

## Verification Requirements

{verification}

## Verification Commands (conductor runs these at verify time)

{verify_cmds}

Do not self-mark complete. Conductor verification is the completion gate.
"""


# --------------------------------------------------------------------------- #
# Dispatcher
# --------------------------------------------------------------------------- #
class Dispatcher:
    def __init__(self, store: ConductorStore, lane_adapter: Optional[LaneAdapter] = None,
                 git: Optional[GitClient] = None, default_session: Optional[str] = None):
        self.store = store
        self.lane = lane_adapter if lane_adapter is not None else LaneAdapter(store)
        self.git = git if git is not None else GitClient()
        # Default tmux session/project segment: the project directory name.
        self.default_session = default_session or store.root.parent.name or "conductor"

    @property
    def project_root(self) -> Path:
        return self.store.root.parent

    # -- dispatch ----------------------------------------------------------- #
    def dispatch(self, track_id: str, lane_session: Optional[str] = None,
                 force: bool = False, create_worktree: bool = False) -> Dict[str, Any]:
        # Serialize against concurrent loop/operator RMW on the same track record.
        with self.store.track_mutex(track_id):
            return self._dispatch_locked(track_id, lane_session, force, create_worktree)

    def _dispatch_locked(self, track_id: str, lane_session: Optional[str],
                         force: bool, create_worktree: bool) -> Dict[str, Any]:
        record = self.store.read_track_record(track_id)
        if record is None:
            raise DispatchError(f"unknown track: {track_id}")
        if record.plan_status is not PlanStatus.APPROVED:
            raise DispatchError(
                f"plan for track {track_id} is not approved (plan_status="
                f"{record.plan_status.value!r}); run 'conductor approve plan' first"
            )

        session = lane_session or self.default_session
        ready = [t for t in record.tasks if t.state is TaskState.READY]
        dispatched: List[Dict[str, Any]] = []
        for task in ready:
            dispatched.append(self._dispatch_task(record, task, session, force, create_worktree))

        # Retry earlier pending_lane tasks: a lane that was absent/busy at dispatch
        # time may be provider_ready now (or a pool slot may have freed up).
        resubmitted = self._retry_pending_lanes(record, session, force)

        if dispatched or resubmitted:
            self.store.write_track_record(record)  # persist updated task states

        return {
            "ok": True,
            "track_id": track_id,
            "dispatched_count": len(dispatched),
            "dispatched": dispatched,
            "resubmitted_count": len(resubmitted),
            "resubmitted": resubmitted,
            "note": ("no ready tasks to dispatch" if not (dispatched or resubmitted) else None),
        }

    # -- lane pool ------------------------------------------------------------ #
    _ACTIVE_LANE_STATES = (TaskState.DISPATCHED, TaskState.WORKING, TaskState.NEEDS_FIX)

    def _lane_pool_size(self) -> int:
        from .store import read_json
        config = read_json(self.store.config_path, {}) or {}
        try:
            return max(1, int(config.get("lane_pool_size", 3)))
        except (TypeError, ValueError):
            return 3

    def _occupied_lanes(self, exclude_task_id: Optional[str] = None) -> set:
        """Lane targets held by active tasks across ALL tracks (lanes are global)."""
        occupied = set()
        for tid in self.store.list_track_ids():
            for d in self.store.list_dispatch_records(tid):
                if d.task_id == exclude_task_id:
                    continue
                if d.lane_target and d.task_state in self._ACTIVE_LANE_STATES:
                    occupied.add(d.lane_target)
        return occupied

    def _allocate_lane(self, session: str, provider: str,
                       exclude_task_id: Optional[str] = None):
        """Pick the first free pool lane: provider, provider-2, ... provider-N.

        Returns ``(lane_target, None)`` or ``(None, reason)`` when every pool
        slot is held by another active task — the caller records the task as
        ``pending_lane`` rather than double-submitting into an occupied pane.
        """
        occupied = self._occupied_lanes(exclude_task_id)
        pool_size = self._lane_pool_size()
        candidates = [f"{session}:{provider}" if i == 1 else f"{session}:{provider}-{i}"
                      for i in range(1, pool_size + 1)]
        for target in candidates:
            if target not in occupied:
                return target, None
        return None, (f"lane pool exhausted: all {pool_size} '{provider}' lane(s) "
                      f"hold active tasks")

    def _retry_pending_lanes(self, record: TrackRecord, session: str,
                             force: bool) -> List[Dict[str, Any]]:
        """Re-attempt submission for tasks stuck in ``pending_lane``."""
        resubmitted: List[Dict[str, Any]] = []
        for drec in self.store.list_dispatch_records(record.track.track_id):
            if drec.dispatch_state is not DispatchState.PENDING_LANE:
                continue
            if drec.task_state is not TaskState.DISPATCHED:
                continue
            result_path = self.store.task_result_path(record.track.track_id, drec.task_id)
            if result_path.exists():
                continue  # worker already produced a result; let verify handle it

            # Reuse the assigned lane, or allocate one now if the pool was full.
            lane_target = drec.lane_target
            if not lane_target:
                lane_target, note = self._allocate_lane(
                    session, drec.provider or "claude", exclude_task_id=drec.task_id)
                if lane_target is None:
                    drec.blocker = note
                    self.store.write_dispatch_record(drec)
                    continue

            lane_status = self.lane.status(lane_target)
            lane_state = LaneState(lane_status["state"])
            now = utc_now_iso()
            drec.lane_target = lane_target
            drec.lane_state = lane_state
            drec.heartbeat_at = now

            if lane_state is LaneState.PROVIDER_READY and drec.task_artifact_ref:
                try:
                    self.lane.submit(lane_target, drec.task_artifact_ref, force=force)
                except LaneError as exc:
                    drec.blocker = f"submit deferred: {exc}"
                    self.store.write_dispatch_record(drec)
                    continue
                drec.dispatch_state = DispatchState.SUBMITTED
                drec.task_state = TaskState.WORKING
                drec.blocker = None
                self.store.write_dispatch_record(drec)
                for t in record.tasks:
                    if t.task_id == drec.task_id:
                        t.state = TaskState.WORKING
                self.store.append_event({"event": "task_resubmitted",
                                         "track_id": record.track.track_id,
                                         "task_id": drec.task_id, "lane": lane_target})
                resubmitted.append({"task_id": drec.task_id, "lane_target": lane_target,
                                    "dispatch_state": drec.dispatch_state.value})
            else:
                if lane_state is LaneState.BLOCKED_PROMPT:
                    drec.dispatch_state = DispatchState.BLOCKED_LANE
                    drec.blocker = "lane shows an operator-action prompt (blocked_prompt)"
                else:
                    drec.blocker = f"lane not ready (state={lane_state.value})"
                self.store.write_dispatch_record(drec)
        return resubmitted

    def _dispatch_task(self, record: TrackRecord, task: Task, session: str,
                       force: bool, create_worktree: bool) -> Dict[str, Any]:
        now = utc_now_iso()
        kind = infer_kind(task.title)
        provider = provider_for_kind(kind)
        # Lane pool: parallel tasks of the same provider get distinct panes
        # (provider, provider-2, ...) instead of colliding on one.
        lane_target, pool_note = self._allocate_lane(session, provider,
                                                     exclude_task_id=task.task_id)
        base_lane = f"{session}:{provider}"

        # 1. Worktree allocation / branch policy (non-destructive by default).
        alloc = allocate_worktree(self.project_root, record.track.track_id, task.task_id,
                                  task.title, git=self.git, create=create_worktree)

        # 2. Paths.
        result_ref = str(self.store.task_result_path(record.track.track_id, task.task_id))
        status_ref = str(self.store.task_status_path(record.track.track_id, task.task_id))
        route_ref = str(self.store.task_route_path(record.track.track_id, task.task_id))
        task_md = self.store.task_artifact_path(record.track.track_id, task.task_id)

        # 3. Task artifact writer.
        atomic_write_text(task_md, render_task_artifact(record, task, kind, result_ref, status_ref))

        # 4. Route decision record.
        decision = RouteDecision(
            track_id=record.track.track_id, task_id=task.task_id,
            chosen_lane=lane_target or base_lane,
            candidates=[lane_target] if lane_target else [base_lane],
            reason=(f"kind={kind} -> provider={provider}"
                    + (f"; {pool_note}; queued" if lane_target is None else "")),
            task_type=kind, risk="normal",
        )
        self.store.write_route_decision(decision)

        # 5+6. Lane readiness + safe submit (never assume the pane is ready).
        dispatch_state = DispatchState.PENDING_LANE
        task_state = TaskState.DISPATCHED
        blocker: Optional[str] = None
        lane_state: Optional[LaneState] = None
        if lane_target is None:
            # Every pool slot holds an active task: queue rather than
            # double-submit into an occupied pane. Retried on later ticks.
            blocker = pool_note
        else:
            lane_status = self.lane.status(lane_target)
            lane_state = LaneState(lane_status["state"])
            if lane_state is LaneState.PROVIDER_READY:
                try:
                    self.lane.submit(lane_target, str(task_md), force=force)
                    dispatch_state = DispatchState.SUBMITTED
                    task_state = TaskState.WORKING
                except LaneError as exc:
                    dispatch_state = DispatchState.PENDING_LANE
                    blocker = f"submit deferred: {exc}"
            elif lane_state is LaneState.BLOCKED_PROMPT:
                dispatch_state = DispatchState.BLOCKED_LANE
                blocker = "lane shows an operator-action prompt (blocked_prompt)"
            else:
                blocker = f"lane not ready (state={lane_state.value})"

        # 7. Persist task state in the plan record.
        task.state = task_state

        # 8. Dispatch record + stale risk.
        stale = classify_stale_risk(now, now, dispatch_state, lane_state, task_state)
        drec = DispatchRecord(
            task_id=task.task_id, track_id=record.track.track_id, title=task.title, kind=kind,
            task_state=task_state, dispatch_state=dispatch_state, provider=provider,
            lane_target=lane_target, lane_state=lane_state,
            worktree_mode=alloc.mode, branch=alloc.branch, workspace=alloc.workspace,
            worktree_path=alloc.worktree_path,
            task_artifact_ref=str(task_md), result_artifact_ref=result_ref,
            route_ref=route_ref, status_ref=status_ref,
            access_task_ids=list(task.access_list.task_ids), dependencies=list(task.dependencies),
            method_id=task.method_id,
            acceptance_criteria=list(task.acceptance_criteria),
            definition_of_done_refs=list(task.definition_of_done_refs),
            verification_requirements=list(task.verification_requirements),
            verification_commands=list(task.verification_commands),
            autonomy_policy=task.autonomy_policy,
            risk_class=task.risk_class,
            stale_risk=stale, blocker=blocker, dispatched_at=now, heartbeat_at=now,
        )
        self.store.write_dispatch_record(drec)

        # 9. Message bus + event (artifact reference only).
        bus = MessageBus(self.store, record.track.track_id)
        bus.send_simple(
            type=MessageType.ASSIGNMENT, sender_type=SenderType.CONDUCTOR, sender_id="conductor",
            recipient_type=RecipientType.LANE, recipient_id=lane_target or base_lane,
            task_id=task.task_id,
            summary=f"dispatch {task.task_id} -> {lane_target or 'queued'} ({dispatch_state.value})",
            body_ref=str(task_md),
        )
        self.store.append_event({"event": "task_dispatched", "track_id": record.track.track_id,
                                 "task_id": task.task_id, "lane": lane_target,
                                 "dispatch_state": dispatch_state.value,
                                 "worktree_mode": alloc.mode.value})

        return self._task_summary(drec)

    # -- task status -------------------------------------------------------- #
    def task_status(self, track_id: str, task_id: str, now: Optional[str] = None) -> Dict[str, Any]:
        drec = self.store.read_dispatch_record(track_id, task_id)
        if drec is None:
            # Not dispatched yet — fall back to the plan view.
            record = self.store.read_track_record(track_id)
            if record is None:
                raise DispatchError(f"unknown track: {track_id}")
            task = next((t for t in record.tasks if t.task_id == task_id), None)
            if task is None:
                raise DispatchError(f"unknown task {task_id} in track {track_id}")
            return {
                "ok": True, "track_id": track_id, "task_id": task_id, "title": task.title,
                "task_state": task.state.value, "dispatch_state": None,
                "dispatched": False, "stale_risk": StaleRisk.NONE.value,
                "dependencies": task.dependencies,
                "access_task_ids": task.access_list.task_ids,
                "route": None, "lane_state": None, "worktree_mode": None,
            }
        # Recompute stale-risk freshly so an aged heartbeat surfaces.
        drec.stale_risk = classify_stale_risk(drec.heartbeat_at, now, drec.dispatch_state,
                                              drec.lane_state, drec.task_state)
        route = self.store.read_route_decision(track_id, task_id)
        summary = self._task_summary(drec)
        summary["route"] = route.to_dict() if route else None
        summary["dispatched"] = True
        return summary

    # -- follow-up ---------------------------------------------------------- #
    def followup(self, track_id: str, task_id: str, body_file: str,
                 force: bool = False) -> Dict[str, Any]:
        drec = self._require_dispatch(track_id, task_id)
        now = utc_now_iso()

        body_path = Path(body_file)
        if not body_path.exists():
            raise DispatchError(f"follow-up body file not found: {body_file}")
        body = body_path.read_text(encoding="utf-8")  # stored as artifact, never pasted

        followups_dir = self.store.task_dir(track_id, task_id) / "followups"
        followups_dir.mkdir(parents=True, exist_ok=True)
        n = len(list(followups_dir.glob("followup-*.md"))) + 1
        artifact = followups_dir / f"followup-{n}.md"
        atomic_write_text(artifact, body)

        bus = MessageBus(self.store, track_id)
        msg = bus.send_simple(
            type=MessageType.FOLLOWUP, sender_type=SenderType.CONDUCTOR, sender_id="conductor",
            recipient_type=RecipientType.TASK, recipient_id=task_id, task_id=task_id,
            summary=f"follow-up #{n} for {task_id}", body_ref=str(artifact),
        )
        self.store.append_event({"event": "task_followup", "track_id": track_id,
                                 "task_id": task_id, "artifact": str(artifact)})

        # Optionally deliver a short reference if the lane is ready — never the body.
        delivered = False
        delivery_note = None
        if drec.lane_target:
            instruction = (f"Follow-up #{n} for task {task_id}: read {artifact} and continue. "
                           f"See {drec.task_artifact_ref}.")
            try:
                self.lane.send_instruction(drec.lane_target, instruction, force=force,
                                           kind="task_followup_delivery")
                delivered = True
            except LaneError as exc:
                delivery_note = f"pending: {exc}"

        drec.last_followup_at = now
        drec.heartbeat_at = now
        drec.stale_risk = classify_stale_risk(now, now, drec.dispatch_state,
                                              drec.lane_state, drec.task_state)
        self.store.write_dispatch_record(drec)

        return {"ok": True, "track_id": track_id, "task_id": task_id, "followup_index": n,
                "artifact_ref": str(artifact), "message_id": msg.message_id,
                "delivered": delivered, "delivery_note": delivery_note,
                "lane_state": drec.lane_state.value if drec.lane_state else None,
                "pasted_body": False}

    # -- nudge -------------------------------------------------------------- #
    def nudge(self, track_id: str, task_id: str, force: bool = False) -> Dict[str, Any]:
        drec = self._require_dispatch(track_id, task_id)
        now = utc_now_iso()
        instruction = (f"Nudge: status on task {task_id}? Continue per {drec.task_artifact_ref}.")

        sent = False
        note = None
        if drec.lane_target:
            try:
                self.lane.send_instruction(drec.lane_target, instruction, force=force, kind="task_nudge")
                sent = True
            except LaneError as exc:
                note = f"pending: {exc}"
        else:
            note = "no lane target on record"

        event = {"event": "task_nudge" if sent else "task_nudge_pending",
                 "track_id": track_id, "task_id": task_id, "lane": drec.lane_target}
        self.store.append_event(event)

        bus = MessageBus(self.store, track_id)
        bus.send_simple(
            type=MessageType.EVENT, sender_type=SenderType.CONDUCTOR, sender_id="conductor",
            recipient_type=RecipientType.TASK, recipient_id=task_id, task_id=task_id,
            summary=f"nudge {task_id} ({'sent' if sent else 'pending'})",
        )

        drec.last_nudge_at = now
        drec.heartbeat_at = now
        drec.stale_risk = classify_stale_risk(now, now, drec.dispatch_state,
                                              drec.lane_state, drec.task_state)
        self.store.write_dispatch_record(drec)

        return {"ok": True, "track_id": track_id, "task_id": task_id, "sent": sent,
                "note": note, "lane_state": drec.lane_state.value if drec.lane_state else None}

    # -- helpers ------------------------------------------------------------ #
    def _require_dispatch(self, track_id: str, task_id: str) -> DispatchRecord:
        drec = self.store.read_dispatch_record(track_id, task_id)
        if drec is None:
            raise DispatchError(
                f"task {task_id} in track {track_id} has not been dispatched yet"
            )
        return drec

    def _task_summary(self, drec: DispatchRecord) -> Dict[str, Any]:
        return {
            "ok": True,
            "track_id": drec.track_id,
            "task_id": drec.task_id,
            "title": drec.title,
            "kind": drec.kind,
            "method_id": drec.method_id,
            "autonomy_policy": drec.autonomy_policy,
            "risk_class": drec.risk_class,
            "acceptance_criteria": drec.acceptance_criteria,
            "definition_of_done_refs": drec.definition_of_done_refs,
            "verification_requirements": drec.verification_requirements,
            "verification_commands": drec.verification_commands,
            "task_state": drec.task_state.value,
            "dispatch_state": drec.dispatch_state.value if drec.dispatch_state else None,
            "provider": drec.provider,
            "lane_target": drec.lane_target,
            "lane_state": drec.lane_state.value if drec.lane_state else None,
            "worktree_mode": drec.worktree_mode.value,
            "branch": drec.branch,
            "workspace": drec.workspace,
            "worktree_path": drec.worktree_path,
            "task_artifact_ref": drec.task_artifact_ref,
            "result_artifact_ref": drec.result_artifact_ref,
            "route_ref": drec.route_ref,
            "status_ref": drec.status_ref,
            "dependencies": drec.dependencies,
            "access_task_ids": drec.access_task_ids,
            "stale_risk": drec.stale_risk.value,
            "blocker": drec.blocker,
            "verification_status": drec.verification_status.value if drec.verification_status else None,
            "verification_ref": drec.verification_ref,
            "verifier": drec.verifier,
            "verified_at": drec.verified_at,
            "ready_for_merge": drec.ready_for_merge,
            "fix_attempts": drec.fix_attempts,
            "max_fix_attempts": drec.max_fix_attempts,
            "dispatched_at": drec.dispatched_at,
            "heartbeat_at": drec.heartbeat_at,
            "last_followup_at": drec.last_followup_at,
            "last_nudge_at": drec.last_nudge_at,
            "last_fix_at": drec.last_fix_at,
        }
