"""Fast blocked-prompt detection for active Conductor tasks.

This module is intentionally small and side-effect-light: it refreshes lane
status for already-dispatched/working tasks that do not yet have a result
artifact, then returns first-class operator details when the provider pane is at
an approval/input prompt.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List

from .lanes import LaneAdapter, LaneError
from .models import LaneState, TaskState
from .store import ConductorStore

_ACTIVE_TASK_STATES = {TaskState.DISPATCHED, TaskState.WORKING}


def active_blocked_prompts(store: ConductorStore, track_id: str) -> List[Dict[str, Any]]:
    """Return active dispatched/working tasks currently blocked in provider UI.

    Only tasks without an existing ``result.md`` are scanned. This preserves the
    normal completion path and avoids reclassifying historical finished output.
    ``LaneAdapter.status`` performs the live tmux capture and uses the lane
    classifier's recent-tail semantics, so stale scrollback text does not become
    a blocker.
    """

    adapter = LaneAdapter(store)
    blocked: List[Dict[str, Any]] = []
    for drec in store.list_dispatch_records(track_id):
        if drec.task_state not in _ACTIVE_TASK_STATES:
            continue
        if drec.result_artifact_ref and Path(drec.result_artifact_ref).exists():
            continue
        if not drec.lane_target:
            continue
        try:
            lane = adapter.status(drec.lane_target)
        except LaneError:
            continue
        if lane.get("state") != LaneState.BLOCKED_PROMPT.value:
            continue
        blocked.append({
            "task_id": drec.task_id,
            "title": drec.title,
            "lane_target": drec.lane_target,
            "provider": drec.provider,
            "lane_state": lane.get("state"),
            "result_artifact_ref": drec.result_artifact_ref,
            "operator_action": "approve the prompt in the tmux pane or move this lane to the project-root session",
        })
    return blocked
