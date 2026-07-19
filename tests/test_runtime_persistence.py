"""Runtime metadata is additive and invisible to existing lane projections."""

from conductor.lanes import LaneAdapter
from conductor.models import (
    DispatchRecord,
    DispatchState,
    LaneRecord,
    LaneState,
    TaskState,
)
from conductor.store import ConductorStore


class FakeTmux:
    def __init__(self, transcript):
        self.transcript = transcript

    def available(self):
        return True

    def capture(self, target, lines=200):
        return True, self.transcript

    def send_text(self, target, text):
        return True

    def send_enter(self, target):
        return True


READY_CLAUDE_T = "│ > type here │\n? for shortcuts"


def test_legacy_lane_record_loads_with_tmux_runtime_defaults():
    record = LaneRecord.from_dict(
        {
            "lane_id": "lane_1",
            "target": "Conductor:claude",
            "session": "Conductor",
            "window": "claude",
            "provider": "claude",
            "state": "provider_ready",
        }
    )

    assert record.runtime == "tmux"
    assert record.adapter_meta == {}
    assert record.state is LaneState.PROVIDER_READY


def test_legacy_dispatch_record_loads_with_tmux_runtime_defaults():
    record = DispatchRecord.from_dict(
        {
            "task_id": "task_1",
            "track_id": "track_1",
            "task_state": "working",
            "dispatch_state": "submitted",
            "worktree_mode": "not_git_repo",
            "stale_risk": "none",
            "method_id": "build",
        }
    )

    assert record.runtime == "tmux"
    assert record.adapter_meta == {}
    assert record.task_state is TaskState.WORKING
    assert record.dispatch_state is DispatchState.SUBMITTED


def test_runtime_metadata_persists_on_lane_and_dispatch_records(tmp_path):
    store = ConductorStore.resolve(root=tmp_path, create=True)
    lane = LaneRecord(
        target="Conductor:claude",
        session="Conductor",
        window="claude",
        provider="claude",
        state=LaneState.PROVIDER_READY,
        adapter_meta={"pane": "%1"},
    )
    store.write_lane_record(store.lanes_dir / "Conductor_claude.json", lane)
    loaded_lane = store.read_lane_record_path(store.lanes_dir / "Conductor_claude.json")

    dispatch = DispatchRecord(
        task_id="task_1",
        track_id="track_1",
        task_state=TaskState.WORKING,
        dispatch_state=DispatchState.SUBMITTED,
        adapter_meta={"delivery": "confirmed"},
    )
    store.write_dispatch_record(dispatch)
    loaded_dispatch = store.read_dispatch_record("track_1", "task_1")

    assert loaded_lane.runtime == "tmux"
    assert loaded_lane.adapter_meta == {"pane": "%1"}
    assert loaded_dispatch.runtime == "tmux"
    assert loaded_dispatch.adapter_meta == {"delivery": "confirmed"}


def test_runtime_metadata_does_not_leak_into_existing_lane_status_projection(tmp_path):
    store = ConductorStore.resolve(root=tmp_path, create=True)
    adapter = LaneAdapter(store, tmux=FakeTmux(READY_CLAUDE_T))

    result = adapter.status("Conductor:claude")

    assert result["state"] == "provider_ready"
    assert "runtime" not in result
    assert "adapter_meta" not in result
    assert set(result) == {
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
