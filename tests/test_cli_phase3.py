"""Phase 3 CLI: lane status/capture/submit via main(), JSON after subcommand."""

import json

import conductor.cli as climod
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
    """Minimal tmux seam for CLI tests."""

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


READY_CLAUDE_T = "│ > Try something │\n? for shortcuts"


def test_lane_status_absent_json(tmp_path, capsys):
    root = ["--root", str(tmp_path)]
    _run(capsys, *root, "init")
    code, data, raw = _run(capsys, *root, "lane", "status", "--target", "missing-session:claude", "--json")
    assert code == 0, raw
    assert data["state"] == "absent"
    assert data["provider"] == "claude"
    assert data["escaped_id"] == "missing-session_claude"


def test_lane_capture_absent_json(tmp_path, capsys):
    root = ["--root", str(tmp_path)]
    _run(capsys, *root, "init")
    code, data, _ = _run(capsys, *root, "lane", "capture", "--target", "missing-session:claude", "--json")
    assert code == 0
    assert data["state"] == "absent"
    assert data["line_count"] == 0


def test_lane_submit_absent_refused_nonzero(tmp_path, capsys):
    root = ["--root", str(tmp_path)]
    _run(capsys, *root, "init")
    code, data, _ = _run(capsys, *root, "lane", "submit",
                         "--target", "missing-session:claude",
                         "--task-file", "/tmp/nonexistent-task.md", "--json")
    assert code == 1
    assert data["submitted"] is False
    assert "provider_ready" in data["error"]


def test_lane_submit_ready_sends_short_reference(tmp_path, capsys, monkeypatch):
    root = ["--root", str(tmp_path)]
    _run(capsys, *root, "init")

    task = tmp_path / "task.md"
    task.write_text("SECRET BODY not to be pasted")
    fake = FakeTmux(transcript=READY_CLAUDE_T)

    # Inject the fake tmux into the CLI's adapter construction.
    real_adapter = LaneAdapter
    monkeypatch.setattr(climod, "LaneAdapter", lambda store: real_adapter(store, tmux=fake))

    code, data, raw = _run(capsys, *root, "lane", "submit",
                          "--target", "Conductor:claude", "--task-file", str(task), "--json")
    assert code == 0, raw
    assert data["submitted"] is True
    assert len(fake.sent) == 1
    assert str(task) in fake.sent[0][1]
    assert "SECRET BODY" not in fake.sent[0][1]


def test_status_includes_lanes_total(tmp_path, capsys, monkeypatch):
    root = ["--root", str(tmp_path)]
    _run(capsys, *root, "init")
    fake = FakeTmux(transcript=READY_CLAUDE_T)
    real_adapter = LaneAdapter
    monkeypatch.setattr(climod, "LaneAdapter", lambda store: real_adapter(store, tmux=fake))
    _run(capsys, *root, "lane", "status", "--target", "Conductor:claude", "--json")

    code, status, _ = _run(capsys, *root, "status", "--json")
    assert code == 0
    assert status["totals"]["lanes"] == 1
    assert status["lanes"][0]["target"] == "Conductor:claude"
