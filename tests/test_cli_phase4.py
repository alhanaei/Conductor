"""Phase 4 CLI: dispatch / task status / followup / nudge, JSON after subcommand."""

import json

import conductor.cli as climod
from conductor.dispatch import Dispatcher
from conductor.lanes import LaneAdapter


def _run(capsys, *argv):
    code = climod.main(list(argv))
    out = capsys.readouterr().out
    parsed = None
    if out.strip():
        try:
            parsed = json.loads(out)
        except json.JSONDecodeError:
            parsed = None
    return code, parsed, out


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


READY_CLAUDE_T = "│ > type │\n? for shortcuts"


def _new_track(capsys, root):
    _run(capsys, *root, "init")
    tid = _run(capsys, *root, "go", "--plan-only", "Build a small dashboard", "--json")[1]["track_id"]
    return tid


def test_dispatch_refuses_unapproved(tmp_path, capsys):
    root = ["--root", str(tmp_path)]
    tid = _new_track(capsys, root)
    code, data, _ = _run(capsys, *root, "dispatch", "--track", tid, "--json")
    assert code == 1
    assert data["ok"] is False


def test_dispatch_pending_lane_flow(tmp_path, capsys):
    """Full smoke: dispatch with no ready lane degrades to pending_lane, exit 0."""
    root = ["--root", str(tmp_path)]
    tid = _new_track(capsys, root)
    _run(capsys, *root, "approve", "plan", "--track", tid, "--json")

    code, data, raw = _run(capsys, *root, "dispatch", "--track", tid, "--json")
    assert code == 0, raw
    assert data["dispatched_count"] == 1
    t = data["dispatched"][0]
    assert t["dispatch_state"] in ("pending_lane", "blocked_lane")
    assert t["worktree_mode"] == "not_git_repo"
    task_id = t["task_id"]

    # task status
    code, st, _ = _run(capsys, *root, "task", "status", "--track", tid, "--task", task_id, "--json")
    assert code == 0
    assert st["task_state"] == "dispatched"
    assert st["route"] is not None
    assert "stale_risk" in st

    # followup (does not paste body)
    body = tmp_path / "fu.md"
    body.write_text("body text")
    code, fu, _ = _run(capsys, *root, "followup", "--track", tid, "--task", task_id,
                      "--body-file", str(body), "--json")
    assert code == 0
    assert fu["pasted_body"] is False
    assert fu["followup_index"] == 1

    # nudge (lane not ready -> not sent, but recorded, exit 0)
    code, nd, _ = _run(capsys, *root, "nudge", "--track", tid, "--task", task_id, "--json")
    assert code == 0
    assert nd["sent"] is False

    # global status still valid
    code, status, _ = _run(capsys, *root, "status", "--json")
    assert code == 0
    assert status["totals"]["tracks"] == 1


def test_dispatch_submits_when_ready_via_injected_adapter(tmp_path, capsys, monkeypatch):
    root = ["--root", str(tmp_path)]
    tid = _new_track(capsys, root)
    _run(capsys, *root, "approve", "plan", "--track", tid, "--json")

    fake = FakeTmux(transcript=READY_CLAUDE_T)
    real_dispatcher = Dispatcher
    monkeypatch.setattr(
        climod, "Dispatcher",
        lambda store: real_dispatcher(store, lane_adapter=LaneAdapter(store, tmux=fake)),
    )
    code, data, raw = _run(capsys, *root, "dispatch", "--track", tid, "--json")
    assert code == 0, raw
    t = data["dispatched"][0]
    assert t["dispatch_state"] == "submitted"
    assert t["task_state"] == "working"
    assert len(fake.sent) == 1
    assert "task.md" in fake.sent[0][1]


def test_task_status_unknown_task_exits_2(tmp_path, capsys):
    root = ["--root", str(tmp_path)]
    tid = _new_track(capsys, root)
    code, data, _ = _run(capsys, *root, "task", "status", "--track", tid, "--task", "task_nope", "--json")
    assert code == 2
    assert data["ok"] is False
