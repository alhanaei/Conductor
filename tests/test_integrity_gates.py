"""Integrity gates: diff scope, test integrity, review verdict → merge gate."""

import json
import subprocess

import pytest

from conductor.cli import main
from conductor.completion import CompletionEngine, CompletionError
from conductor.dispatch import Dispatcher
from conductor.intake import approve_plan, create_planned_track
from conductor.integrity import (
    check_diff_scope,
    check_review_verdict,
    check_test_integrity,
    read_verdict,
)
from conductor.lanes import LaneAdapter
from conductor.models import TaskState
from conductor.store import ConductorStore
from conductor.worktree import GitClient


class FakeTmux:
    def available(self):
        return True

    def capture(self, target, lines=200):
        return (False, "")

    def send_text(self, target, text):
        return True

    def send_enter(self, target):
        return True

    def ensure(self, session, window):
        return True


# --------------------------------------------------------------------------- #
# Pure gate: diff scope
# --------------------------------------------------------------------------- #
def test_diff_scope_skips_when_unmeasurable():
    check = check_diff_scope(None, ["src/**"])
    assert check["passed"] is True
    assert "skipped" in check["detail"]


def test_diff_scope_no_scope_reports_evidence():
    check = check_diff_scope(["src/a.py", "docs/b.md"], [])
    assert check["passed"] is True
    assert check["changed_files"] == ["src/a.py", "docs/b.md"]
    assert "no scope declared" in check["detail"]


def test_diff_scope_enforces_globs():
    ok = check_diff_scope(["src/conductor/a.py"], ["src/conductor/**"])
    assert ok["passed"] is True
    bad = check_diff_scope(["src/conductor/a.py", "README.md"], ["src/conductor/**"])
    assert bad["passed"] is False
    assert bad["out_of_scope"] == ["README.md"]


def test_diff_scope_ignores_conductor_artifacts():
    check = check_diff_scope(
        [".conductor/tracks/t/tasks/k/result.md", ".hermes/dispatcher/x.json"],
        ["src/**"])
    assert check["passed"] is True
    assert check["changed_files"] == []


# --------------------------------------------------------------------------- #
# Pure gate: test integrity
# --------------------------------------------------------------------------- #
def test_test_integrity_build_task_touching_tests_fails():
    check = check_test_integrity(["tests/test_x.py"], [], "build")
    assert check["passed"] is False
    assert check["test_files_modified"] == ["tests/test_x.py"]


def test_test_integrity_test_method_exempt():
    check = check_test_integrity(["tests/test_x.py"], [], "test")
    assert check["passed"] is True


def test_test_integrity_scope_grant_allows():
    check = check_test_integrity(["tests/test_x.py"], ["tests/**"], "build")
    assert check["passed"] is True


def test_test_integrity_detects_common_patterns():
    for path in ["tests/test_a.py", "test/unit.py", "src/foo_test.go",
                 "app/button.test.tsx", "spec/user.spec.rb", "test_main.py"]:
        check = check_test_integrity([path], [], "build")
        assert check["passed"] is False, path


def test_test_integrity_skips_and_config_patterns():
    assert check_test_integrity(None, [], "build")["passed"] is True
    cfg = {"test_file_patterns": ["checks/**"]}
    assert check_test_integrity(["checks/x.py"], [], "build", cfg)["passed"] is False
    assert check_test_integrity(["tests/test_x.py"], [], "build", cfg)["passed"] is True


# --------------------------------------------------------------------------- #
# Pure gate: review verdict
# --------------------------------------------------------------------------- #
def test_read_verdict_states(tmp_path):
    p = tmp_path / "verdict.json"
    assert read_verdict(p)["present"] is False

    p.write_text("not json")
    assert read_verdict(p)["valid"] is False

    p.write_text(json.dumps({"verdict": "maybe"}))
    assert read_verdict(p)["valid"] is False

    p.write_text(json.dumps({"verdict": "reject", "blockers": ["missing tests"]}))
    v = read_verdict(p)
    assert v["valid"] is True and v["verdict"] == "reject"
    assert v["blockers"] == ["missing tests"]


def test_check_review_verdict_passes_on_either_value(tmp_path):
    p = tmp_path / "verdict.json"
    assert check_review_verdict(p)["passed"] is False  # missing
    p.write_text(json.dumps({"verdict": "reject", "blockers": ["x"]}))
    assert check_review_verdict(p)["passed"] is True   # reviewer did its job
    p.write_text(json.dumps({"verdict": "approve"}))
    assert check_review_verdict(p)["passed"] is True


