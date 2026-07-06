"""Append/read semantics, event files, and the worker-status projection."""

import pytest

from conductor.message_bus import MessageBus
from conductor.models import (
    HeartbeatStatus,
    MessageEnvelope,
    MessageType,
    SenderType,
)
from conductor.store import ConductorStore


@pytest.fixture()
def store(tmp_path):
    return ConductorStore.resolve(root=tmp_path, create=True)


def test_send_appends_and_lists_in_order(store):
    track = store.create_track("goal")
    bus = MessageBus(store, track.track_id)
    bus.send_simple(MessageType.PROGRESS, body="one", sender_id="w1")
    bus.send_simple(MessageType.PROGRESS, body="two", sender_id="w1")
    bus.send_simple(MessageType.TASK_COMPLETE, body="done", sender_id="w1")

    messages = bus.list_messages()
    assert [m.body for m in messages] == ["one", "two", "done"]
    assert bus.count() == 3


def test_send_writes_event_file(store):
    track = store.create_track("goal")
    bus = MessageBus(store, track.track_id)
    msg = bus.send_simple(MessageType.PROGRESS, body="hi", sender_id="w1")
    event_file = store.events_dir(track.track_id) / f"{msg.message_id}.event"
    assert event_file.exists()


def test_list_filters_by_type_and_task(store):
    track = store.create_track("goal")
    bus = MessageBus(store, track.track_id)
    bus.send_simple(MessageType.PROGRESS, body="p", sender_id="w1", task_id="task_a")
    bus.send_simple(MessageType.BLOCKED, body="b", sender_id="w1", task_id="task_b")

    assert len(bus.list_messages(type=MessageType.BLOCKED)) == 1
    assert len(bus.list_messages(task_id="task_a")) == 1
    assert len(bus.list_messages(type=MessageType.PROGRESS, task_id="task_b")) == 0


def test_limit_returns_last_n(store):
    track = store.create_track("goal")
    bus = MessageBus(store, track.track_id)
    for i in range(5):
        bus.send_simple(MessageType.PROGRESS, body=str(i), sender_id="w1")
    last2 = bus.list_messages(limit=2)
    assert [m.body for m in last2] == ["3", "4"]


def test_worker_status_projection_tracks_latest(store):
    track = store.create_track("goal")
    bus = MessageBus(store, track.track_id)
    bus.send_simple(MessageType.PROGRESS, body="working", sender_id="w1")
    bus.send_simple(MessageType.PROGRESS, body="still", sender_id="w2")
    bus.send_simple(MessageType.TASK_COMPLETE, body="done", sender_id="w1")

    workers = bus.worker_status()["workers"]
    assert set(workers) == {"w1", "w2"}
    assert workers["w1"]["last_type"] == "TASK_COMPLETE"
    assert workers["w1"]["heartbeat"] == HeartbeatStatus.DEAD.value
    assert workers["w2"]["heartbeat"] == HeartbeatStatus.ALIVE.value


def test_projection_rebuilds_from_queue_after_restart(store, tmp_path):
    track = store.create_track("goal")
    bus = MessageBus(store, track.track_id)
    bus.send_simple(MessageType.PROGRESS, body="x", sender_id="w1")

    # New store + bus = simulated restart; projection already on disk.
    reloaded = ConductorStore.resolve(root=tmp_path, create=False)
    bus2 = MessageBus(reloaded, track.track_id)
    assert "w1" in bus2.worker_status()["workers"]
    assert bus2.count() == 1


def test_track_id_mismatch_rejected(store):
    track = store.create_track("goal")
    bus = MessageBus(store, track.track_id)
    bad = MessageEnvelope(track_id="some_other_track", type=MessageType.PROGRESS,
                          sender_type=SenderType.WORKER, sender_id="w1")
    with pytest.raises(ValueError):
        bus.send(bad)
