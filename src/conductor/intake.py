"""Phase 2 orchestration: goal intake, plan review, and plan approval.

This layer turns an operator goal into a durable, reviewable plan on top of the
Phase 1 state substrate, and gates it behind an explicit approval. It contains
no dispatch, tmux, or provider logic — that is intentionally a later phase.
"""

from __future__ import annotations

from typing import Any, Dict

from . import planner
from .models import (
    ApprovalKind,
    ApprovalRequest,
    ApprovalState,
    PlanStatus,
    TrackRecord,
    TrackState,
    utc_now_iso,
)
from .store import ConductorStore, atomic_write_text


class PlanError(RuntimeError):
    """Raised on invalid plan-lifecycle operations (e.g. unknown track)."""


def _task_workflow_mode_from_tags(tags: list[str]) -> str:
    for tag in tags:
        if tag.startswith("task-workflow:"):
            return planner._validate_task_workflow_mode(tag.split(":", 1)[1])
    return "stage"


def create_planned_track(store: ConductorStore, goal: str,
                         requested_by: str = "operator",
                         task_workflow_mode: str = "stage") -> TrackRecord:
    """`go --plan-only`: create a track and generate spec/plan/metadata.

    Produces a deterministic task DAG, real ``spec.md`` / ``plan.md`` artifacts,
    a pending PLAN approval request, and persists the aggregate to
    ``metadata.json``. No worker dispatch.
    """
    if not goal or not goal.strip():
        raise PlanError("goal must be a non-empty string")

    # Reuse the Phase 1 layout creation (dirs, bus, placeholders, events).
    track = store.create_track(goal)
    track.state = TrackState.PLAN_REVIEW

    task_workflow_mode = planner._validate_task_workflow_mode(task_workflow_mode)
    track.tags.append(f"task-workflow:{task_workflow_mode}")
    tasks = planner.build_tasks(track.track_id, goal, task_workflow_mode=task_workflow_mode)
    approval = ApprovalRequest(
        track_id=track.track_id,
        kind=ApprovalKind.PLAN,
        state=ApprovalState.PENDING,
        requested_by=requested_by,
    )

    record = TrackRecord(
        track=track,
        plan_status=PlanStatus.PENDING_REVIEW,
        plan_revision=1,
        tasks=tasks,
        approvals=[approval],
    )

    # Overwrite the placeholder spec/plan with real Phase 2 content.
    tdir = store.track_dir(track.track_id)
    atomic_write_text(tdir / "spec.md",
                      planner.render_spec(track.track_id, goal, track.created_at))
    atomic_write_text(tdir / "plan.md",
                      planner.render_plan(track.track_id, goal, track.created_at,
                                          tasks, record.plan_status.value,
                                          record.plan_revision,
                                          task_workflow_mode=task_workflow_mode))
    atomic_write_text(store.definition_of_done_path(track.track_id),
                      planner.render_definition_of_done(track.track_id, goal))
    from .store import atomic_write_json
    atomic_write_json(store.quality_gates_path(track.track_id),
                      planner.render_quality_gates(track.track_id, goal))

    store.write_track_record(record)
    store.append_event({"event": "plan_generated", "track_id": track.track_id,
                        "task_count": len(tasks), "plan_status": record.plan_status.value,
                        "task_workflow_mode": task_workflow_mode})
    return record


def review_plan(store: ConductorStore, track_id: str) -> Dict[str, Any]:
    """`plan review`: machine-readable summary of the generated plan + gate state."""
    record = store.read_track_record(track_id)
    if record is None:
        raise PlanError(f"unknown track: {track_id}")

    approval = record.plan_approval()
    return {
        "track_id": track_id,
        "goal": record.track.goal,
        "track_state": record.track.state.value,
        "plan_status": record.plan_status.value,
        "plan_revision": record.plan_revision,
        "max_plan_revisions": record.max_plan_revisions,
        "task_count": len(record.tasks),
        "approval_pending": (approval.state is ApprovalState.PENDING) if approval else False,
        "approved": record.is_plan_approved(),
        "spec_ref": str(store.track_dir(track_id) / "spec.md"),
        "plan_ref": str(store.track_dir(track_id) / "plan.md"),
        "tasks": [
            {
                "task_id": t.task_id,
                "title": t.title,
                "state": t.state.value,
                "dependencies": t.dependencies,
                "access_list": t.access_list.to_dict(),
            }
            for t in record.tasks
        ],
    }


def approve_plan(store: ConductorStore, track_id: str,
                 decided_by: str = "operator", rationale: str = "") -> Dict[str, Any]:
    """`approve plan`: persist approval + timestamp. Idempotent if already approved."""
    record = store.read_track_record(track_id)
    if record is None:
        raise PlanError(f"unknown track: {track_id}")

    approval = record.plan_approval()
    if approval is None:
        # No plan was generated yet — nothing to approve.
        raise PlanError(f"track {track_id} has no plan to approve; run 'go --plan-only' first")

    already = record.is_plan_approved()
    if not already:
        approval.state = ApprovalState.APPROVED
        approval.decided_by = decided_by
        approval.decided_at = utc_now_iso()
        if rationale:
            approval.rationale = rationale
        record.plan_status = PlanStatus.APPROVED
        record.track.state = TrackState.APPROVED
        store.write_track_record(record)
        # Re-render plan.md so the artifact's approval status is not stale.
        atomic_write_text(
            store.track_dir(track_id) / "plan.md",
            planner.render_plan(track_id, record.track.goal, record.track.created_at,
                                record.tasks, record.plan_status.value,
                                record.plan_revision,
                                task_workflow_mode=_task_workflow_mode_from_tags(record.track.tags)),
        )
        store.append_event({"event": "plan_approved", "track_id": track_id,
                            "decided_by": decided_by})

    return {
        "track_id": track_id,
        "approved": True,
        "already_approved": already,
        "plan_status": record.plan_status.value,
        "track_state": record.track.state.value,
        "approval_id": approval.approval_id,
        "decided_by": approval.decided_by,
        "decided_at": approval.decided_at,
    }
