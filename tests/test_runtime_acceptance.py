"""Independent acceptance coverage for the Phase A tmux runtime."""

import json

import pytest

from conductor.lanes import LaneAdapter, LaneError
from conductor.models import DispatchRecord, LaneRecord, LaneState
from conductor.runtime import TmuxLaneRuntime
from conductor.store import ConductorStore


class FakeTmux:
    def __init__(self, transcript="", capture_ok=True):
        self.transcript = transcript
        self.capture_ok = capture_ok
        self.sent = []
        self.entered = 0

    def available(self):
        return True

    def capture(self, target, lines=200):
        return self.capture_ok, self.transcript if self.capture_ok else ""

    def send_text(self, target, text):
        self.sent.append((target, text))
        return True

    def send_enter(self, target):
        self.entered += 1
        return True


READY_TRANSCRIPT = "> type here\n? for shortcuts"

STATUS_KEYS = {
    "ok",
    "lane_id",
    "target",
    "session",
    "window",
    "provider",
    "state",
    "tmux_available",
    "current_task_id",
    "last_line_count",
    "last_transcript_ref",
    "last_event",
    "last_classified_at",
    "last_capture_at",
    "last_submit_at",
    "last_heartbeat_at",
    "created_at",
    "updated_at",
    "escaped_id",
}


@pytest.fixture()
def store(tmp_path):
    return ConductorStore.resolve(root=tmp_path, create=True)


@pytest.mark.parametrize(
    "transcript,capture_ok,expected_state",
    [
        ("user@host:~/repo$ ", True, LaneState.SHELL),
        ("esc to interrupt", True, LaneState.BUSY),
        ("Do you want to proceed?\n1. Yes\n2. No", True, LaneState.BLOCKED_PROMPT),
        ("plain provider output", True, LaneState.UNKNOWN),
        ("", False, LaneState.ABSENT),
    ],
)
def test_runtime_refusal_preserves_event_side_effect(
    store, tmp_path, transcript, capture_ok, expected_state
):
    task = tmp_path / "task.md"
    task.write_text("body", encoding="utf-8")
    tmux = FakeTmux(transcript=transcript, capture_ok=capture_ok)
    runtime = TmuxLaneRuntime(LaneAdapter(store, tmux=tmux))

    with pytest.raises(LaneError, match="refusing to submit"):
        runtime.submit("Conductor:claude", str(task))

    record = store.read_lane_record_path(store.lanes_dir / "Conductor_claude.json")
    assert record.state is expected_state
    assert record.last_event["event"] == "submit_refused"
    assert record.last_event["state"] == expected_state.value
    assert tmux.sent == []
    assert tmux.entered == 0


def test_runtime_preserves_force_escape_hatch_on_non_ready_lane(store, tmp_path):
    task = tmp_path / "task.md"
    task.write_text("body", encoding="utf-8")
    tmux = FakeTmux(transcript="user@host:~/repo$ ")
    adapter = LaneAdapter(store, tmux=tmux)
    adapter.delivery_settle_seconds = 0
    runtime = TmuxLaneRuntime(adapter)

    result = runtime.submit("Conductor:claude", str(task), force=True)

    assert result["submitted"] is True
    assert result["state"] == "shell"
    assert result["forced"] is True
    assert len(tmux.sent) == 1
    assert tmux.entered == 1


def test_runtime_keeps_status_capture_and_submit_projection_keys_stable(store, tmp_path):
    task = tmp_path / "task.md"
    task.write_text("body", encoding="utf-8")
    adapter = LaneAdapter(store, tmux=FakeTmux(transcript=READY_TRANSCRIPT))
    adapter.delivery_settle_seconds = 0
    runtime = TmuxLaneRuntime(adapter)

    status = runtime.status("Conductor:claude")
    capture = runtime.capture("Conductor:claude", lines=25)
    submit = runtime.submit("Conductor:claude", str(task))

    assert set(status) == STATUS_KEYS
    assert set(capture) == STATUS_KEYS | {
        "captured_at",
        "line_count",
        "transcript",
        "transcript_ref",
    }
    assert set(submit) == {
        "ok",
        "submitted",
        "target",
        "state",
        "forced",
        "task_file",
        "instruction",
        "submitted_at",
    }
    for projection in (status, capture, submit):
        assert "runtime" not in projection
        assert "adapter_meta" not in projection


def test_legacy_store_files_load_runtime_defaults(store):
    lane_path = store.lanes_dir / "Conductor_claude.json"
    lane_path.write_text(
        json.dumps(
            {
                "lane_id": "lane_legacy",
                "target": "Conductor:claude",
                "session": "Conductor",
                "window": "claude",
                "state": "provider_ready",
            }
        ),
        encoding="utf-8",
    )
    dispatch_path = store.task_status_path("track_legacy", "task_legacy")
    dispatch_path.parent.mkdir(parents=True)
    dispatch_path.write_text(
        json.dumps(
            {
                "task_id": "task_legacy",
                "track_id": "track_legacy",
                "task_state": "working",
                "dispatch_state": "submitted",
                "worktree_mode": "not_git_repo",
                "stale_risk": "none",
                "method_id": "test",
            }
        ),
        encoding="utf-8",
    )

    lane = store.list_lane_records()[0]
    dispatch = store.read_dispatch_record("track_legacy", "task_legacy")

    assert lane.runtime == "tmux"
    assert lane.adapter_meta == {}
    assert dispatch.runtime == "tmux"
    assert dispatch.adapter_meta == {}


def test_runtime_metadata_defaults_are_not_shared_between_records():
    lane_one = LaneRecord(target="Conductor:a", session="Conductor", window="a")
    lane_two = LaneRecord(target="Conductor:b", session="Conductor", window="b")
    dispatch_one = DispatchRecord(task_id="task_a", track_id="track_a")
    dispatch_two = DispatchRecord(task_id="task_b", track_id="track_b")

    lane_one.adapter_meta["pane"] = {"id": "%1"}
    dispatch_one.adapter_meta["delivery"] = {"confirmed": True}

    assert lane_two.adapter_meta == {}
    assert dispatch_two.adapter_meta == {}
    assert LaneRecord.from_dict(lane_one.to_dict()).adapter_meta == {"pane": {"id": "%1"}}
    assert DispatchRecord.from_dict(dispatch_one.to_dict()).adapter_meta == {
        "delivery": {"confirmed": True}
    }
