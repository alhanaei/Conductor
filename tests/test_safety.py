"""Safety trio: command-running verification, allowlist, track-write mutex."""

import multiprocessing as mp
import subprocess
from pathlib import Path

import pytest

from conductor.completion import CompletionEngine
from conductor.dispatch import Dispatcher
from conductor.intake import approve_plan, create_planned_track
from conductor.lanes import LaneAdapter
from conductor.models import VerificationStatus
from conductor.store import ConductorStore, file_mutex
from conductor.verify_commands import (
    DEFAULT_ALLOWED_COMMANDS,
    load_allowlist,
    run_verification_command,
    run_verification_commands,
)


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


def _dispatched(store):
    rec = create_planned_track(store, "Build a small dashboard")
    approve_plan(store, rec.track.track_id)
    disp = Dispatcher(store, lane_adapter=LaneAdapter(store, tmux=FakeTmux()),
                      git=FakeGit(), default_session="proj")
    res = disp.dispatch(rec.track.track_id)
    return rec.track.track_id, res["dispatched"][0]["task_id"]


def _write_result(store, track_id, task_id):
    store.task_result_path(track_id, task_id).write_text("done\n", encoding="utf-8")


# --------------------------------------------------------------------------- #
# verify_commands: safe runner semantics
# --------------------------------------------------------------------------- #
def test_allowlisted_command_runs_and_passes(tmp_path):
    check = run_verification_command("python -c pass", tmp_path)
    assert check["passed"] is True
    assert check["exit_code"] == 0


def test_failing_command_is_failed_check(tmp_path):
    # Semicolon inside quotes is fine: no shell involved, one literal argument.
    check = run_verification_command("python -c 'import sys; sys.exit(3)'", tmp_path)
    assert check["passed"] is False
    assert check["exit_code"] == 3


def test_non_allowlisted_command_refused_loudly(tmp_path):
    check = run_verification_command("rm -rf /", tmp_path)
    assert check["passed"] is False
    assert check["exit_code"] is None
    assert "allowlist" in check["detail"]


def test_unquoted_shell_metacharacters_rejected(tmp_path):
    for cmd in ["python -c pass; rm x", "pytest | tee out", "make && make install",
                "python > out.txt", "echo `id`"]:
        check = run_verification_command(cmd, tmp_path)
        assert check["passed"] is False, cmd
        assert "metacharacters" in check["detail"] or "allowlist" in check["detail"]


def test_quoted_metacharacters_allowed(tmp_path):
    # The quoted text is a single literal argument — safe without a shell.
    check = run_verification_command("python -c 'import sys; sys.exit(0)'", tmp_path)
    assert check["passed"] is True


def test_allowlist_extension_from_config():
    allow = load_allowlist({"verification_allowed_commands": ["mytool"]})
    assert "mytool" in allow
    assert DEFAULT_ALLOWED_COMMANDS <= allow


def test_run_commands_output_evidence(tmp_path):
    checks = run_verification_commands(
        ["python -c 'print(\"hello-evidence\")'"], tmp_path)
    assert checks[0]["passed"] is True
    assert "hello-evidence" in checks[0]["output_tail"]


# --------------------------------------------------------------------------- #
# verification gate actually runs configured commands
# --------------------------------------------------------------------------- #
def test_verify_runs_configured_commands_pass(store):
    track_id, task_id = _dispatched(store)
    _write_result(store, track_id, task_id)
    drec = store.read_dispatch_record(track_id, task_id)
    drec.verification_commands = ["python -c 'import sys; sys.exit(0)'"]
    store.write_dispatch_record(drec)

    result = CompletionEngine(store).verify(track_id)
    r = next(x for x in result["results"] if x["task_id"] == task_id)
    assert r["passed"] is True

    gate = store.read_verification(track_id, task_id)
    assert gate.commands == ["python -c 'import sys; sys.exit(0)'"]
    assert any(c["name"] == "verification_command" and c["passed"] for c in gate.checks)
    # command output persisted as durable evidence
    out = store.task_dir(track_id, task_id) / "verification-output.txt"
    assert out.exists()
    assert str(out) in gate.evidence_refs


