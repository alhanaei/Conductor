"""T4 tests for event correlation and targeted runtime monitoring."""

from pathlib import Path

import pytest

from conductor.blocked_prompts import active_blocked_prompts
from conductor.models import DispatchRecord, LaneState, TaskState
from conductor.runtime.events import RuntimeEvent, RuntimeEventKind, RuntimeEventLedger
from conductor.runtime.monitor import EventMonitor
from conductor.store import ConductorStore


class FakeLaneAdapter:
    def __init__(self, states=None):
        self.states = states or {}
        self.calls = []

    def status(self, target):
        self.calls.append(target)
        return {
            "target": target,
            "state": self.states.get(target, LaneState.PROVIDER_READY.value),
        }


class FakeCompletionEngine:
    def __init__(self):
        self.calls = []

    def verify_ready_results(self, track_id):
        self.calls.append(track_id)
        return {"ok": True, "track_id": track_id}


@pytest.fixture()
def store(tmp_path):
    return ConductorStore.resolve(root=tmp_path, create=True)


def _dispatch(store, track_id, task_id, lane_target, *, state=TaskState.DISPATCHED):
    worktree = store.root / "worktrees" / task_id
    worktree.mkdir(parents=True, exist_ok=True)
    record = DispatchRecord(
        track_id=track_id,
        task_id=task_id,
        title=task_id,
        task_state=state,
        lane_target=lane_target,
        provider=lane_target.split(":", 1)[1],
        workspace=str(worktree),
        worktree_path=str(worktree),
        result_artifact_ref=str(store.task_result_path(track_id, task_id)),
    )
    store.write_dispatch_record(record)
    return store.read_dispatch_record(track_id, task_id)


def _pane_event(lane_target="project:codex", **overrides):
    fields = {
        "source": "tmux_control:project",
        "source_key": "pane:%1:one",
        "kind": RuntimeEventKind.PANE_OUTPUT,
        "observed_at": "2099-01-01T00:00:00+00:00",
        "lane_target": lane_target,
        "payload": {"pane_id": "%1", "tail": "Allow command?"},
    }
    fields.update(overrides)
    return RuntimeEvent(**fields)


def _monitor(store, lane=None, completion=None):
    return EventMonitor(
        store,
        lane_adapter=lane or FakeLaneAdapter(),
        completion_engine=completion or FakeCompletionEngine(),
    )


def test_fresh_pane_event_correlates_and_refreshes_only_matching_lane(store):
    matched = _dispatch(store, "track_1", "task_1", "project:codex")
    other = _dispatch(store, "track_1", "task_2", "project:claude")
    lane = FakeLaneAdapter({"project:codex": LaneState.BLOCKED_PROMPT.value})
    monitor = _monitor(store, lane=lane)

    result = monitor.process(_pane_event())

    assert result["accepted"] is True
    assert result["task_id"] == matched.task_id
    assert lane.calls == [matched.lane_target]
    assert other.lane_target not in lane.calls
    events = list(RuntimeEventLedger(store).iter_events())
    source_event = events[0]
    assert source_event.track_id == matched.track_id
    assert source_event.task_id == matched.task_id
    assert source_event.worktree_path == matched.worktree_path
    assert source_event.confidence == "correlated"
    assert events[-1].payload["lane_state"] == LaneState.BLOCKED_PROMPT.value
    current = store.read_dispatch_record(matched.track_id, matched.task_id)
    assert current.task_state is TaskState.DISPATCHED
    assert current.ready_for_merge is False


def test_duplicate_pane_event_does_not_reclassify_lane(store):
    _dispatch(store, "track_1", "task_1", "project:codex")
    lane = FakeLaneAdapter()
    monitor = _monitor(store, lane=lane)
    event = _pane_event()

    first = monitor.process(event)
    second = monitor.process(_pane_event())

    assert first["accepted"] is True
    assert second == {"accepted": False, "duplicate": True, "event_id": event.event_id}
    assert lane.calls == ["project:codex"]


def test_historical_pane_event_is_recorded_but_not_reclassified(store):
    _dispatch(store, "track_1", "task_1", "project:codex")
    lane = FakeLaneAdapter()
    monitor = _monitor(store, lane=lane)

    result = monitor.process(
        _pane_event(observed_at="2000-01-01T00:00:00+00:00")
    )

    assert result["accepted"] is True
    assert result["ignored"] == "stale_event"
    assert lane.calls == []
    assert list(RuntimeEventLedger(store).iter_events())[0].payload["ignored_reason"] == "stale_event"


