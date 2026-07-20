"""Phase 6 operator surface: summary, notify, heartbeat, approval, verify-hook."""

import pytest

import conductor.operator as operator_module
from conductor.completion import CompletionEngine
from conductor.dispatch import Dispatcher
from conductor.intake import approve_plan, create_planned_track
from conductor.lanes import LaneAdapter
from conductor.models import TaskState
from conductor.operator import (
    HEARTBEAT_CADENCE_SECONDS,
    OperatorError,
    OperatorView,
    heartbeat_due,
)
from conductor.store import ConductorStore


class FakeTmux:
    def available(self):
        return True

    def capture(self, target, lines=200):
        return (False, "")  # lane absent -> pending_lane

    def send_text(self, target, text):
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


@pytest.fixture()
def store(tmp_path):
    return ConductorStore.resolve(root=tmp_path, create=True)


def _planned(store, goal="Build a small dashboard"):
    return create_planned_track(store, goal).track.track_id


def _dispatched(store):
    tid = _planned(store)
    approve_plan(store, tid)
    disp = Dispatcher(store, lane_adapter=LaneAdapter(store, tmux=FakeTmux()),
                      git=FakeGit(), default_session="proj")
    task_id = disp.dispatch(tid)["dispatched"][0]["task_id"]
    return tid, task_id


def _write_result(store, tid, task_id):
    store.task_result_path(tid, task_id).write_text("TASK_COMPLETE\n", encoding="utf-8")


def _mark_remaining_tasks_complete(store, tid, except_task_id):
    record = store.read_track_record(tid)
    for task in record.tasks:
        if task.task_id != except_task_id and task.state is TaskState.PENDING:
            task.state = TaskState.COMPLETE
    store.write_track_record(record)


# --------------------------------------------------------------------------- #
# heartbeat_due (pure)
# --------------------------------------------------------------------------- #
def test_heartbeat_first_is_due():
    assert heartbeat_due(None, "2026-01-01T00:00:00+00:00") is True


def test_heartbeat_within_cadence_not_due():
    assert heartbeat_due("2026-01-01T00:00:00+00:00", "2026-01-01T00:03:00+00:00",
                         HEARTBEAT_CADENCE_SECONDS) is False  # 180s < 300s


def test_heartbeat_past_cadence_is_due():
    assert heartbeat_due("2026-01-01T00:00:00+00:00", "2026-01-01T00:05:30+00:00",
                         HEARTBEAT_CADENCE_SECONDS) is True   # 330s >= 300s


def test_heartbeat_terminal_suppressed_unless_forced():
    assert heartbeat_due(None, "2026-01-01T00:00:00+00:00", terminal=True) is False
    assert heartbeat_due(None, "2026-01-01T00:00:00+00:00", terminal=True, force=True) is True


# --------------------------------------------------------------------------- #
# summary
# --------------------------------------------------------------------------- #
def test_summary_telegram_is_bounded_and_grounded(store):
    tid = _planned(store)
    text = OperatorView(store).render_telegram(tid)
    assert tid in text
    assert "plan: pending_review" in text
    assert "next:" in text
    assert "spec.md" in text  # artifact link present
    assert len(text) <= 3500


def test_summary_all_tracks(store):
    _planned(store, "goal one")
    _planned(store, "goal two")
    data = OperatorView(store).summary(None)
    assert data["scope"] == "all"
    assert data["track_count"] == 2


def test_summary_unknown_track_raises(store):
    with pytest.raises(OperatorError):
        OperatorView(store).summary("track_nope")


# --------------------------------------------------------------------------- #
# notify signals
# --------------------------------------------------------------------------- #
def test_notify_needs_approval_when_plan_unapproved(store):
    tid = _planned(store)
    n = OperatorView(store).notify(tid)
    assert n["signal"] == "needs_approval"
    assert n["severity"] == "warning"
    assert "approve plan" in n["next_command"]


def test_notify_needs_verification_after_dispatch(store):
    tid, task_id = _dispatched(store)
    _write_result(store, tid, task_id)
    n = OperatorView(store).notify(tid)
    assert n["signal"] == "needs_verification"
    assert n["task_id"] == task_id
    assert "monitor status" in n["next_command"]
    assert "--watch" not in n["next_command"]


def test_notify_blocked_prompt_when_active_lane_needs_operator_action(store, monkeypatch):
    tid, task_id = _dispatched(store)
    blocked = [{
        "task_id": task_id,
        "title": "Clarify requirements and constraints",
        "lane_target": "proj:claude",
        "provider": "claude",
        "lane_state": "blocked_prompt",
        "result_artifact_ref": str(store.task_result_path(tid, task_id)),
        "operator_action": "approve the prompt in the tmux pane or move this lane to the project-root session",
    }]
    monkeypatch.setattr(operator_module, "active_blocked_prompts", lambda store, track_id: blocked)

    n = OperatorView(store).notify(tid)

    assert n["signal"] == "blocked_prompt"
    assert n["severity"] == "error"
    assert n["blocked_prompts"][0]["task_id"] == task_id
    assert "lane blocked" in n["next_command"]


def test_notify_ready_for_merge_after_verify(store):
    tid, task_id = _dispatched(store)
    _write_result(store, tid, task_id)
    CompletionEngine(store).verify(tid)
    n = OperatorView(store).notify(tid)
    assert n["signal"] == "needs_advance"
    assert n["severity"] == "info"


