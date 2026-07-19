"""Durable, deduplicated runtime event records for event-assisted monitoring."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Dict, Iterator, Optional, Set

from ..models import SCHEMA_VERSION, SchemaError, _Model, utc_now_iso
from ..store import (
    ConductorStore,
    append_jsonl,
    atomic_write_json,
    iter_jsonl,
    read_json,
)


class RuntimeEventKind(str, Enum):
    PANE_OUTPUT = "pane_output"
    PANE_LIFECYCLE = "pane_lifecycle"
    ARTIFACT_CREATED = "artifact_created"
    ARTIFACT_MODIFIED = "artifact_modified"
    EVENT_STREAM_GAP = "event_stream_gap"
    UNRESOLVED_EVENT = "unresolved_event"
    WORKSPACE_PROVENANCE_MISMATCH = "workspace_provenance_mismatch"
    RECONCILIATION = "reconciliation"


_CONFIDENCE_VALUES = {"direct", "correlated", "unresolved"}
_UNRESOLVED_KINDS = {
    RuntimeEventKind.UNRESOLVED_EVENT,
    RuntimeEventKind.WORKSPACE_PROVENANCE_MISMATCH,
}


def runtime_event_id(source: str, source_key: str) -> str:
    """Return the stable identity for one source-native event."""
    material = f"{source}:{source_key}".encode("utf-8")
    return hashlib.sha256(material).hexdigest()


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise SchemaError(message)


def _optional_string(value: Optional[str], field_name: str) -> None:
    _require(
        value is None or isinstance(value, str),
        f"RuntimeEvent.{field_name} must be a string or null",
    )


@dataclass
class RuntimeEvent(_Model):
    event_id: str = ""
    source: str = ""
    source_key: str = ""
    kind: RuntimeEventKind = RuntimeEventKind.UNRESOLVED_EVENT
    observed_at: str = field(default_factory=utc_now_iso)
    lane_target: Optional[str] = None
    track_id: Optional[str] = None
    task_id: Optional[str] = None
    worktree_path: Optional[str] = None
    evidence_ref: Optional[str] = None
    confidence: str = "direct"
    payload: Dict[str, Any] = field(default_factory=dict)
    schema_version: int = SCHEMA_VERSION

    def __post_init__(self) -> None:
        if not self.event_id and self.source and self.source_key:
            self.event_id = runtime_event_id(self.source, self.source_key)

    def _post_load(self) -> None:
        if not isinstance(self.kind, RuntimeEventKind):
            try:
                self.kind = RuntimeEventKind(self.kind)
            except ValueError as exc:
                raise SchemaError(f"RuntimeEvent.kind is invalid: {self.kind!r}") from exc

    def validate(self) -> None:
        _require(
            isinstance(self.source, str) and bool(self.source),
            "RuntimeEvent.source is required",
        )
        _require(
            isinstance(self.source_key, str) and bool(self.source_key),
            "RuntimeEvent.source_key is required",
        )
        _require(isinstance(self.event_id, str), "RuntimeEvent.event_id must be a string")
        _require(
            self.event_id == runtime_event_id(self.source, self.source_key),
            "RuntimeEvent.event_id must match source and source_key",
        )
        _require(isinstance(self.kind, RuntimeEventKind), "RuntimeEvent.kind is invalid")
        _require(
            isinstance(self.observed_at, str) and bool(self.observed_at),
            "RuntimeEvent.observed_at is required",
        )
        for field_name in (
            "lane_target",
            "track_id",
            "task_id",
            "worktree_path",
            "evidence_ref",
        ):
            _optional_string(getattr(self, field_name), field_name)
        _require(
            self.confidence in _CONFIDENCE_VALUES,
            f"RuntimeEvent.confidence must be one of {sorted(_CONFIDENCE_VALUES)}",
        )
        _require(isinstance(self.payload, dict), "RuntimeEvent.payload must be a dict")
        _require(
            self.schema_version == SCHEMA_VERSION,
            f"RuntimeEvent.schema_version must be {SCHEMA_VERSION}",
        )


@dataclass
class EventCursor(_Model):
    source_id: str = ""
    position: str = ""
    updated_at: str = field(default_factory=utc_now_iso)

    def validate(self) -> None:
        _require(
            isinstance(self.source_id, str) and bool(self.source_id),
            "EventCursor.source_id is required",
        )
        _require(
            isinstance(self.position, str) and bool(self.position),
            "EventCursor.position is required",
        )
        _require(
            isinstance(self.updated_at, str) and bool(self.updated_at),
            "EventCursor.updated_at is required",
        )


class RuntimeEventLedger:
    """Append-only event ledger with restart-safe duplicate suppression."""

    def __init__(self, store: ConductorStore):
        self.store = store
        self._event_ids: Set[str] = set()
        for record in iter_jsonl(self.store.runtime_events_path()):
            try:
                event = RuntimeEvent.from_dict(record)
            except (SchemaError, TypeError):
                continue
            self._event_ids.add(event.event_id)

    def append(self, event: RuntimeEvent) -> bool:
        event.validate()
        if event.event_id in self._event_ids:
            return False
        append_jsonl(self.store.runtime_events_path(), event.to_dict())
        self._event_ids.add(event.event_id)
        return True

    def iter_events(self) -> Iterator[RuntimeEvent]:
        for record in iter_jsonl(self.store.runtime_events_path()):
            try:
                yield RuntimeEvent.from_dict(record)
            except (SchemaError, TypeError):
                continue

    def read_cursor(self, source_id: str) -> Optional[EventCursor]:
        data = read_json(self.store.runtime_cursor_path(source_id))
        if data is None:
            return None
        cursor = EventCursor.from_dict(data)
        if cursor.source_id != source_id:
            raise SchemaError(
                f"cursor source mismatch: expected {source_id!r}, got {cursor.source_id!r}"
            )
        return cursor

    def write_cursor(self, cursor: EventCursor) -> None:
        cursor.validate()
        atomic_write_json(self.store.runtime_cursor_path(cursor.source_id), cursor.to_dict())

    def record_unresolved(self, event: RuntimeEvent) -> Path:
        event.validate()
        if event.kind not in _UNRESOLVED_KINDS:
            raise SchemaError("record_unresolved requires an unresolved event kind")
        self.append(event)
        path = self.store.runtime_unresolved_dir() / f"{event.event_id}.json"
        atomic_write_json(path, event.to_dict())
        return path

    def record_gap(self, source_id: str, reason: str) -> RuntimeEvent:
        if not isinstance(source_id, str) or not source_id:
            raise SchemaError("record_gap source_id is required")
        if not isinstance(reason, str) or not reason:
            raise SchemaError("record_gap reason is required")
        observed_at = utc_now_iso()
        event = RuntimeEvent(
            source=source_id,
            source_key=f"gap:{observed_at}:{reason}",
            kind=RuntimeEventKind.EVENT_STREAM_GAP,
            observed_at=observed_at,
            payload={"reason": reason, "source_id": source_id},
        )
        self.append(event)
        path = self.store.runtime_gaps_dir() / f"{event.event_id}.json"
        atomic_write_json(path, event.to_dict())
        return event
