"""T1 contract tests for the durable runtime event ledger."""

import hashlib
import json

import pytest

from conductor.models import SchemaError
from conductor.runtime import LaneRuntime, TmuxLaneRuntime
from conductor.runtime.events import (
    EventCursor,
    RuntimeEvent,
    RuntimeEventKind,
    RuntimeEventLedger,
    runtime_event_id,
)
from conductor.store import ConductorStore, atomic_write_json, read_json, read_jsonl


@pytest.fixture()
def store(tmp_path):
    return ConductorStore.resolve(root=tmp_path, create=True)


def test_runtime_event_id_is_stable_and_round_trips():
    source = "tmux_control:Conductor"
    source_key = "%1:sha256-output"
    expected = hashlib.sha256(f"{source}:{source_key}".encode("utf-8")).hexdigest()

    first = RuntimeEvent(
        source=source,
        source_key=source_key,
        kind=RuntimeEventKind.PANE_OUTPUT,
        lane_target="Conductor:codex",
        track_id="track_1",
        task_id="task_1",
        worktree_path="/tmp/worktree",
        evidence_ref=".conductor/transcripts/pane.txt",
        confidence="correlated",
        payload={"tail": "bounded", "line_count": 3},
    )
    equivalent = RuntimeEvent(
        source=source,
        source_key=source_key,
        kind=RuntimeEventKind.PANE_OUTPUT,
    )
    restored = RuntimeEvent.from_dict(first.to_dict())

    assert runtime_event_id(source, source_key) == expected
    assert first.event_id == expected
    assert equivalent.event_id == expected
    assert restored.to_dict() == first.to_dict()
    assert restored.kind is RuntimeEventKind.PANE_OUTPUT


def test_duplicate_append_has_no_second_canonical_record_and_survives_restart(store):
    ledger = RuntimeEventLedger(store)
    first = RuntimeEvent(
        source="fs_artifact",
        source_key="tracks/track_1/tasks/task_1/result.md:hash",
        kind=RuntimeEventKind.ARTIFACT_CREATED,
        track_id="track_1",
        task_id="task_1",
    )
    duplicate = RuntimeEvent.from_dict(first.to_dict())

    assert ledger.append(first) is True
    assert ledger.append(duplicate) is False
    assert len(read_jsonl(store.runtime_events_path())) == 1

    restarted = RuntimeEventLedger(store)

    assert restarted.append(duplicate) is False
    assert [event.event_id for event in restarted.iter_events()] == [first.event_id]
    assert len(read_jsonl(store.runtime_events_path())) == 1


def test_legacy_root_stays_lazy_until_first_runtime_write(store):
    assert not store.runtime_dir().exists()

    ledger = RuntimeEventLedger(store)

    assert ledger.read_cursor("tmux_control:Conductor") is None
    assert list(ledger.iter_events()) == []
    assert not store.runtime_dir().exists()

    event = RuntimeEvent(
        source="tmux_control:Conductor",
        source_key="%1:first",
        kind=RuntimeEventKind.PANE_OUTPUT,
    )
    assert ledger.append(event) is True
    assert store.runtime_events_path().is_file()


def test_cursor_round_trip_uses_expected_layout(store):
    ledger = RuntimeEventLedger(store)
    cursor = EventCursor(source_id="tmux_control:Conductor", position="%1:42")

    ledger.write_cursor(cursor)

    expected_path = (
        store.root / "runtime" / "cursors" / "tmux_control:Conductor.json"
    )
    assert store.runtime_cursor_path(cursor.source_id) == expected_path
    assert expected_path.is_file()
    assert ledger.read_cursor(cursor.source_id).to_dict() == cursor.to_dict()


def test_cursor_source_mismatch_is_rejected(store):
    ledger = RuntimeEventLedger(store)
    requested_source = "tmux_control:Conductor"
    wrong = EventCursor(source_id="tmux_control:Other", position="42")
    atomic_write_json(store.runtime_cursor_path(requested_source), wrong.to_dict())

    with pytest.raises(SchemaError, match="cursor source mismatch"):
        ledger.read_cursor(requested_source)


@pytest.mark.parametrize(
    "source_id",
    ["", ".", "..", "../escape", "nested/source", "nested\\source"],
)
def test_cursor_path_rejects_unsafe_source_ids(store, source_id):
    with pytest.raises(ValueError, match="safe path component"):
        store.runtime_cursor_path(source_id)


