"""Closed fix loop: archive → bounded fix → deliver → converge → escalate."""

import json

import pytest

from conductor.cli import main
from conductor.completion import CompletionEngine, auto_fix_failed_tasks
from conductor.dispatch import Dispatcher
from conductor.intake import approve_plan, create_planned_track
from conductor.lanes import LaneAdapter
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


READY_CLAUDE_T = "│ > type │\n? for shortcuts"


@pytest.fixture()
def store(tmp_path):
    return ConductorStore.resolve(root=tmp_path, create=True)


def _setup(store, tmux=None):
    """Approved track, dispatched first task, failing verification command."""
    rec = create_planned_track(store, "goal")
    tid = rec.track.track_id
    approve_plan(store, tid)
    lane = LaneAdapter(store, tmux=tmux or FakeTmux(capture_ok=False))
    disp = Dispatcher(store, lane_adapter=lane, git=FakeGit(), default_session="proj")
    task_id = disp.dispatch(tid)["dispatched"][0]["task_id"]
    drec = store.read_dispatch_record(tid, task_id)
    drec.verification_commands = ["python -c 'import sys; sys.exit(1)'"]
    store.write_dispatch_record(drec)
    return tid, task_id, lane


def _write_result(store, tid, task_id, text="TASK_COMPLETE\n"):
    store.task_result_path(tid, task_id).write_text(text, encoding="utf-8")


def test_auto_fix_archives_result_and_opens_fix(store):
    tid, task_id, lane = _setup(store)
    _write_result(store, tid, task_id)

    engine = CompletionEngine(store)
    verified = engine.verify_ready_results(tid)
    assert verified["failed_count"] == 1

    fixes = auto_fix_failed_tasks(engine, lane, tid, verified)
    assert fixes["fixed_count"] == 1
    f = fixes["fixed"][0]
    assert f["fix_attempt"] == 1
    assert f["delivered"] is False  # lane absent -> pending, never unsafe

    # Failing result archived; fix artifact exists.
    task_dir = store.task_dir(tid, task_id)
    assert not store.task_result_path(tid, task_id).exists()
    assert (task_dir / "result-attempt-1.md").exists()
    assert (task_dir / "fixes" / "fix-1.md").exists()

    # Next verify tick skips (no fresh result) -> attempts are NOT burned.
    second = engine.verify_ready_results(tid)
    assert second["failed_count"] == 0
    assert any(s["reason"] == "result_artifact_missing" for s in second["skipped"])
    assert store.read_dispatch_record(tid, task_id).fix_attempts == 1


def test_fresh_result_reenters_verification_and_can_pass(store):
    tid, task_id, lane = _setup(store)
    _write_result(store, tid, task_id)
    engine = CompletionEngine(store)
    fixes = auto_fix_failed_tasks(engine, lane, tid, engine.verify_ready_results(tid))
    assert fixes["fixed_count"] == 1

    # Worker fixes the problem: fresh result + passing command.
    drec = store.read_dispatch_record(tid, task_id)
    drec.verification_commands = ["python -c 'import sys; sys.exit(0)'"]
    store.write_dispatch_record(drec)
    _write_result(store, tid, task_id, "fixed for real\n")

    verified = engine.verify_ready_results(tid)
    assert verified["verified_count"] == 1
    assert verified["results"][0]["task_state"] == "ready_for_merge"


def test_exhausted_attempts_escalate_without_new_fix(store):
    tid, task_id, lane = _setup(store)
    engine = CompletionEngine(store)

    for n in (1, 2, 3):
        _write_result(store, tid, task_id, f"attempt {n}\n")
        verified = engine.verify_ready_results(tid)
        fixes = auto_fix_failed_tasks(engine, lane, tid, verified)
        assert fixes["fixed_count"] == 1

    # Fourth failing result: attempts exhausted -> escalation, no fix-4.md.
    _write_result(store, tid, task_id, "attempt 4\n")
    verified = engine.verify_ready_results(tid)
    fixes = auto_fix_failed_tasks(engine, lane, tid, verified)
    assert fixes["fixed_count"] == 0
    assert fixes["exhausted_count"] == 1
    assert not (store.task_dir(tid, task_id) / "fixes" / "fix-4.md").exists()

    drec = store.read_dispatch_record(tid, task_id)
    assert drec.blocker and "exhausted" in drec.blocker
    events = read_jsonl(store.events_path)
    assert any(e.get("event") == "fix_attempts_exhausted" for e in events)


def test_delivery_when_lane_ready_references_artifact_only(store):
    tmux = FakeTmux(transcript=READY_CLAUDE_T)
    tid, task_id, lane = _setup(store, tmux=tmux)
    _write_result(store, tid, task_id, "SECRET WORKER OUTPUT\n")
    engine = CompletionEngine(store)
    sends_before = len(tmux.sent)

    fixes = auto_fix_failed_tasks(engine, lane, tid, engine.verify_ready_results(tid))
    f = fixes["fixed"][0]
    assert f["delivered"] is True
    assert len(tmux.sent) == sends_before + 1
    sent_text = tmux.sent[-1][1]
    assert "fix-1.md" in sent_text
    assert "SECRET WORKER OUTPUT" not in sent_text  # reference only, never bodies


# --------------------------------------------------------------------------- #
# CLI loop integration
# --------------------------------------------------------------------------- #
def _run(capsys, *argv):
    code = main(list(argv))
    out = capsys.readouterr().out
    try:
        return code, (json.loads(out) if out.strip() else None)
    except json.JSONDecodeError:
        return code, None


def _cli_setup(tmp_path, capsys):
    root = ["--root", str(tmp_path)]
    _run(capsys, *root, "init")
    tid = _run(capsys, *root, "go", "--plan-only", "goal", "--json")[1]["track_id"]
    _run(capsys, *root, "approve", "plan", "--track", tid, "--json")
    task_id = _run(capsys, *root, "dispatch", "--track", tid, "--json")[1]["dispatched"][0]["task_id"]
    _run(capsys, *root, "task", "set-verify", "--track", tid, "--task", task_id,
         "--command", "python -c 'import sys; sys.exit(1)'", "--json")
    return root, tid, task_id


def test_loop_tick_auto_fixes_failed_verification(tmp_path, capsys):
    root, tid, task_id = _cli_setup(tmp_path, capsys)
    store = ConductorStore.resolve(root=tmp_path, create=False)
    store.task_result_path(tid, task_id).write_text("claim\n")

    code, data = _run(capsys, *root, "loop", "--track", tid, "--json")
    assert code == 0
    cycle = data["cycles"][0]
    assert cycle["verified"]["failed_count"] == 1
    assert cycle["fixes"]["fixed_count"] == 1
    assert store.read_dispatch_record(tid, task_id).fix_attempts == 1
    assert (store.task_dir(tid, task_id) / "result-attempt-1.md").exists()


def test_loop_no_auto_fix_flag_disables(tmp_path, capsys):
    root, tid, task_id = _cli_setup(tmp_path, capsys)
    store = ConductorStore.resolve(root=tmp_path, create=False)
    store.task_result_path(tid, task_id).write_text("claim\n")

    code, data = _run(capsys, *root, "loop", "--track", tid, "--no-auto-fix", "--json")
    assert code == 0
    assert data["cycles"][0]["fixes"] is None
    assert store.read_dispatch_record(tid, task_id).fix_attempts == 0
    assert store.task_result_path(tid, task_id).exists()  # untouched
