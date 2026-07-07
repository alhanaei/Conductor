"""Worker self-reporting protocol + multi-window lane pool allocation."""

import json

import pytest

from conductor.cli import main
from conductor.dispatch import Dispatcher
from conductor.intake import approve_plan, create_planned_track
from conductor.lanes import LaneAdapter, parse_target
from conductor.models import DispatchState, TaskState
from conductor.store import ConductorStore, read_jsonl


class FakeTmux:
    def __init__(self, transcript="", capture_ok=True):
        self.transcript = transcript
        self.capture_ok = capture_ok
        self.sent = []

    def available(self):
        return True

    def capture(self, target, lines=200):
        return (self.capture_ok, self.transcript if self.capture_ok else "")

    def send_text(self, target, text):
        self.sent.append((target, text))
        return True

    def send_enter(self, target):
        return True

    def ensure(self, session, window):
        return True


class FakeGit:
    def available(self):
        return True

    def is_repo(self, path):
        return False

    def add_worktree(self, repo, worktree_path, branch):
        return True


READY_T = "│ > type │\n? for shortcuts"


@pytest.fixture()
def store(tmp_path):
    return ConductorStore.resolve(root=tmp_path, create=True)


def _dispatcher(store, tmux=None):
    lane = LaneAdapter(store, tmux=tmux or FakeTmux(capture_ok=False))
    return Dispatcher(store, lane_adapter=lane, git=FakeGit(), default_session="proj")


# --------------------------------------------------------------------------- #
# Lane pool: provider suffix parsing
# --------------------------------------------------------------------------- #
def test_pool_window_maps_to_base_provider():
    assert parse_target("proj:claude-2").provider == "claude"
    assert parse_target("proj:codex-3").provider == "codex"
    assert parse_target("proj:claude").provider == "claude"
    # non-numeric suffixes are not pool lanes
    assert parse_target("proj:claude-x").provider is None


# --------------------------------------------------------------------------- #
# Lane pool: allocation
# --------------------------------------------------------------------------- #
def _two_parallel_ready_tasks(store):
    """Create a track whose first two tasks are READY with the same provider."""
    rec = create_planned_track(store, "goal")
    tid = rec.track.track_id
    approve_plan(store, tid)

    def mutate(record):
        # Make the second task independent + READY, same kind as the first
        # (clarify -> claude) so both route to the claude pool.
        second = record.tasks[1]
        second.title = "Clarify secondary requirements"
        second.dependencies = []
        second.state = TaskState.READY

    store.update_track_record(tid, mutate)
    return tid


def test_parallel_tasks_get_distinct_pool_lanes(store):
    tid = _two_parallel_ready_tasks(store)
    dispatcher = _dispatcher(store)
    result = dispatcher.dispatch(tid)
    assert result["dispatched_count"] == 2
    lanes = [t["lane_target"] for t in result["dispatched"]]
    assert lanes[0] != lanes[1]
    assert set(lanes) == {"proj:claude", "proj:claude-2"}


def test_pool_exhaustion_queues_instead_of_double_submitting(store, tmp_path):
    # Shrink the pool to 1 so the second task exhausts it.
    import json as _json
    config = _json.loads(store.config_path.read_text())
    config["lane_pool_size"] = 1
    store.config_path.write_text(_json.dumps(config))

    tid = _two_parallel_ready_tasks(store)
    tmux = FakeTmux(transcript=READY_T)  # lane ready: first task submits
    dispatcher = _dispatcher(store, tmux=tmux)
    result = dispatcher.dispatch(tid)

    states = {t["task_id"]: t for t in result["dispatched"]}
    submitted = [t for t in states.values() if t["dispatch_state"] == "submitted"]
    queued = [t for t in states.values() if t["lane_target"] is None]
    assert len(submitted) == 1
    assert len(queued) == 1
    assert "pool exhausted" in queued[0]["blocker"]
    # Only ONE submission reached tmux — no double-submit into the same pane.
    task_submissions = [s for s in tmux.sent if "task.md" in s[1]]
    assert len(task_submissions) == 1


