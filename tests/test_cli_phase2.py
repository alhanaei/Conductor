"""End-to-end Phase 2 CLI: go / plan review / approve plan, JSON after subcommand."""

import json

import pytest

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


def test_go_review_approve_flow(tmp_path, capsys):
    root = ["--root", str(tmp_path)]
    _run(capsys, *root, "init")

    # go --plan-only with --json AFTER the subcommand
    code, data, raw = _run(capsys, *root, "go", "--plan-only", "Build a small dashboard", "--json")
    assert code == 0 and data is not None, raw
    assert data["ok"] is True
    assert data["plan_status"] == "pending_review"
    assert data["task_count"] == 5
    tid = data["track_id"]

    # plan review --json
    code, data, raw = _run(capsys, *root, "plan", "review", "--track", tid, "--json")
    assert code == 0, raw
    assert data["approval_pending"] is True
    assert data["approved"] is False
    assert len(data["tasks"]) == 5

    # approve plan --json
    code, data, raw = _run(capsys, *root, "approve", "plan", "--track", tid, "--json")
    assert code == 0, raw
    assert data["approved"] is True
    assert data["already_approved"] is False
    assert data["plan_status"] == "approved"

    # idempotent re-approve
    code, data, _ = _run(capsys, *root, "approve", "plan", "--track", tid, "--json")
    assert code == 0
    assert data["already_approved"] is True


def test_status_reflects_plan(tmp_path, capsys):
    root = ["--root", str(tmp_path)]
    _run(capsys, *root, "init")
    tid = _run(capsys, *root, "go", "--plan-only", "goal", "--json")[1]["track_id"]
    _run(capsys, *root, "approve", "plan", "--track", tid, "--json")

    code, status, _ = _run(capsys, *root, "status", "--json")
    assert code == 0
    t = status["tracks"][0]
    assert t["plan_status"] == "approved"
    assert t["approved"] is True
    assert t["task_count"] == 5


def test_go_without_init_gives_actionable_error(tmp_path, capsys):
    code, data, raw = _run(capsys, "--root", str(tmp_path), "go", "--plan-only", "g", "--json")
    assert code == 2
    assert data is not None and data["ok"] is False
    assert "init" in (data.get("hint", "") + data.get("error", "")).lower()


def test_plan_review_unknown_track_exits_2(tmp_path, capsys):
    root = ["--root", str(tmp_path)]
    _run(capsys, *root, "init")
    code, data, _ = _run(capsys, *root, "plan", "review", "--track", "track_nope", "--json")
    assert code == 2
    assert data["ok"] is False


def test_plan_persists_across_restart(tmp_path, capsys):
    """Two independent CLI invocations share plan + approval state via disk only."""
    root = ["--root", str(tmp_path)]
    _run(capsys, *root, "init")
    tid = _run(capsys, *root, "go", "--plan-only", "persistent", "--json")[1]["track_id"]
    _run(capsys, *root, "approve", "plan", "--track", tid, "--json")

    # "Restart": fresh main() call reads approval back from disk.
    code, data, _ = _run(capsys, *root, "plan", "review", "--track", tid, "--json")
    assert code == 0
    assert data["approved"] is True
    assert data["plan_status"] == "approved"


def test_go_accepts_full_task_workflow_mode(tmp_path, capsys):
    root = ["--root", str(tmp_path)]
    _run(capsys, *root, "init")

    code, data, raw = _run(
        capsys,
        *root,
        "go",
        "--plan-only",
        "Build a small dashboard",
        "--task-workflow-mode",
        "full",
        "--json",
    )

    assert code == 0, raw
    assert data["task_workflow_mode"] == "full"
    from pathlib import Path

    plan = Path(data["plan_ref"]).read_text()
    metadata = json.loads((Path(data["plan_ref"]).parent / "metadata.json").read_text())
    assert "- task_workflow_mode: full" in plan
    assert "## Per-Task Workflow Contract" in plan
    assert "task-workflow:full" in metadata["tags"]

    _run(capsys, *root, "approve", "plan", "--track", data["track_id"], "--json")
    approved_plan = Path(data["plan_ref"]).read_text()
    assert "- task_workflow_mode: full" in approved_plan
    assert "## Per-Task Workflow Contract" in approved_plan
