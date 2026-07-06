"""Operator-facing status projection.

Aggregates the per-track logs and projections into a single JSON document that
Hermes/Telegram can parse. It reads everything fresh from disk so the status is
always grounded in the durable state, never in process memory.
"""

from __future__ import annotations

from typing import Any, Dict, List

from .lanes import list_lane_status
from .locks import LockManager
from .message_bus import MessageBus
from .models import utc_now_iso
from .store import ConductorStore, read_json


def build_status(store: ConductorStore) -> Dict[str, Any]:
    config = read_json(store.config_path, {})
    tracks: List[Dict[str, Any]] = []

    total_messages = 0
    total_locks = 0
    total_workers = 0

    for track_id in store.list_track_ids():
        record = store.read_track_record(track_id)
        if record is None:
            continue
        track = record.track
        bus = MessageBus(store, track_id)
        locks = LockManager(store, track_id)

        message_count = bus.count()
        worker_status = bus.worker_status().get("workers", {})
        lock_list = locks.list_locks()

        total_messages += message_count
        total_workers += len(worker_status)
        total_locks += len(lock_list)

        tracks.append({
            "track_id": track.track_id,
            "goal": track.goal,
            "state": track.state.value,
            "plan_status": record.plan_status.value,
            "task_count": len(record.tasks),
            "approved": record.is_plan_approved(),
            "created_at": track.created_at,
            "updated_at": track.updated_at,
            "message_count": message_count,
            "workers": worker_status,
            "locks": [fl.to_dict() for fl in lock_list],
        })

    lanes = list_lane_status(store)

    return {
        "schema_version": config.get("schema_version"),
        "state_root": str(store.root),
        "generated_at": utc_now_iso(),
        "totals": {
            "tracks": len(tracks),
            "messages": total_messages,
            "locks": total_locks,
            "workers": total_workers,
            "lanes": len(lanes),
        },
        "tracks": tracks,
        "lanes": lanes,
    }