def test_pending_lane_task_is_resubmitted_when_lane_becomes_ready(store):
    rec = create_planned_track(store, "goal")
    tid = rec.track.track_id
    approve_plan(store, tid)

    absent = FakeTmux(capture_ok=False)
    dispatcher = _dispatcher(store, tmux=absent)
    first = dispatcher.dispatch(tid)
    task_id = first["dispatched"][0]["task_id"]
    assert first["dispatched"][0]["dispatch_state"] == "pending_lane"

    # Lane comes up: the next dispatch tick resubmits the pending task.
    ready = FakeTmux(transcript=READY_T)
    dispatcher2 = _dispatcher(store, tmux=ready)
    second = dispatcher2.dispatch(tid)
    assert second["resubmitted_count"] == 1
    assert second["resubmitted"][0]["task_id"] == task_id

    drec = store.read_dispatch_record(tid, task_id)
    assert drec.dispatch_state is DispatchState.SUBMITTED
    assert drec.task_state is TaskState.WORKING
    assert any("task.md" in s[1] for s in ready.sent)
    events = read_jsonl(store.events_path)
    assert any(e.get("event") == "task_resubmitted" for e in events)


def test_ready_for_review_frees_the_lane(store):
    tid = _two_parallel_ready_tasks(store)
    import json as _json
    config = _json.loads(store.config_path.read_text())
    config["lane_pool_size"] = 1
    store.config_path.write_text(_json.dumps(config))

    dispatcher = _dispatcher(store, tmux=FakeTmux(transcript=READY_T))
    result = dispatcher.dispatch(tid)
    holder = next(t for t in result["dispatched"] if t["lane_target"])
    # Holder claims completion -> lane freed for the queued task on retry.
    drec = store.read_dispatch_record(tid, holder["task_id"])
    drec.task_state = TaskState.READY_FOR_REVIEW
    store.write_dispatch_record(drec)

    second = dispatcher.dispatch(tid)
    assert second["resubmitted_count"] == 1


# --------------------------------------------------------------------------- #
# Worker protocol CLI
# --------------------------------------------------------------------------- #
def _run(capsys, *argv):
    code = main(list(argv))
    out = capsys.readouterr().out
    try:
        return code, (json.loads(out) if out.strip() else None)
    except json.JSONDecodeError:
        return code, None


def _cli_dispatched(tmp_path, capsys):
    root = ["--root", str(tmp_path)]
    _run(capsys, *root, "init")
    tid = _run(capsys, *root, "go", "--plan-only", "goal", "--json")[1]["track_id"]
    _run(capsys, *root, "approve", "plan", "--track", tid, "--json")
    task_id = _run(capsys, *root, "dispatch", "--track", tid, "--json")[1]["dispatched"][0]["task_id"]
    return root, tid, task_id


def test_worker_beat_updates_heartbeat_and_bus(tmp_path, capsys):
    root, tid, task_id = _cli_dispatched(tmp_path, capsys)
    store = ConductorStore.resolve(root=tmp_path, create=False)
    before = store.read_dispatch_record(tid, task_id).heartbeat_at

    code, data = _run(capsys, *root, "worker", "beat", "--track", tid,
                      "--task", task_id, "--worker", "w1", "--note", "halfway", "--json")
    assert code == 0
    assert data["heartbeat_at"] >= before

    from conductor.message_bus import MessageBus
    from conductor.models import MessageType
    msgs = MessageBus(store, tid).list_messages(type=MessageType.HEARTBEAT)
    assert msgs and msgs[-1].sender_id == "w1"
    # worker-status projection reflects the beat
    workers = MessageBus(store, tid).worker_status()["workers"]
    assert workers["w1"]["last_type"] == "HEARTBEAT"