# --------------------------------------------------------------------------- #
# GitClient diff helpers (real git)
# --------------------------------------------------------------------------- #
def _git(repo, *args):
    subprocess.run(["git", *args], cwd=str(repo), check=True, capture_output=True)


def _make_repo(tmp_path):
    _git(tmp_path, "init", "-b", "main")
    _git(tmp_path, "config", "user.email", "t@t")
    _git(tmp_path, "config", "user.name", "t")
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "app.py").write_text("x = 1\n")
    _git(tmp_path, "add", "-A")
    _git(tmp_path, "commit", "-m", "init")


def test_git_client_changed_files(tmp_path):
    _make_repo(tmp_path)
    git = GitClient()
    baseline = git.head_commit(str(tmp_path))
    assert baseline

    (tmp_path / "src" / "app.py").write_text("x = 2\n")     # modified tracked
    (tmp_path / "new.txt").write_text("hello\n")            # untracked
    changed = git.changed_files(str(tmp_path), baseline)
    assert changed == ["new.txt", "src/app.py"]

    assert git.changed_files(str(tmp_path / "does-not-exist-xyz"), baseline) is None


# --------------------------------------------------------------------------- #
# End-to-end: dispatch baseline → verify gates in a real repo
# --------------------------------------------------------------------------- #
def _dispatched_in_repo(tmp_path):
    _make_repo(tmp_path)
    store = ConductorStore.resolve(root=tmp_path, create=True)
    rec = create_planned_track(store, "goal")
    tid = rec.track.track_id
    approve_plan(store, tid)
    disp = Dispatcher(store, lane_adapter=LaneAdapter(store, tmux=FakeTmux()),
                      default_session="proj")  # real GitClient
    task_id = disp.dispatch(tid)["dispatched"][0]["task_id"]
    return store, tid, task_id


def test_dispatch_records_baseline_commit(tmp_path):
    store, tid, task_id = _dispatched_in_repo(tmp_path)
    drec = store.read_dispatch_record(tid, task_id)
    assert drec.baseline_commit == GitClient().head_commit(str(tmp_path))


def test_verify_fails_out_of_scope_change(tmp_path, capsys):
    store, tid, task_id = _dispatched_in_repo(tmp_path)
    code = main(["--root", str(tmp_path), "task", "set-scope", "--track", tid,
                 "--task", task_id, "--path", "src/**", "--json"])
    capsys.readouterr()
    assert code == 0

    (tmp_path / "README.md").write_text("out of scope\n")
    store.task_result_path(tid, task_id).write_text("done\n")

    result = CompletionEngine(store).verify(tid)
    r = next(x for x in result["results"] if x["task_id"] == task_id)
    assert r["passed"] is False
    gate = store.read_verification(tid, task_id)
    scope_check = next(c for c in gate.checks if c["name"] == "diff_scope")
    assert scope_check["out_of_scope"] == ["README.md"]


def test_verify_passes_in_scope_change(tmp_path, capsys):
    store, tid, task_id = _dispatched_in_repo(tmp_path)
    main(["--root", str(tmp_path), "task", "set-scope", "--track", tid,
          "--task", task_id, "--path", "src/**", "--json"])
    capsys.readouterr()

    (tmp_path / "src" / "app.py").write_text("x = 3\n")
    store.task_result_path(tid, task_id).write_text("done\n")

    result = CompletionEngine(store).verify(tid)
    r = next(x for x in result["results"] if x["task_id"] == task_id)
    assert r["passed"] is True


def test_verify_fails_when_non_test_task_edits_tests(tmp_path):
    store, tid, task_id = _dispatched_in_repo(tmp_path)  # first task: method=spec
    (tmp_path / "tests").mkdir()
    (tmp_path / "tests" / "test_app.py").write_text("assert True\n")
    store.task_result_path(tid, task_id).write_text("done\n")

    result = CompletionEngine(store).verify(tid)
    r = next(x for x in result["results"] if x["task_id"] == task_id)
    assert r["passed"] is False
    gate = store.read_verification(tid, task_id)
    ti = next(c for c in gate.checks if c["name"] == "test_integrity")
    assert ti["passed"] is False


