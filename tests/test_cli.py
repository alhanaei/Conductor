"""End-to-end CLI behavior through ``conductor.cli.main`` with JSON output."""

import json

import pytest

from conductor.cli import main


def _run(capsys, *argv):
    """Invoke the CLI, returning (exit_code, parsed_json_or_None, raw_stdout)."""
    code = main(list(argv))
    out = capsys.readouterr().out
    parsed = None
    if out.strip():
        try:
            parsed = json.loads(out)
        except json.JSONDecodeError:
            parsed = None
    return code, parsed, out


def test_init_dry_run_writes_nothing(tmp_path, capsys):
    code, data, _ = _run(capsys, "--root", str(tmp_path), "--json", "init", "--dry-run")
    assert code == 0
    assert data["dry_run"] is True
    assert not (tmp_path / ".conductor").exists()


def test_init_creates_root(tmp_path, capsys):
    code, data, _ = _run(capsys, "--root", str(tmp_path), "--json", "init")
    assert code == 0
    assert data["initialized"] is True
    assert (tmp_path / ".conductor" / "conductor.json").exists()


def test_full_flow_track_message_lock_status(tmp_path, capsys):
    root = ["--root", str(tmp_path), "--json"]

    _run(capsys, *root, "init")

    code, data, _ = _run(capsys, *root, "track", "new", "phase 1 smoke goal")
    assert code == 0
    track_id = data["track_id"]

    # send a message
    code, data, _ = _run(capsys, *root, "message", "send",
                         "--track", track_id, "--type", "PROGRESS",
                         "--body", "working on it", "--worker", "w1")
    assert code == 0
    assert data["type"] == "PROGRESS"

    # list it back deterministically
    code, data, _ = _run(capsys, *root, "message", "list", "--track", track_id)
    assert code == 0
    assert data["count"] == 1
    assert data["messages"][0]["body"] == "working on it"

    # acquire a lock
    code, data, _ = _run(capsys, *root, "lock", "acquire",
                         "--track", track_id, "--file", "src/x.py", "--worker", "w1")
    assert code == 0 and data["acquired"] is True

    # conflicting acquire returns exit 1
    code, data, _ = _run(capsys, *root, "lock", "acquire",
                         "--track", track_id, "--file", "src/x.py", "--worker", "w2")
    assert code == 1 and data["acquired"] is False

    # status reflects everything
    code, status, _ = _run(capsys, *root, "status")
    assert code == 0
    assert status["totals"]["tracks"] == 1
    assert status["totals"]["messages"] == 1
    assert status["totals"]["locks"] == 1
    assert status["tracks"][0]["track_id"] == track_id


def test_release_then_reacquire(tmp_path, capsys):
    root = ["--root", str(tmp_path), "--json"]
    _run(capsys, *root, "init")
    track_id = _run(capsys, *root, "track", "new", "g")[1]["track_id"]

    _run(capsys, *root, "lock", "acquire", "--track", track_id, "--file", "a.py", "--worker", "w1")
    code, data, _ = _run(capsys, *root, "lock", "release",
                         "--track", track_id, "--file", "a.py", "--worker", "w1")
    assert code == 0 and data["released"] is True

    code, data, _ = _run(capsys, *root, "lock", "acquire",
                         "--track", track_id, "--file", "a.py", "--worker", "w2")
    assert code == 0 and data["acquired"] is True


def test_doctor_reports_health(tmp_path, capsys):
    root = ["--root", str(tmp_path), "--json"]
    _run(capsys, *root, "init")
    _run(capsys, *root, "track", "new", "g")
    code, report, _ = _run(capsys, *root, "doctor")
    assert code == 0
    assert report["ok"] is True
    assert any(c["name"] == "state_root_exists" and c["ok"] for c in report["checks"])


def test_doctor_fails_without_init(tmp_path, capsys):
    code, report, _ = _run(capsys, "--root", str(tmp_path), "--json", "doctor")
    assert code == 1
    assert report["ok"] is False


def test_invalid_message_type_exits_2(tmp_path, capsys):
    root = ["--root", str(tmp_path), "--json"]
    _run(capsys, *root, "init")
    track_id = _run(capsys, *root, "track", "new", "g")[1]["track_id"]
    code = main(["--root", str(tmp_path), "message", "send",
                 "--track", track_id, "--type", "NONSENSE", "--body", "x"])
    assert code == 2


def test_json_flag_accepted_after_subcommand(tmp_path, capsys):
    """Regression: ``status --json`` / ``doctor --json`` (flag AFTER subcommand)."""
    _run(capsys, "--root", str(tmp_path), "init")

    # Flag after the subcommand must produce JSON (exit 0) for both commands.
    code, data, raw = _run(capsys, "--root", str(tmp_path), "status", "--json")
    assert code == 0 and data is not None and "totals" in data, raw

    code, data, raw = _run(capsys, "--root", str(tmp_path), "doctor", "--json")
    assert code == 0 and data is not None and data["ok"] is True, raw

    # And the global-before-subcommand form still works.
    code, data, raw = _run(capsys, "--root", str(tmp_path), "--json", "status")
    assert code == 0 and data is not None and "totals" in data, raw


def test_state_survives_restart(tmp_path, capsys):
    """Two independent CLI invocations share state purely through disk."""
    root = ["--root", str(tmp_path), "--json"]
    _run(capsys, *root, "init")
    track_id = _run(capsys, *root, "track", "new", "persistent goal")[1]["track_id"]
    _run(capsys, *root, "message", "send", "--track", track_id,
         "--type", "PROGRESS", "--body", "before restart", "--worker", "w1")

    # "Restart": fresh main() call, nothing in memory carries over.
    code, data, _ = _run(capsys, *root, "message", "list", "--track", track_id)
    assert code == 0
    assert data["count"] == 1
    assert data["messages"][0]["body"] == "before restart"
