"""T3 tests for filesystem-assisted Conductor artifact events."""

import os
import time
from pathlib import Path

import pytest

from conductor.runtime.events import RuntimeEventKind, RuntimeEventLedger
from conductor.runtime.fs_events import (
    ArtifactEventSource,
    FakeWatcher,
    InotifyWatcher,
    WatcherEvent,
)
from conductor.store import ConductorStore


@pytest.fixture()
def store(tmp_path):
    return ConductorStore.resolve(root=tmp_path, create=True)


def _task_file(store, name="result.md"):
    path = store.task_dir("track_1", "task_1") / name
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


def test_start_adds_root_and_known_artifact_directories(store):
    _task_file(store).write_text("result", encoding="utf-8")
    bus = store.message_bus_dir("track_1")
    bus.mkdir(parents=True)
    watcher = FakeWatcher()
    source = ArtifactEventSource(store, watcher)

    source.start()

    assert store.tracks_dir in watcher.added
    assert store.track_dir("track_1") in watcher.added
    assert store.tasks_dir("track_1") in watcher.added
    assert store.task_dir("track_1", "task_1") in watcher.added
    assert bus in watcher.added


@pytest.mark.parametrize(
    "name,kind",
    [
        ("result.md", "created"),
        ("status.json", "modified"),
        ("verification.json", "modified"),
        ("verification.md", "created"),
        ("verdict.json", "created"),
    ],
)
def test_task_artifacts_become_correlated_events(store, name, kind):
    path = _task_file(store, name)
    path.write_text(f"{name}-body", encoding="utf-8")
    watcher = FakeWatcher([WatcherEvent(path=path, kind=kind, at="2026-07-20T00:00:00Z")])
    source = ArtifactEventSource(store, watcher)
    source.start()

    events = source.read_events()

    assert len(events) == 1
    event = events[0]
    expected_kind = (
        RuntimeEventKind.ARTIFACT_CREATED
        if kind == "created"
        else RuntimeEventKind.ARTIFACT_MODIFIED
    )
    assert event.kind is expected_kind
    assert event.source == "fs_artifact"
    assert event.track_id == "track_1"
    assert event.task_id == "task_1"
    assert event.evidence_ref == f"tracks/track_1/tasks/task_1/{name}"
    assert event.payload == {
        "artifact": name,
        "path": f"tracks/track_1/tasks/task_1/{name}",
    }


def test_message_bus_event_is_track_correlated(store):
    path = store.message_bus_dir("track_1") / "events" / "event_1.json"
    path.parent.mkdir(parents=True)
    path.write_text("{}", encoding="utf-8")
    watcher = FakeWatcher([WatcherEvent(path=path, kind="created", at="now")])
    source = ArtifactEventSource(store, watcher)
    source.start()

    event = source.read_events()[0]

    assert event.track_id == "track_1"
    assert event.task_id is None
    assert event.payload["artifact"] == "message_bus"
    assert event.evidence_ref == "tracks/track_1/.message-bus/events/event_1.json"


def test_same_path_and_content_dedupes_in_runtime_ledger(store):
    path = _task_file(store)
    path.write_text("same", encoding="utf-8")
    watcher = FakeWatcher(
        [
            WatcherEvent(path=path, kind="modified", at="one"),
            WatcherEvent(path=path, kind="modified", at="two"),
        ]
    )
    source = ArtifactEventSource(store, watcher)
    source.start()
    first, second = source.read_events()
    ledger = RuntimeEventLedger(store)

    assert first.event_id == second.event_id
    assert ledger.append(first) is True
    assert ledger.append(second) is False
    assert len(list(ledger.iter_events())) == 1


def test_content_change_changes_event_identity(store):
    path = _task_file(store)
    path.write_text("one", encoding="utf-8")
    watcher = FakeWatcher([WatcherEvent(path=path, kind="modified", at="one")])
    source = ArtifactEventSource(store, watcher)
    source.start()
    first = source.read_events()[0]

    path.write_text("two", encoding="utf-8")
    watcher.push(WatcherEvent(path=path, kind="modified", at="two"))
    second = source.read_events()[0]

    assert first.event_id != second.event_id


def test_overflow_sets_gap_without_inventing_artifact_event(store):
    watcher = FakeWatcher(
        [WatcherEvent(path=store.tracks_dir, kind="overflow", at="now")]
    )
    source = ArtifactEventSource(store, watcher)
    source.start()

    assert source.read_events() == []
    assert source.gap_reason() == "filesystem watcher overflow"


def test_unrelated_and_out_of_root_paths_are_ignored(store, tmp_path):
    unrelated = store.root / "unrelated.txt"
    unrelated.write_text("ignore", encoding="utf-8")
    outside = tmp_path / "outside.txt"
    outside.write_text("ignore", encoding="utf-8")
    task_other = _task_file(store, "notes.txt")
    task_other.write_text("ignore", encoding="utf-8")
    watcher = FakeWatcher(
        [
            WatcherEvent(path=unrelated, kind="modified", at="now"),
            WatcherEvent(path=outside, kind="modified", at="now"),
            WatcherEvent(path=task_other, kind="modified", at="now"),
        ]
    )
    source = ArtifactEventSource(store, watcher)
    source.start()

    assert source.read_events() == []


def test_created_directory_is_added_as_watch_without_artifact_event(store):
    task_dir = store.task_dir("track_1", "task_new")
    task_dir.mkdir(parents=True)
    watcher = FakeWatcher([WatcherEvent(path=task_dir, kind="created", at="now")])
    source = ArtifactEventSource(store, watcher)
    source.start()
    watcher.added.clear()

    assert source.read_events() == []
    assert watcher.added == [task_dir]


def test_close_is_explicit_and_idempotent(store):
    watcher = FakeWatcher()
    source = ArtifactEventSource(store, watcher)
    source.start()

    source.close()
    source.close()

    assert watcher.close_calls == 1


@pytest.mark.skipif(
    os.environ.get("CONDUCTOR_LIVE_INOTIFY") != "1",
    reason="set CONDUCTOR_LIVE_INOTIFY=1 for the gated live inotify smoke",
)
def test_live_inotify_observes_result_creation(store):
    task_dir = store.task_dir("track_1", "task_1")
    task_dir.mkdir(parents=True)
    watcher = InotifyWatcher()
    source = ArtifactEventSource(store, watcher)
    source.start()
    try:
        path = task_dir / "result.md"
        path.write_text("done", encoding="utf-8")
        deadline = time.monotonic() + 3.0
        events = []
        while time.monotonic() < deadline and not events:
            events.extend(source.read_events(timeout=0.2))
        assert any(
            event.kind is RuntimeEventKind.ARTIFACT_CREATED
            and event.task_id == "task_1"
            for event in events
        )
    finally:
        source.close()
