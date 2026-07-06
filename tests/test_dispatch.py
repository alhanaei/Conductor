"""Phase 4 dispatch: routing, worktree policy, stale-risk, artifacts, safety."""

import pytest

from conductor.dispatch import (
    Dispatcher,
    DispatchError,
    classify_stale_risk,
    infer_kind,
    provider_for_kind,
)
from conductor.intake import approve_plan, create_planned_track
from conductor.lanes import LaneAdapter
from conductor.models import (
    DispatchState,
    LaneState,
    StaleRisk,
    TaskState,
)
from conductor.store import ConductorStore, read_jsonl
from conductor.worktree import allocate_worktree, branch_name, slugify


# --------------------------------------------------------------------------- #
# Fakes
# --------------------------------------------------------------------------- #
class FakeTmux:
    def __init__(self, available=True, transcript="", capture_ok=True):
        self._available = available
        self.transcript = transcript
        self.capture_ok = capture_ok
        self.sent = []
        self.entered = 0

    def available(self):
        return self._available

    def capture(self, target, lines=200):
        return (self.capture_ok, self.transcript if self.capture_ok else "")

    def send_text(self, target, text):
        self.sent.append((target, text))
        return True

    def send_enter(self, target):
        self.entered += 1
        return True

    def ensure(self, session, window):
        return True


class FakeGit:
    def __init__(self, is_repo=False, add_ok=True):
        self._is_repo = is_repo
        self.add_ok = add_ok
        self.added = []

    def available(self):
        return True

    def is_repo(self, path):
        return self._is_repo

    def add_worktree(self, repo, worktree_path, branch):
        self.added.append((repo, worktree_path, branch))
        return self.add_ok


READY_CLAUDE_T = "│ > type here │\n? for shortcuts"


@pytest.fixture()
def store(tmp_path):
    return ConductorStore.resolve(root=tmp_path, create=True)


def _approved_track(store):
    rec = create_planned_track(store, "Build a small dashboard")
    approve_plan(store, rec.track.track_id)
    return rec.track.track_id


def _dispatcher(store, tmux=None, git=None):
    lane = LaneAdapter(store, tmux=tmux or FakeTmux(capture_ok=False))
    return Dispatcher(store, lane_adapter=lane, git=git or FakeGit(is_repo=False),
                      default_session="proj")


# --------------------------------------------------------------------------- #
# Routing policy
# --------------------------------------------------------------------------- #
def test_infer_kind_and_provider():
    assert infer_kind("Clarify requirements and constraints") == "clarify"
    assert infer_kind("Design approach, interfaces, and file surfaces") == "design"
    assert infer_kind("Implement the solution") == "implement"
    assert infer_kind("Add tests and verify behavior") == "test"
    assert infer_kind("Review, document, and finalize") == "review"
    assert infer_kind("something else") == "general"
    assert provider_for_kind("implement") == "codex"
    assert provider_for_kind("clarify") == "claude"
    assert provider_for_kind("review") == "claude"


# --------------------------------------------------------------------------- #
# Branch naming + worktree policy
# --------------------------------------------------------------------------- #
def test_branch_name_is_deterministic_and_safe():
    b1 = branch_name("track_1", "task_9", "Implement the Solution!!")
    b2 = branch_name("track_1", "task_9", "Implement the Solution!!")
    assert b1 == b2
    assert b1 == "conductor/track_1/task_9-implement-the-solution"
    assert " " not in b1


def test_slugify_handles_empty():
    assert slugify("") == "task"
    assert slugify("A B/C") == "a-b-c"


def test_allocate_worktree_non_git_degrades(tmp_path):
    alloc = allocate_worktree(tmp_path, "t1", "k1", "title", git=FakeGit(is_repo=False))
    assert alloc.mode.value == "not_git_repo"
    assert alloc.is_git_repo is False
    assert alloc.workspace == str(tmp_path)
    assert alloc.worktree_path is None
    assert alloc.branch.startswith("conductor/t1/k1-")


def test_allocate_worktree_git_planned(tmp_path):
    git = FakeGit(is_repo=True)
    alloc = allocate_worktree(tmp_path, "t1", "k1", "title", git=git, create=False)
    assert alloc.mode.value == "git_planned"
    assert alloc.worktree_path is not None
    assert git.added == []  # planning does not mutate