def test_verify_skips_gates_outside_git(tmp_path):
    """Non-git workspaces keep the pre-gate behavior (skip, don't fail)."""
    store = ConductorStore.resolve(root=tmp_path, create=True)
    rec = create_planned_track(store, "goal")
    tid = rec.track.track_id
    approve_plan(store, tid)
    disp = Dispatcher(store, lane_adapter=LaneAdapter(store, tmux=FakeTmux()),
                      default_session="proj")
    task_id = disp.dispatch(tid)["dispatched"][0]["task_id"]
    store.task_result_path(tid, task_id).write_text("done\n")

    result = CompletionEngine(store).verify(tid)
    r = next(x for x in result["results"] if x["task_id"] == task_id)
    assert r["passed"] is True


# --------------------------------------------------------------------------- #
# Review verdict → verification + merge gate
# --------------------------------------------------------------------------- #
def _dispatched_review_task(tmp_path):
    """Track where only the review task is dispatched; others already complete."""
    store = ConductorStore.resolve(root=tmp_path, create=True)
    rec = create_planned_track(store, "goal")
    tid = rec.track.track_id
    approve_plan(store, tid)

    def mutate(record):
        for t in record.tasks:
            if t.method_id == "review":
                t.state = TaskState.READY
                t.dependencies = []
            else:
                t.state = TaskState.COMPLETE

    store.update_track_record(tid, mutate)
    disp = Dispatcher(store, lane_adapter=LaneAdapter(store, tmux=FakeTmux()),
                      default_session="proj")
    task_id = disp.dispatch(tid)["dispatched"][0]["task_id"]
    store.task_result_path(tid, task_id).write_text("review done\n")
    return store, tid, task_id


def test_review_task_verification_requires_verdict(tmp_path):
    store, tid, task_id = _dispatched_review_task(tmp_path)
    result = CompletionEngine(store).verify(tid)
    r = next(x for x in result["results"] if x["task_id"] == task_id)
    assert r["passed"] is False  # result.md alone is not enough for a reviewer

    code = main(["--root", str(tmp_path), "worker", "verdict", "--track", tid,
                 "--task", task_id, "--worker", "w1", "--verdict", "approve", "--json"])
    assert code == 0
    result = CompletionEngine(store).verify(tid)
    r = next(x for x in result["results"] if x["task_id"] == task_id)
    assert r["passed"] is True


def test_reject_verdict_blocks_merge(tmp_path, capsys):
    store, tid, task_id = _dispatched_review_task(tmp_path)
    main(["--root", str(tmp_path), "worker", "verdict", "--track", tid,
          "--task", task_id, "--worker", "w1", "--verdict", "reject",
          "--blocker", "missing error handling", "--json"])
    capsys.readouterr()

    engine = CompletionEngine(store)
    engine.verify(tid)  # verification passes (reviewer did its job)

    with pytest.raises(CompletionError) as exc:
        engine.approve_merge(tid)
    assert "review verdict gate" in str(exc.value)
    assert "missing error handling" in str(exc.value)
    # --force still overrides (operator's prerogative)
    assert engine.approve_merge(tid, force=True)["merge_approved"] is True


def test_approve_verdict_allows_merge(tmp_path, capsys):
    store, tid, task_id = _dispatched_review_task(tmp_path)
    main(["--root", str(tmp_path), "worker", "verdict", "--track", tid,
          "--task", task_id, "--worker", "w1", "--verdict", "approve", "--json"])
    capsys.readouterr()

    engine = CompletionEngine(store)
    engine.verify(tid)
    engine.advance_verified(tid)
    assert engine.approve_merge(tid)["merge_approved"] is True


def test_missing_verdict_blocks_merge_even_if_forced_past_verify(tmp_path):
    store, tid, task_id = _dispatched_review_task(tmp_path)
    engine = CompletionEngine(store)
    engine.verify(tid)  # fails (no verdict) -> needs_fix
    with pytest.raises(CompletionError):
        engine.approve_merge(tid)


# --------------------------------------------------------------------------- #
# CLI: set-scope syncs plan + dispatch record
# --------------------------------------------------------------------------- #
def test_cli_set_scope_updates_both_records(tmp_path, capsys):
    store, tid, task_id = _dispatched_in_repo(tmp_path)
    code = main(["--root", str(tmp_path), "task", "set-scope", "--track", tid,
                 "--task", task_id, "--path", "src/**", "--path", "docs/**", "--json"])
    out = json.loads(capsys.readouterr().out)
    assert code == 0
    assert out["scope_paths"] == ["src/**", "docs/**"]
    assert out["dispatch_record_updated"] is True
    assert store.read_dispatch_record(tid, task_id).scope_paths == ["src/**", "docs/**"]
    record = store.read_track_record(tid)
    task = next(t for t in record.tasks if t.task_id == task_id)
    assert task.scope_paths == ["src/**", "docs/**"]
