"""Phase 5 CLI: verify / fix / approve merge / close / reconcile via main()."""

import json
import time

import conductor.cli as cli
from conductor.cli import main


def _run(capsys, *argv):
    code = main(list(argv))
    out = capsys.readouterr().out
    parsed = None
    if out.strip():
        try:
            parsed = json.loads(out)
        except json.JSONDecodeError:
            parsed = None
    return code, parsed, out


def _approved_dispatched(capsys, root, tmp_path):
    _run(capsys, *root, "init")
    tid = _run(capsys, *root, "go", "--plan-only", "Build a small dashboard", "--json")[1]["track_id"]
    _run(capsys, *root, "approve", "plan", "--track", tid, "--json")
    disp = _run(capsys, *root, "dispatch", "--track", tid, "--json")[1]
    task_id = disp["dispatched"][0]["task_id"]
    return tid, task_id


def _write_result(tmp_path, tid, task_id, text="TASK_COMPLETE\nworker says done\n"):
    p = tmp_path / ".conductor" / "tracks" / tid / "tasks" / task_id / "result.md"
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text)


def test_full_gate_sequence(tmp_path, capsys):
    root = ["--root", str(tmp_path)]
    tid, task_id = _approved_dispatched(capsys, root, tmp_path)
    _write_result(tmp_path, tid, task_id)  # worker claim without verifier proof

    # close before merge approval -> exit 1
    code, data, _ = _run(capsys, *root, "close", "--track", tid, "--json")
    assert code == 1 and data["ok"] is False

    # approve merge before verify -> exit 1
    code, data, _ = _run(capsys, *root, "approve", "merge", "--track", tid, "--json")
    assert code == 1 and data["ok"] is False
    assert "unverified" in (data.get("evidence") or {})

    # verify -> pass
    code, data, raw = _run(capsys, *root, "verify", "--track", tid, "--json")
    assert code == 0, raw
    assert data["verified_count"] == 1
    assert data["results"][0]["task_state"] == "ready_for_merge"

    # task status surfaces verification fields
    code, st, _ = _run(capsys, *root, "task", "status", "--track", tid, "--task", task_id, "--json")
    assert code == 0
    assert st["verification_status"] == "passed"
    assert st["ready_for_merge"] is True

    # approve merge after verify is still blocked while downstream DAG tasks remain.
    code, data, _ = _run(capsys, *root, "approve", "merge", "--track", tid, "--json")
    assert code == 1 and data["ok"] is False
    assert "unfinalized_tasks" in (data.get("evidence") or {})

    # force remains available for explicit operator override in fixture/sandbox flows.
    code, data, _ = _run(capsys, *root, "approve", "merge", "--track", tid, "--force", "--json")
    assert code == 0 and data["merge_approved"] is True

    # close also refuses unfinished DAGs unless explicitly forced.
    code, data, _ = _run(capsys, *root, "close", "--track", tid, "--json")
    assert code == 1 and data["ok"] is False
    assert "unfinalized_tasks" in (data.get("evidence") or {})

    code, data, _ = _run(capsys, *root, "close", "--track", tid, "--force", "--json")
    assert code == 0 and data["closed"] is True
    assert data["track_state"] == "complete"

    # status still valid
    code, status, _ = _run(capsys, *root, "status", "--json")
    assert code == 0
    assert status["tracks"][0]["state"] == "complete"


def test_verify_fail_then_fix(tmp_path, capsys):
    root = ["--root", str(tmp_path)]
    tid, task_id = _approved_dispatched(capsys, root, tmp_path)
    # no result artifact -> verify fails
    code, data, _ = _run(capsys, *root, "verify", "--track", tid, "--json")
    assert code == 0
    assert data["failed_count"] == 1
    assert data["results"][0]["task_state"] == "needs_fix"

    # fix increments
    code, data, _ = _run(capsys, *root, "fix", "--track", tid, "--task", task_id, "--json")
    assert code == 0
    assert data["fix_attempt"] == 1
    assert data["pasted_body"] is False