def test_terminal_task_pane_event_does_not_reclassify(store):
    _dispatch(
        store,
        "track_1",
        "task_1",
        "project:codex",
        state=TaskState.COMPLETE,
    )
    lane = FakeLaneAdapter()
    result = _monitor(store, lane=lane).process(_pane_event())

    assert result["ignored"] == "terminal_task"
    assert lane.calls == []


def test_result_artifact_event_invokes_existing_verifier_only(store):
    record = _dispatch(store, "track_1", "task_1", "project:codex")
    result_path = store.task_result_path(record.track_id, record.task_id)
    result_path.write_text("TASK_COMPLETE\n", encoding="utf-8")
    completion = FakeCompletionEngine()
    monitor = _monitor(store, completion=completion)
    event = RuntimeEvent(
        source="fs_artifact",
        source_key="result:one",
        kind=RuntimeEventKind.ARTIFACT_CREATED,
        observed_at="2099-01-01T00:00:00+00:00",
        track_id=record.track_id,
        task_id=record.task_id,
        evidence_ref=str(result_path),
        payload={"artifact": "result.md", "path": str(result_path)},
    )

    processed = monitor.process(event)

    assert processed["verification_requested"] is True
    assert completion.calls == [record.track_id]


def test_workspace_mismatch_is_recorded_as_unresolved_evidence(store):
    _dispatch(store, "track_1", "task_1", "project:codex")
    lane = FakeLaneAdapter()
    monitor = _monitor(store, lane=lane)

    result = monitor.process(_pane_event(worktree_path="/wrong/worktree"))

    assert result["accepted"] is True
    assert result["unresolved"] == "workspace_provenance_mismatch"
    event = list(RuntimeEventLedger(store).iter_events())[0]
    assert event.kind is RuntimeEventKind.WORKSPACE_PROVENANCE_MISMATCH
    assert event.confidence == "unresolved"
    assert Path(result["unresolved_ref"]).exists()
    assert lane.calls == []


def test_unknown_lane_is_recorded_as_unresolved_event(store):
    monitor = _monitor(store)

    result = monitor.process(_pane_event(lane_target="project:missing"))

    assert result["unresolved"] == "unresolved_event"
    event = list(RuntimeEventLedger(store).iter_events())[0]
    assert event.kind is RuntimeEventKind.UNRESOLVED_EVENT
    assert event.payload["reason"] == "no matching active dispatch"


def test_gap_event_runs_one_bounded_reconciliation(store):
    _dispatch(store, "track_1", "task_1", "project:codex")
    _dispatch(store, "track_1", "task_2", "project:claude")
    lane = FakeLaneAdapter()
    monitor = _monitor(store, lane=lane)
    gap = RuntimeEvent(
        source="tmux_control:project",
        source_key="gap:disconnect:one",
        kind=RuntimeEventKind.EVENT_STREAM_GAP,
        payload={"reason": "control client disconnected"},
    )

    first = monitor.process(gap)
    second = monitor.process(RuntimeEvent.from_dict(gap.to_dict()))

    assert first["reconciled"] is True
    assert second["duplicate"] is True
    assert lane.calls == ["project:codex", "project:claude"]
    reconciliations = [
        event
        for event in RuntimeEventLedger(store).iter_events()
        if event.kind is RuntimeEventKind.RECONCILIATION
    ]
    assert len(reconciliations) == 1
    assert reconciliations[0].payload["lanes_checked"] == 2


def test_blocked_prompt_projection_uses_fresh_ledger_evidence(store):
    record = _dispatch(store, "track_1", "task_1", "project:codex")
    lane = FakeLaneAdapter({record.lane_target: LaneState.BLOCKED_PROMPT.value})
    _monitor(store, lane=lane).process(_pane_event())

    blocked = active_blocked_prompts(store, record.track_id)

    assert [item["task_id"] for item in blocked] == [record.task_id]
    assert blocked[0]["lane_state"] == LaneState.BLOCKED_PROMPT.value
    assert blocked[0]["event_id"]
    assert lane.calls == [record.lane_target]
