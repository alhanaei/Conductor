"""Per-track append-only message bus.

Each track owns ``.message-bus/`` containing:

* ``queue.jsonl``        — the immutable, append-only message log (source of truth).
* ``events/<id>.event``  — one tiny signal file per message, for watchers/pollers
                           that want filesystem-level notification without parsing
                           the whole queue.
* ``worker-status.json`` — a projection: latest known status per worker, rebuilt
                           from the queue so it can be regenerated after a crash.

The bus never mutates a prior message. "Editing" status is done by appending a
newer message and re-projecting. This keeps causality auditable.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from .models import (
    HeartbeatStatus,
    MessageEnvelope,
    MessageType,
    RecipientType,
    SenderType,
    utc_now_iso,
)
from .store import (
    ConductorStore,
    append_jsonl,
    atomic_write_json,
    read_json,
    read_jsonl,
)

# Message types that carry a worker liveness signal worth projecting.
_STATUS_TYPES = {
    MessageType.PROGRESS,
    MessageType.HEARTBEAT,
    MessageType.TASK_COMPLETE,
    MessageType.TASK_FAILED,
    MessageType.BLOCKED,
    MessageType.STATUS,
}


class MessageBus:
    def __init__(self, store: ConductorStore, track_id: str):
        self.store = store
        self.track_id = track_id

    # -- writing ------------------------------------------------------------ #
    def send(self, message: MessageEnvelope) -> MessageEnvelope:
        """Append a validated message, drop an event signal file, re-project status."""
        if not message.track_id:
            message.track_id = self.track_id
        if message.track_id != self.track_id:
            raise ValueError(
                f"message.track_id {message.track_id!r} does not match bus track {self.track_id!r}"
            )
        message.validate()

        self.store.message_bus_dir(self.track_id).mkdir(parents=True, exist_ok=True)
        self.store.events_dir(self.track_id).mkdir(parents=True, exist_ok=True)

        append_jsonl(self.store.queue_path(self.track_id), message.to_dict())
        self._write_event_file(message)
        self._project_worker_status()
        return message

    def send_simple(
        self,
        type: MessageType,
        body: str = "",
        sender_type: SenderType = SenderType.WORKER,
        sender_id: str = "",
        recipient_type: RecipientType = RecipientType.BROADCAST,
        recipient_id: str = "",
        task_id: Optional[str] = None,
        summary: str = "",
        body_ref: Optional[str] = None,
        requires_ack: bool = False,
    ) -> MessageEnvelope:
        """Convenience constructor used by the CLI."""
        msg = MessageEnvelope(
            track_id=self.track_id,
            task_id=task_id,
            type=type,
            sender_type=sender_type,
            sender_id=sender_id,
            recipient_type=recipient_type,
            recipient_id=recipient_id,
            body=body,
            body_ref=body_ref,
            summary=summary or (body[:120] if body else type.value),
            requires_ack=requires_ack,
        )
        return self.send(msg)

    def _write_event_file(self, message: MessageEnvelope) -> None:
        """Write a small per-message signal file: ``events/<message_id>.event``."""
        event_path = self.store.events_dir(self.track_id) / f"{message.message_id}.event"
        payload = {
            "message_id": message.message_id,
            "type": message.type.value,
            "task_id": message.task_id,
            "sender_id": message.sender_id,
            "created_at": message.created_at,
        }
        atomic_write_json(event_path, payload)

    # -- projections -------------------------------------------------------- #
    def _project_worker_status(self) -> Dict[str, Any]:
        """Rebuild ``worker-status.json`` from the queue (last write per worker)."""
        workers: Dict[str, Dict[str, Any]] = {}
        for rec in read_jsonl(self.store.queue_path(self.track_id)):
            try:
                msg_type = MessageType(rec.get("type"))
            except ValueError:
                continue
            if msg_type not in _STATUS_TYPES:
                continue
            worker = rec.get("sender_id") or "unknown"
            workers[worker] = {
                "worker_id": worker,
                "last_type": msg_type.value,
                "last_task_id": rec.get("task_id"),
                "last_summary": rec.get("summary", ""),
                "last_message_id": rec.get("message_id"),
                "last_seen_at": rec.get("created_at"),
                "heartbeat": _infer_heartbeat(msg_type).value,
            }
        projection = {
            "track_id": self.track_id,
            "workers": workers,
            "updated_at": utc_now_iso(),
        }
        atomic_write_json(self.store.worker_status_path(self.track_id), projection)
        return projection

    def worker_status(self) -> Dict[str, Any]:
        return read_json(
            self.store.worker_status_path(self.track_id),
            {"track_id": self.track_id, "workers": {}},
        )

    # -- reading ------------------------------------------------------------ #
    def list_messages(
        self,
        type: Optional[MessageType] = None,
        task_id: Optional[str] = None,
        limit: Optional[int] = None,
    ) -> List[MessageEnvelope]:
        """Return messages in append order, optionally filtered. Deterministic."""
        messages: List[MessageEnvelope] = []
        for rec in read_jsonl(self.store.queue_path(self.track_id)):
            try:
                msg = MessageEnvelope.from_dict(rec)
            except Exception:
                continue
            if type is not None and msg.type != type:
                continue
            if task_id is not None and msg.task_id != task_id:
                continue
            messages.append(msg)
        if limit is not None and limit >= 0:
            messages = messages[-limit:]
        return messages

    def count(self) -> int:
        return len(read_jsonl(self.store.queue_path(self.track_id)))


def _infer_heartbeat(msg_type: MessageType) -> HeartbeatStatus:
    if msg_type in (MessageType.TASK_COMPLETE, MessageType.TASK_FAILED):
        return HeartbeatStatus.DEAD
    if msg_type == MessageType.BLOCKED:
        return HeartbeatStatus.STALE
    return HeartbeatStatus.ALIVE