def test_allocate_worktree_git_create(tmp_path):
    git = FakeGit(is_repo=True, add_ok=True)
    alloc = allocate_worktree(tmp_path, "t1", "k1", "title", git=git, create=True)
    assert alloc.mode.value == "git_worktree"
    assert len(git.added) == 1


# --------------------------------------------------------------------------- #
# Stale-risk classifier
# --------------------------------------------------------------------------- #
def test_stale_risk_fresh_is_none():
    now = "2026-01-01T00:00:10+00:00"
    assert classify_stale_risk("2026-01-01T00:00:00+00:00", now) is StaleRisk.NONE


def test_stale_risk_grows_with_age():
    base = "2026-01-01T00:00:00+00:00"
    assert classify_stale_risk(base, "2026-01-01T00:01:30+00:00") is StaleRisk.LOW      # 90s
    assert classify_stale_risk(base, "2026-01-01T00:06:00+00:00") is StaleRisk.MEDIUM   # 360s
    assert classify_stale_risk(base, "2026-01-01T00:16:40+00:00") is StaleRisk.HIGH     # 1000s


def test_stale_risk_blocked_lane_is_at_least_medium():
    now = "2026-01-01T00:00:05+00:00"
    assert classify_stale_risk("2026-01-01T00:00:00+00:00", now,
                               dispatch_state=DispatchState.BLOCKED_LANE) is StaleRisk.MEDIUM


def test_stale_risk_absent_submitted_is_high():
    now = "2026-01-01T00:00:05+00:00"
    assert classify_stale_risk("2026-01-01T00:00:00+00:00", now,
                               dispatch_state=DispatchState.SUBMITTED,
                               lane_state=LaneState.ABSENT) is StaleRisk.HIGH


def test_stale_risk_terminal_task_is_none():
    assert classify_stale_risk("2000-01-01T00:00:00+00:00", "2026-01-01T00:00:00+00:00",
                               task_state=TaskState.COMPLETE) is StaleRisk.NONE


# --------------------------------------------------------------------------- #
# Dispatch gate + flow
# --------------------------------------------------------------------------- #
def test_dispatch_refuses_unapproved_plan(store):
    rec = create_planned_track(store, "goal")  # not approved
    dispatcher = _dispatcher(store)
    with pytest.raises(DispatchError):
        dispatcher.dispatch(rec.track.track_id)


def test_dispatch_writes_artifacts_and_status_when_lane_absent(store, tmp_path):
    tid = _approved_track(store)
    fake = FakeTmux(capture_ok=False)  # lane absent
    dispatcher = _dispatcher(store, tmux=fake)
    result = dispatcher.dispatch(tid)

    assert result["dispatched_count"] == 1
    t = result["dispatched"][0]
    assert t["dispatch_state"] == "pending_lane"   # not a failure
    assert t["task_state"] == "dispatched"
    assert t["worktree_mode"] == "not_git_repo"
    assert fake.sent == []  # NOTHING submitted to a non-ready lane

    task_id = t["task_id"]
    assert store.task_artifact_path(tid, task_id).exists()
    assert store.task_status_path(tid, task_id).exists()
    assert store.read_route_decision(tid, task_id) is not None

    # task.md references the result path; it is an artifact, not a pasted body
    body = store.task_artifact_path(tid, task_id).read_text()
    assert "## Objective" in body and "result artifact" in body
    assert "## Method Contract" in body
    assert "## Anti-Rationalization Guardrails" in body
    assert "## Definition of Done" in body
    assert "method: spec" in body
    assert "Do not claim completion without command evidence." in body

    # Persisted task state survives a fresh store (restart).
    reloaded = ConductorStore.resolve(root=tmp_path, create=False)
    rec = reloaded.read_track_record(tid)
    dispatched_task = next(t for t in rec.tasks if t.task_id == task_id)
    assert dispatched_task.state is TaskState.DISPATCHED


def test_dispatch_submits_short_reference_when_ready(store):
    tid = _approved_track(store)
    fake = FakeTmux(transcript=READY_CLAUDE_T)  # provider_ready
    dispatcher = _dispatcher(store, tmux=fake)
    result = dispatcher.dispatch(tid)

    t = result["dispatched"][0]
    assert t["dispatch_state"] == "submitted"
    assert t["task_state"] == "working"
    # Exactly one literal send, and it references the task.md path, not file bodies.
    assert len(fake.sent) == 1
    sent_text = fake.sent[0][1]
    assert "task.md" in sent_text
    assert "Build a small dashboard" not in sent_text  # no plan/goal body pasted