def test_fix_refuses_after_max(tmp_path, capsys):
    root = ["--root", str(tmp_path)]
    tid, task_id = _approved_dispatched(capsys, root, tmp_path)
    for _ in range(3):
        _run(capsys, *root, "fix", "--track", tid, "--task", task_id, "--json")
    code, data, _ = _run(capsys, *root, "fix", "--track", tid, "--task", task_id, "--json")
    assert code == 1
    assert data["ok"] is False


def test_reconcile_json(tmp_path, capsys):
    root = ["--root", str(tmp_path)]
    tid, task_id = _approved_dispatched(capsys, root, tmp_path)
    _write_result(tmp_path, tid, task_id)
    # not verified -> reconcile flags it
    code, data, _ = _run(capsys, *root, "reconcile", "--track", tid, "--json")
    assert code == 0
    assert data["consistent"] is False
    task = next(t for t in data["tasks"] if t["task_id"] == task_id)
    assert "worker_result_without_verification" in task["issues"]


def test_close_refused_before_merge_exit_1(tmp_path, capsys):
    root = ["--root", str(tmp_path)]
    tid, task_id = _approved_dispatched(capsys, root, tmp_path)
    _write_result(tmp_path, tid, task_id)
    _run(capsys, *root, "verify", "--track", tid, "--json")
    code, data, _ = _run(capsys, *root, "close", "--track", tid, "--json")
    assert code == 1
    assert data["ok"] is False


def test_advance_cli_releases_next_task(tmp_path, capsys):
    root = ["--root", str(tmp_path)]
    tid, task_id = _approved_dispatched(capsys, root, tmp_path)
    _write_result(tmp_path, tid, task_id)
    _run(capsys, *root, "verify", "--track", tid, "--json")

    code, data, raw = _run(capsys, *root, "advance", "--track", tid, "--json")

    assert code == 0, raw
    assert data["advanced"] == [task_id]
    assert data["newly_ready_count"] == 1


def test_loop_tick_skips_working_without_result_then_advances_when_result_exists(tmp_path, capsys):
    root = ["--root", str(tmp_path)]
    tid, task_id = _approved_dispatched(capsys, root, tmp_path)

    code, data, raw = _run(capsys, *root, "loop", "--track", tid, "--json")
    assert code == 0, raw
    first = data["cycles"][0]
    assert first["verified"]["verified_count"] == 0
    assert first["verified"]["skipped"][0]["reason"] == "result_artifact_missing"

    _write_result(tmp_path, tid, task_id)
    code, data, raw = _run(capsys, *root, "loop", "--track", tid, "--json")
    assert code == 0, raw
    cycle = data["cycles"][0]
    assert cycle["verified"]["verified_count"] == 1
    assert cycle["advanced"]["advanced"] == [task_id]
    assert cycle["advanced"]["newly_ready_count"] == 1
    assert cycle["dispatched"]["dispatched_count"] == 1


def _complete_other_plan_tasks(tmp_path, tid, task_id):
    """Fixture shortcut: mark all plan tasks except ``task_id`` complete."""
    from conductor.models import TaskState
    from conductor.store import ConductorStore

    store = ConductorStore.resolve(root=tmp_path, create=False)
    record = store.read_track_record(tid)
    for task in record.tasks:
        if task.task_id != task_id and task.state is TaskState.PENDING:
            task.state = TaskState.COMPLETE
    store.write_track_record(record)


def test_loop_default_awaits_operator_when_all_tasks_complete(tmp_path, capsys):
    """Without --auto-finalize the loop must NOT approve merge/close itself."""
    root = ["--root", str(tmp_path)]
    tid, task_id = _approved_dispatched(capsys, root, tmp_path)
    _write_result(tmp_path, tid, task_id)
    _complete_other_plan_tasks(tmp_path, tid, task_id)

    code, data, raw = _run(capsys, *root, "loop", "--track", tid, "--json")
    assert code == 0, raw
    assert data["stop_reason"] == "awaiting_operator"
    assert data["finalized"]["attempted"] is False
    assert data["finalized"]["closed"] is False
    assert any("approve merge" in c for c in data["finalized"]["next_commands"])


