"""Blocked-prompt projection from fresh runtime event evidence."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from .models import LaneState, TaskState
from .runtime.events import RuntimeEvent, RuntimeEventKind, RuntimeEventLedger
from .store import ConductorStore

_ACTIVE_TASK_STATES = {TaskState.DISPATCHED, TaskState.WORKING}


def _parse_iso(value: Optional[str]) -> Optional[datetime]:
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed


def _fresh(event: RuntimeEvent, updated_at: str) -> bool:
    observed = _parse_iso(event.observed_at)
    updated = _parse_iso(updated_at)
    return observed is None or updated is None or observed >= updated


def active_blocked_prompts(store: ConductorStore, track_id: str) -> List[Dict[str, Any]]:
    """Return active tasks whose latest targeted observation is a live prompt.

    The event monitor owns live lane classification. This projection reads its
    durable observations and never captures every active pane during a status or
    operator query.
    """

    latest: Dict[str, RuntimeEvent] = {}
    for event in RuntimeEventLedger(store).iter_events():
        if event.kind is not RuntimeEventKind.PANE_OUTPUT:
            continue
        if event.track_id != track_id or not event.task_id:
            continue
        if "lane_state" not in event.payload:
            continue
        latest[event.task_id] = event

    blocked: List[Dict[str, Any]] = []
    for record in store.list_dispatch_records(track_id):
        if record.task_state not in _ACTIVE_TASK_STATES:
            continue
        if record.result_artifact_ref and Path(record.result_artifact_ref).exists():
            continue
        if not record.lane_target:
            continue
        event = latest.get(record.task_id)
        if event is None or event.lane_target != record.lane_target:
            continue
        if not _fresh(event, record.updated_at):
            continue
        if event.payload.get("lane_state") != LaneState.BLOCKED_PROMPT.value:
            continue
        blocked.append(
            {
                "task_id": record.task_id,
                "title": record.title,
                "lane_target": record.lane_target,
                "provider": record.provider,
                "lane_state": event.payload["lane_state"],
                "result_artifact_ref": record.result_artifact_ref,
                "event_id": event.event_id,
                "observed_at": event.observed_at,
                "operator_action": "approve the prompt in the tmux pane or move this lane to the project-root session",
            }
        )
    return blocked