def test_dispatch_only_first_ready_task(store):
    tid = _approved_track(store)
    dispatcher = _dispatcher(store)
    result = dispatcher.dispatch(tid)
    assert result["dispatched_count"] == 1  # chain DAG: only the first task is READY


def test_dispatch_records_route_decision_fields(store):
    tid = _approved_track(store)
    dispatcher = _dispatcher(store)
    result = dispatcher.dispatch(tid)
    task_id = result["dispatched"][0]["task_id"]
    route = store.read_route_decision(tid, task_id)
    assert route.chosen_lane == "proj:claude"   # clarify -> claude
    assert route.task_type == "clarify"
    assert route.candidates == ["proj:claude"]


def test_dispatch_persists_method_metadata(store):
    tid = _approved_track(store)
    dispatcher = _dispatcher(store)
    result = dispatcher.dispatch(tid)
    task_id = result["dispatched"][0]["task_id"]

    drec = store.read_dispatch_record(tid, task_id)
    assert drec.method_id == "spec"
    assert drec.autonomy_policy == "stop_on_ambiguity"
    assert drec.definition_of_done_refs == ["definition_of_done.md"]


# --------------------------------------------------------------------------- #
# task status / followup / nudge
# --------------------------------------------------------------------------- #
def test_task_status_returns_expected_fields(store):
    tid = _approved_track(store)
    dispatcher = _dispatcher(store)
    task_id = dispatcher.dispatch(tid)["dispatched"][0]["task_id"]

    status = dispatcher.task_status(tid, task_id)
    for key in ("task_state", "dispatch_state", "lane_state", "worktree_mode",
                "branch", "stale_risk", "route", "blocker", "heartbeat_at"):
        assert key in status
    assert status["dispatched"] is True
    assert status["route"] is not None


def test_followup_writes_artifact_and_does_not_paste_body(store, tmp_path):
    tid = _approved_track(store)
    dispatcher = _dispatcher(store, tmux=FakeTmux(capture_ok=False))
    task_id = dispatcher.dispatch(tid)["dispatched"][0]["task_id"]

    body = tmp_path / "fu.md"
    body.write_text("LONG FOLLOW-UP BODY that must not be pasted")
    result = dispatcher.followup(tid, task_id, str(body))

    assert result["pasted_body"] is False
    assert result["delivered"] is False  # lane absent
    from pathlib import Path
    assert Path(result["artifact_ref"]).exists()
    assert "LONG FOLLOW-UP BODY" in Path(result["artifact_ref"]).read_text()

    events = read_jsonl(store.events_path)
    assert any(e.get("event") == "task_followup" for e in events)


def test_followup_delivers_short_reference_when_ready(store, tmp_path):
    tid = _approved_track(store)
    fake = FakeTmux(transcript=READY_CLAUDE_T)
    dispatcher = _dispatcher(store, tmux=fake)
    task_id = dispatcher.dispatch(tid)["dispatched"][0]["task_id"]
    sends_before = len(fake.sent)

    body = tmp_path / "fu.md"
    body.write_text("SECRET FOLLOWUP BODY")
    result = dispatcher.followup(tid, task_id, str(body))
    assert result["delivered"] is True
    # A new short instruction was sent that references the artifact, not its body.
    assert len(fake.sent) == sends_before + 1
    assert "SECRET FOLLOWUP BODY" not in fake.sent[-1][1]


def test_nudge_pending_when_lane_absent(store):
    tid = _approved_track(store)
    dispatcher = _dispatcher(store, tmux=FakeTmux(capture_ok=False))
    task_id = dispatcher.dispatch(tid)["dispatched"][0]["task_id"]
    result = dispatcher.nudge(tid, task_id)
    assert result["sent"] is False
    events = read_jsonl(store.events_path)
    assert any(e.get("event") == "task_nudge_pending" for e in events)


def test_nudge_sends_when_ready(store):
    tid = _approved_track(store)
    fake = FakeTmux(transcript=READY_CLAUDE_T)
    dispatcher = _dispatcher(store, tmux=fake)
    task_id = dispatcher.dispatch(tid)["dispatched"][0]["task_id"]
    result = dispatcher.nudge(tid, task_id)
    assert result["sent"] is True


def test_followup_requires_dispatch(store):
    tid = _approved_track(store)
    dispatcher = _dispatcher(store)
    with pytest.raises(DispatchError):
        dispatcher.nudge(tid, "task_never_dispatched")