def test_loop_auto_finalize_refused_for_requires_operator_tasks(tmp_path, capsys):
    """--auto-finalize still defers when a task's autonomy_policy requires an operator."""
    root = ["--root", str(tmp_path)]
    tid, task_id = _approved_dispatched(capsys, root, tmp_path)
    _write_result(tmp_path, tid, task_id)
    _complete_other_plan_tasks(tmp_path, tid, task_id)

    # The default plan's review task carries autonomy_policy=requires_operator.
    code, data, raw = _run(capsys, *root, "loop", "--track", tid, "--auto-finalize", "--json")
    assert code == 0, raw
    assert data["stop_reason"] == "awaiting_operator"
    assert data["finalized"]["attempted"] is False
    assert data["finalized"]["requires_operator_tasks"]


def test_loop_auto_finalizes_with_flag_and_force(tmp_path, capsys):
    root = ["--root", str(tmp_path)]
    tid, task_id = _approved_dispatched(capsys, root, tmp_path)
    _write_result(tmp_path, tid, task_id)
    _complete_other_plan_tasks(tmp_path, tid, task_id)

    code, data, raw = _run(capsys, *root, "loop", "--track", tid,
                           "--auto-finalize", "--force", "--json")
    assert code == 0, raw
    assert data["finalized"]["closed"] is True
    assert data["finalized"]["merge_approved"] is True
    assert data["finalized"]["closed_result"]["track_state"] == "complete"


def test_loop_watch_is_refused_without_sleep(tmp_path, capsys, monkeypatch):
    root = ["--root", str(tmp_path)]
    tid, _task_id = _approved_dispatched(capsys, root, tmp_path)

    def fail_sleep(_seconds):
        raise AssertionError("loop --watch must be refused before sleeping")

    monkeypatch.setattr(time, "sleep", fail_sleep)
    code, data, raw = _run(
        capsys, *root, "loop", "--track", tid, "--watch",
        "--max-cycles", "3", "--poll-interval", "0.01", "--json",
    )

    assert code == 2, raw
    assert data["ok"] is False
    assert data["error"] == "loop --watch has been removed"
    assert "monitor run" in data["migration_command"]


def test_loop_watch_refusal_does_not_scan_blocked_lanes(tmp_path, capsys, monkeypatch):
    root = ["--root", str(tmp_path)]
    tid, _task_id = _approved_dispatched(capsys, root, tmp_path)

    def fail_scan(_store, _track_id):
        raise AssertionError("refused loop --watch must not scan lanes")

    monkeypatch.setattr(cli, "active_blocked_prompts", fail_scan)
    code, data, raw = _run(
        capsys, *root, "loop", "--track", tid, "--watch",
        "--stop-on-blocked-prompt", "--json",
    )

    assert code == 2, raw
    assert data["ok"] is False
    assert data["watch"] is False
    assert data["migration_command"].endswith(f"monitor run --track {tid} --json")


def test_lane_blocked_command_reports_active_blocked_prompts(tmp_path, capsys, monkeypatch):
    root = ["--root", str(tmp_path)]
    tid, task_id = _approved_dispatched(capsys, root, tmp_path)
    blocked = [{
        "task_id": task_id,
        "title": "Clarify requirements and constraints",
        "lane_target": "proj:claude",
        "provider": "claude",
        "lane_state": "blocked_prompt",
        "result_artifact_ref": str(tmp_path / ".conductor" / "tracks" / tid / "tasks" / task_id / "result.md"),
        "operator_action": "approve the prompt in the tmux pane or move this lane to the project-root session",
    }]
    monkeypatch.setattr(cli, "active_blocked_prompts", lambda store, track_id: blocked)

    code, data, raw = _run(capsys, *root, "lane", "blocked", "--track", tid, "--json")

    assert code == 0, raw
    assert data["blocked_count"] == 1
    assert data["blocked"][0]["lane_target"] == "proj:claude"


def test_loop_max_cycles_compatibility_option_still_runs_one_tick(
    tmp_path, capsys
):
    root = ["--root", str(tmp_path)]
    track_id, _task_id = _approved_dispatched(capsys, root, tmp_path)

    code, data, raw = _run(
        capsys,
        *root,
        "loop",
        "--track",
        track_id,
        "--max-cycles",
        "3",
        "--json",
    )

    assert code == 0, raw
    assert data["cycle_count"] == 1
    assert data["watch"] is False
    assert data["stop_reason"] == "idle"
