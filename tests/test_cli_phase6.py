"""Phase 6 CLI: operator summary/notify/heartbeat/approval/verify-hook via main()."""

import json

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


def _track(capsys, root):
    _run(capsys, *root, "init")
    return _run(capsys, *root, "go", "--plan-only", "Build a small dashboard", "--json")[1]["track_id"]


def test_operator_summary_telegram_text(tmp_path, capsys):
    root = ["--root", str(tmp_path)]
    tid = _track(capsys, root)
    code, _, out = _run(capsys, *root, "operator", "summary", "--track", tid, "--format", "telegram")
    assert code == 0
    assert tid in out
    assert "next:" in out
    assert "plan: pending_review" in out


def test_operator_summary_json_after_subcommand(tmp_path, capsys):
    root = ["--root", str(tmp_path)]
    tid = _track(capsys, root)
    code, data, _ = _run(capsys, *root, "operator", "summary", "--track", tid, "--json")
    assert code == 0
    assert data["scope"] == "track"
    assert data["signal"] == "needs_approval"


def test_operator_approval_plan_then_not_needed(tmp_path, capsys):
    root = ["--root", str(tmp_path)]
    tid = _track(capsys, root)
    code, data, _ = _run(capsys, *root, "operator", "approval", "--track", tid, "--kind", "plan", "--json")
    assert code == 0 and data["needed"] is True
    assert "approve plan" in data["command"]

    _run(capsys, *root, "approve", "plan", "--track", tid, "--json")
    code, data, _ = _run(capsys, *root, "operator", "approval", "--track", tid, "--kind", "plan", "--json")
    assert data["needed"] is False


def test_operator_notify_and_verify_hook(tmp_path, capsys):
    root = ["--root", str(tmp_path)]
    tid = _track(capsys, root)
    _run(capsys, *root, "approve", "plan", "--track", tid, "--json")
    _run(capsys, *root, "dispatch", "--track", tid, "--json")

    code, data, _ = _run(capsys, *root, "operator", "notify", "--track", tid, "--json")
    assert code == 0
    assert data["signal"] == "needs_verification"
    assert data["dedupe_key"]
    assert "telegram_text" in data

    code, hook, _ = _run(capsys, *root, "operator", "verify-hook", "--track", tid, "--json")
    assert code == 0
    assert "monitor status" in data["next_command"]
    assert all("--watch" not in c["command"] for c in hook["commands"])


def test_operator_heartbeat_now_flag(tmp_path, capsys):
    root = ["--root", str(tmp_path)]
    tid = _track(capsys, root)
    code, data, _ = _run(capsys, *root, "operator", "heartbeat", "--track", tid,
                        "--now", "2026-06-29T12:00:00Z", "--json")
    assert code == 0
    assert data["due"] is True
    assert data["cadence_seconds"] == 300


def test_operator_summary_unknown_track_exits_2(tmp_path, capsys):
    root = ["--root", str(tmp_path)]
    _run(capsys, *root, "init")
    code, data, _ = _run(capsys, *root, "operator", "notify", "--track", "track_nope", "--json")
    assert code == 2
    assert data["ok"] is False
