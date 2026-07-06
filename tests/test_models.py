"""Schema validation, enum coercion, and round-trip (de)serialization."""

import pytest

from conductor.models import (
    AccessList,
    ApprovalRequest,
    EvidenceLevel,
    FileLock,
    HeartbeatState,
    MessageEnvelope,
    MessageType,
    OperatorNotification,
    RecipientType,
    RouteDecision,
    SchemaError,
    SenderType,
    Task,
    TaskAttempt,
    TaskState,
    Track,
    TrackState,
    VerificationGate,
    WorkerLane,
    new_id,
)


def test_new_id_is_prefixed_and_unique():
    a = new_id("track")
    b = new_id("track")
    assert a.startswith("track_")
    assert a != b


def test_track_requires_goal():
    with pytest.raises(SchemaError):
        Track(goal="   ").validate()


def test_track_round_trip_preserves_enum():
    t = Track(goal="ship phase 1", state=TrackState.PLANNING)
    data = t.to_dict()
    assert data["state"] == "planning"  # enum collapsed to string
    restored = Track.from_dict(data)
    assert restored.state is TrackState.PLANNING
    assert restored.goal == "ship phase 1"
    assert restored.track_id == t.track_id


def test_from_dict_rejects_bad_enum():
    data = Track(goal="x").to_dict()
    data["state"] = "not_a_state"
    with pytest.raises(SchemaError):
        Track.from_dict(data)


def test_from_dict_ignores_unknown_fields():
    data = Track(goal="x").to_dict()
    data["future_field"] = {"added": "by a later schema"}
    restored = Track.from_dict(data)  # must not raise
    assert restored.goal == "x"


def test_task_nested_access_list_round_trip():
    task = Task(
        track_id="track_1",
        title="impl",
        state=TaskState.READY,
        access_list=AccessList(task_ids=["task_0"], artifact_refs=["spec.md"]),
    )
    data = task.to_dict()
    assert data["access_list"]["task_ids"] == ["task_0"]
    restored = Task.from_dict(data)
    assert isinstance(restored.access_list, AccessList)
    assert restored.access_list.task_ids == ["task_0"]
    assert restored.state is TaskState.READY


def test_task_requires_track_id():
    with pytest.raises(SchemaError):
        Task(track_id="", title="x").validate()


def test_message_envelope_round_trip():
    msg = MessageEnvelope(
        track_id="track_1",
        type=MessageType.PROGRESS,
        sender_type=SenderType.WORKER,
        sender_id="w1",
        recipient_type=RecipientType.BROADCAST,
        summary="halfway",
    )
    data = msg.to_dict()
    assert data["type"] == "PROGRESS"
    assert data["sender_type"] == "worker"
    restored = MessageEnvelope.from_dict(data)
    assert restored.type is MessageType.PROGRESS
    assert restored.sender_type is SenderType.WORKER
    assert restored.recipient_type is RecipientType.BROADCAST


def test_message_requires_track_id():
    with pytest.raises(SchemaError):
        MessageEnvelope(track_id="").validate()


def test_filelock_validation():
    with pytest.raises(SchemaError):
        FileLock(path="", worker_id="w1").validate()
    fl = FileLock(path="a.py", worker_id="w1", track_id="t1")
    fl.validate()
    assert FileLock.from_dict(fl.to_dict()).path == "a.py"


def test_taskattempt_positive_number():
    with pytest.raises(SchemaError):
        TaskAttempt(task_id="t", attempt_number=0).validate()


def test_remaining_models_round_trip():
    models = [
        WorkerLane(target="Conductor:claude"),
        HeartbeatState(worker_id="w1", track_id="t1"),
        ApprovalRequest(track_id="t1", requested_by="op"),
        VerificationGate(track_id="t1", name="tests", commands=["pytest -q"],
                         evidence_level=EvidenceLevel.TOOL_VERIFIED),
        RouteDecision(track_id="t1", task_id="task_1", chosen_lane="Conductor:claude"),
        OperatorNotification(track_id="t1", title="done"),
    ]
    for m in models:
        restored = type(m).from_dict(m.to_dict())
        assert restored.to_dict() == m.to_dict()