def test_verify_fails_when_configured_command_fails(store):
    """A worker result alone no longer passes if the configured command fails."""
    track_id, task_id = _dispatched(store)
    _write_result(store, track_id, task_id)  # worker claims done
    drec = store.read_dispatch_record(track_id, task_id)
    drec.verification_commands = ["python -c 'import sys; sys.exit(1)'"]
    store.write_dispatch_record(drec)

    result = CompletionEngine(store).verify(track_id)
    r = next(x for x in result["results"] if x["task_id"] == task_id)
    assert r["passed"] is False
    assert r["task_state"] == "needs_fix"
    gate = store.read_verification(track_id, task_id)
    assert gate.status is VerificationStatus.FAILED


def test_verify_fails_on_non_allowlisted_command(store):
    track_id, task_id = _dispatched(store)
    _write_result(store, track_id, task_id)
    drec = store.read_dispatch_record(track_id, task_id)
    drec.verification_commands = ["curl http://evil.example/x"]
    store.write_dispatch_record(drec)

    result = CompletionEngine(store).verify(track_id)
    r = next(x for x in result["results"] if x["task_id"] == task_id)
    assert r["passed"] is False  # refused loudly, not skipped silently


# --------------------------------------------------------------------------- #
# CLI: task set-verify
# --------------------------------------------------------------------------- #
def test_cli_task_set_verify_updates_plan_and_dispatch(tmp_path, capsys):
    import json

    from conductor.cli import main

    root = ["--root", str(tmp_path)]
    main([*root, "init"])
    capsys.readouterr()
    main([*root, "go", "--plan-only", "goal", "--json"])
    tid = json.loads(capsys.readouterr().out)["track_id"]
    main([*root, "approve", "plan", "--track", tid, "--json"])
    capsys.readouterr()
    main([*root, "dispatch", "--track", tid, "--json"])
    task_id = json.loads(capsys.readouterr().out)["dispatched"][0]["task_id"]

    code = main([*root, "task", "set-verify", "--track", tid, "--task", task_id,
                 "--command", "python -c pass", "--json"])
    data = json.loads(capsys.readouterr().out)
    assert code == 0
    assert data["verification_commands"] == ["python -c pass"]
    assert data["dispatch_record_updated"] is True

    # verify picks the command up from the dispatch record
    drec = ConductorStore.resolve(root=tmp_path, create=False) \
        .read_dispatch_record(tid, task_id)
    assert drec.verification_commands == ["python -c pass"]


# --------------------------------------------------------------------------- #
# track mutex: concurrent RMW does not lose updates
# --------------------------------------------------------------------------- #
def _tag_appender(root_str: str, track_id: str, tag: str):
    store = ConductorStore.resolve(root=Path(root_str), create=False)
    store.update_track_record(track_id, lambda rec: rec.track.tags.append(tag))


def test_concurrent_track_updates_are_not_lost(tmp_path):
    store = ConductorStore.resolve(root=tmp_path, create=True)
    tid = create_planned_track(store, "goal").track.track_id

    ctx = mp.get_context("spawn")
    n = 8
    procs = [ctx.Process(target=_tag_appender, args=(str(store.root), tid, f"tag{i}"))
             for i in range(n)]
    for p in procs:
        p.start()
    for p in procs:
        p.join(timeout=30)

    record = store.read_track_record(tid)
    # Every process's append survived: no lost updates under the mutex.
    # (The track may carry pre-existing tags like task-workflow markers.)
    added = [t for t in record.track.tags if t.startswith("tag")]
    assert sorted(added) == sorted(f"tag{i}" for i in range(n))


def test_file_mutex_times_out(tmp_path):
    mutex_path = tmp_path / ".m"
    with file_mutex(mutex_path):
        with pytest.raises(TimeoutError):
            # flock is per-fd, so a second acquisition in the same process
            # exercises the timeout path deterministically.
            with file_mutex(mutex_path, timeout=0.2, poll=0.05):
                pass


def test_exact_git_diff_check_policy_command_runs(tmp_path):
    subprocess.run(
        ["git", "init", "-q"], cwd=tmp_path, check=True, capture_output=True
    )

    check = run_verification_command("git diff --check", tmp_path)

    assert check["passed"] is True
    assert check["exit_code"] == 0


def test_other_git_commands_remain_rejected(tmp_path):
    check = run_verification_command("git status", tmp_path)

    assert check["passed"] is False
    assert check["exit_code"] is None
    assert "allowlist" in check["detail"]