@pytest.mark.parametrize(
    "kind",
    [
        RuntimeEventKind.UNRESOLVED_EVENT,
        RuntimeEventKind.WORKSPACE_PROVENANCE_MISMATCH,
    ],
)
def test_unresolved_kinds_persist_projection_and_canonical_event(store, kind):
    ledger = RuntimeEventLedger(store)
    event = RuntimeEvent(
        source="tmux_control:Conductor",
        source_key=f"%9:{kind.value}",
        kind=kind,
        lane_target="Conductor:unknown",
        task_id="task_1",
        worktree_path="/wrong/worktree",
        confidence="unresolved",
        payload={"reason": kind.value},
    )

    path = ledger.record_unresolved(event)

    assert path == store.runtime_unresolved_dir() / f"{event.event_id}.json"
    assert path.is_file()
    assert read_json(path)["kind"] == kind.value
    assert [item.event_id for item in ledger.iter_events()] == [event.event_id]


def test_record_unresolved_rejects_authoritative_event_kind(store):
    ledger = RuntimeEventLedger(store)
    event = RuntimeEvent(
        source="tmux_control:Conductor",
        source_key="%1:output",
        kind=RuntimeEventKind.PANE_OUTPUT,
    )

    with pytest.raises(SchemaError, match="requires an unresolved event kind"):
        ledger.record_unresolved(event)

    assert not store.runtime_dir().exists()


def test_gap_persists_projection_and_dedupes_equivalent_gap(store, monkeypatch):
    from conductor.runtime import events

    monkeypatch.setattr(events, "utc_now_iso", lambda: "2026-07-19T12:00:00+00:00")
    ledger = RuntimeEventLedger(store)

    first = ledger.record_gap("tmux_control:Conductor", "control client EOF")
    second = ledger.record_gap("tmux_control:Conductor", "control client EOF")

    expected_path = store.runtime_gaps_dir() / f"{first.event_id}.json"
    assert first.event_id == second.event_id
    assert first.kind is RuntimeEventKind.EVENT_STREAM_GAP
    assert first.payload == {
        "reason": "control client EOF",
        "source_id": "tmux_control:Conductor",
    }
    assert expected_path.is_file()
    assert read_json(expected_path)["kind"] == "event_stream_gap"
    assert len(read_jsonl(store.runtime_events_path())) == 1


def test_malformed_and_invalid_ledger_records_are_ignored(store):
    valid = RuntimeEvent(
        source="fs_artifact",
        source_key="tracks/track_1/tasks/task_1/status.json:hash",
        kind=RuntimeEventKind.ARTIFACT_MODIFIED,
    )
    path = store.runtime_events_path()
    path.parent.mkdir(parents=True)
    path.write_text(
        json.dumps(valid.to_dict())
        + "\n"
        + "{not-json\n"
        + json.dumps({"event_id": "invalid"})
        + "\n",
        encoding="utf-8",
    )

    ledger = RuntimeEventLedger(store)

    assert [event.event_id for event in ledger.iter_events()] == [valid.event_id]
    assert ledger.append(valid) is False


@pytest.mark.parametrize(
    "event,match",
    [
        (
            RuntimeEvent(
                event_id="wrong",
                source="fs_artifact",
                source_key="path:hash",
                kind=RuntimeEventKind.ARTIFACT_CREATED,
            ),
            "must match source and source_key",
        ),
        (
            RuntimeEvent(
                source="fs_artifact",
                source_key="path:hash",
                kind=RuntimeEventKind.ARTIFACT_CREATED,
                confidence="certain",
            ),
            "confidence must be one of",
        ),
        (
            RuntimeEvent(
                source="fs_artifact",
                source_key="path:hash",
                kind="artifact_created",
            ),
            "kind is invalid",
        ),
    ],
)
def test_invalid_runtime_events_are_rejected_without_writes(store, event, match):
    ledger = RuntimeEventLedger(store)

    with pytest.raises(SchemaError, match=match):
        ledger.append(event)

    assert not store.runtime_dir().exists()


def test_invalid_cursor_is_rejected_without_writes(store):
    ledger = RuntimeEventLedger(store)

    with pytest.raises(SchemaError, match="position is required"):
        ledger.write_cursor(EventCursor(source_id="tmux_control:Conductor"))

    assert not store.runtime_dir().exists()


def test_tmux_runtime_conforms_to_runtime_checkable_contract():
    runtime = TmuxLaneRuntime(object())

    assert isinstance(runtime, LaneRuntime)