def test_notify_ready_for_final_merge_when_all_tasks_finalizable(store):
    tid, task_id = _dispatched(store)
    _write_result(store, tid, task_id)
    CompletionEngine(store).verify(tid)
    _mark_remaining_tasks_complete(store, tid, task_id)
    n = OperatorView(store).notify(tid)
    assert n["signal"] == "ready_for_merge"
    assert n["severity"] == "success"


def test_notify_needs_fix_when_verification_fails(store):
    tid, task_id = _dispatched(store)  # no result -> verify fails
    CompletionEngine(store).verify(tid)
    n = OperatorView(store).notify(tid)
    assert n["signal"] == "needs_fix"


def test_notify_closed_signal(store):
    tid, task_id = _dispatched(store)
    _write_result(store, tid, task_id)
    engine = CompletionEngine(store)
    engine.verify(tid)
    _mark_remaining_tasks_complete(store, tid, task_id)
    engine.approve_merge(tid)
    engine.close(tid)
    n = OperatorView(store).notify(tid)
    assert n["signal"] == "closed"
    assert n["severity"] == "success"


def test_notify_dedupe_key_changes_with_state(store):
    tid, task_id = _dispatched(store)
    _write_result(store, tid, task_id)
    before = OperatorView(store).notify(tid)["dedupe_key"]
    CompletionEngine(store).verify(tid)
    after = OperatorView(store).notify(tid)["dedupe_key"]
    assert before != after


# --------------------------------------------------------------------------- #
# approval payloads
# --------------------------------------------------------------------------- #
def test_plan_approval_then_not_needed(store):
    tid = _planned(store)
    view = OperatorView(store)
    payload = view.approval(tid, "plan")
    assert payload["needed"] is True
    assert "approve plan" in payload["command"]

    approve_plan(store, tid)
    payload2 = view.approval(tid, "plan")
    assert payload2["needed"] is False
    assert payload2["status"] == "approved"


def test_merge_approval_not_ready_before_verify_then_ready(store):
    tid, task_id = _dispatched(store)
    _write_result(store, tid, task_id)
    view = OperatorView(store)

    before = view.approval(tid, "merge")
    assert before["needed"] is True
    assert before["ready"] is False
    assert "verify" in before["blocking_command"]

    CompletionEngine(store).verify(tid)
    after = view.approval(tid, "merge")
    assert after["ready"] is False
    assert "loop" in after["blocking_command"]

    _mark_remaining_tasks_complete(store, tid, task_id)
    after = view.approval(tid, "merge")
    assert after["ready"] is True
    assert any(e["verification_status"] == "passed" for e in after["verification_evidence"])


# --------------------------------------------------------------------------- #
# verify-hook
# --------------------------------------------------------------------------- #
def test_verify_hook_before_verification_includes_verify(store):
    tid, task_id = _dispatched(store)
    _write_result(store, tid, task_id)
    hook = OperatorView(store).verify_hook(tid)
    cmds = [c["command"] for c in hook["commands"]]
    assert any("conductor loop --track" in c and "--watch" not in c for c in cmds)


def test_verify_hook_after_close_includes_reconcile_and_summary(store):
    tid, task_id = _dispatched(store)
    _write_result(store, tid, task_id)
    engine = CompletionEngine(store)
    engine.verify(tid)
    _mark_remaining_tasks_complete(store, tid, task_id)
    engine.approve_merge(tid)
    engine.close(tid)
    hook = OperatorView(store).verify_hook(tid)
    cmds = " ".join(c["command"] for c in hook["commands"])
    assert "reconcile" in cmds
    assert "operator summary" in cmds


def test_verify_hook_merge_suggestion_is_auto_run_under_delegated_authority(store):
    tid, task_id = _dispatched(store)
    _write_result(store, tid, task_id)
    CompletionEngine(store).verify(tid)  # verified but downstream tasks remain
    hook = OperatorView(store).verify_hook(tid)
    loop_cmd = next(c for c in hook["commands"] if "loop" in c["command"])
    assert "--watch" not in loop_cmd["command"]
    assert loop_cmd["auto_run"] is True

    _mark_remaining_tasks_complete(store, tid, task_id)
    hook = OperatorView(store).verify_hook(tid)
    merge_cmd = next(c for c in hook["commands"] if "approve merge" in c["command"])
    assert merge_cmd["auto_run"] is True


# --------------------------------------------------------------------------- #
# heartbeat command (integration with persistence)
# --------------------------------------------------------------------------- #
def test_heartbeat_command_due_then_not_due(store):
    tid = _planned(store)
    view = OperatorView(store)
    first = view.heartbeat(tid, now="2026-06-29T12:00:00Z")
    assert first["due"] is True
    # 100s later -> within cadence -> not due
    second = view.heartbeat(tid, now="2026-06-29T12:01:40Z")
    assert second["due"] is False
    # 6 minutes after the first -> due again
    third = view.heartbeat(tid, now="2026-06-29T12:06:30Z")
    assert third["due"] is True


def test_heartbeat_no_change_body(store):
    tid = _planned(store)
    view = OperatorView(store)
    view.heartbeat(tid, now="2026-06-29T12:00:00Z")
    # state unchanged, past cadence -> due with 'no change'
    again = view.heartbeat(tid, now="2026-06-29T12:10:00Z")
    assert again["due"] is True
    assert again["body"] == "no change"