def test_worker_complete_requires_result(tmp_path, capsys):
    root, tid, task_id = _cli_dispatched(tmp_path, capsys)
    code, data = _run(capsys, *root, "worker", "complete", "--track", tid,
                      "--task", task_id, "--worker", "w1", "--json")
    assert code == 1
    assert "result" in data["error"]


def test_worker_complete_is_claim_not_completion(tmp_path, capsys):
    root, tid, task_id = _cli_dispatched(tmp_path, capsys)
    store = ConductorStore.resolve(root=tmp_path, create=False)
    store.task_result_path(tid, task_id).write_text("did the work\n")

    code, data = _run(capsys, *root, "worker", "complete", "--track", tid,
                      "--task", task_id, "--worker", "w1", "--json")
    assert code == 0
    assert data["task_state"] == "ready_for_review"  # NOT complete

    drec = store.read_dispatch_record(tid, task_id)
    assert drec.task_state is TaskState.READY_FOR_REVIEW
    assert drec.verification_status is None  # verification still gates
    record = store.read_track_record(tid)
    task = next(t for t in record.tasks if t.task_id == task_id)
    assert task.state is TaskState.READY_FOR_REVIEW


def test_worker_beat_unknown_task_exits_2(tmp_path, capsys):
    root = ["--root", str(tmp_path)]
    _run(capsys, *root, "init")
    tid = _run(capsys, *root, "go", "--plan-only", "goal", "--json")[1]["track_id"]
    code, data = _run(capsys, *root, "worker", "beat", "--track", tid,
                      "--task", "task_nope", "--worker", "w1", "--json")
    assert code == 2
    assert data["ok"] is False


def test_legacy_dispatch_record_does_not_poison_occupancy_scan(store):
    """A status.json written by an older schema (retired task_state value) in
    one track must not crash dispatch for every other track (found live:
    'awaiting_verification' records from a pre-hardening soak test)."""
    import json as _json

    old = create_planned_track(store, "old soak track")
    legacy_dir = store.task_dir(old.track.track_id, "task_legacy")
    legacy_dir.mkdir(parents=True, exist_ok=True)
    (legacy_dir / "status.json").write_text(_json.dumps({
        "task_id": "task_legacy", "track_id": old.track.track_id,
        "task_state": "awaiting_verification",  # retired enum value
        "lane_target": "proj:claude",
    }))

    tid = _two_parallel_ready_tasks(store)
    result = _dispatcher(store).dispatch(tid)  # must not raise
    assert result["dispatched_count"] == 2
    # The unreadable record is skipped by listing, not surfaced as occupancy.
    assert store.list_dispatch_records(old.track.track_id) == []


def test_worker_complete_never_downgrades_verified_task(tmp_path, capsys):
    """Field race: the loop verified+completed a task before the worker's late
    claim arrived; the claim must not knock it back to ready_for_review."""
    root, tid, task_id = _cli_dispatched(tmp_path, capsys)
    store = ConductorStore.resolve(root=tmp_path, create=False)
    store.task_result_path(tid, task_id).write_text("done\n")

    # Verifier promotes the task all the way to complete.
    from conductor.completion import CompletionEngine
    engine = CompletionEngine(store)
    engine.verify(tid)
    engine.advance_verified(tid)
    assert store.read_dispatch_record(tid, task_id).task_state is TaskState.COMPLETE

    # Late claim arrives.
    code, data = _run(capsys, *root, "worker", "complete", "--track", tid,
                      "--task", task_id, "--worker", "w1", "--json")
    assert code == 0
    assert data["claim_applied"] is False
    assert data["task_state"] == "complete"  # not downgraded
    assert store.read_dispatch_record(tid, task_id).task_state is TaskState.COMPLETE
    record = store.read_track_record(tid)
    task = next(t for t in record.tasks if t.task_id == task_id)
    assert task.state is TaskState.COMPLETE
