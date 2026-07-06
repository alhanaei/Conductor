"""Lane launch: shell-gated provider start + tiered model policy."""

import json

import pytest

from conductor.cli import main
from conductor.lanes import (
    DEFAULT_LANE_MODELS,
    LaneAdapter,
    LaneError,
    resolve_lane_model,
)
from conductor.store import ConductorStore


class FakeTmux:
    """Transcript can be switched after the launch command is sent."""

    def __init__(self, transcript="", capture_ok=True, after_launch=None):
        self.transcript = transcript
        self.capture_ok = capture_ok
        self.after_launch = after_launch
        self.sent = []

    def available(self):
        return True

    def capture(self, target, lines=200):
        return (self.capture_ok, self.transcript if self.capture_ok else "")

    def send_text(self, target, text):
        self.sent.append((target, text))
        if self.after_launch is not None:
            self.transcript = self.after_launch  # provider UI comes up
        return True

    def send_enter(self, target):
        return True

    def ensure(self, session, window):
        return True


SHELL_T = "user@host:~/projects$ "
READY_CLAUDE_T = "│ > try something │\n? for shortcuts"
BUSY_T = "✻ Thinking… (esc to interrupt)"


@pytest.fixture()
def store(tmp_path):
    return ConductorStore.resolve(root=tmp_path, create=True)


# --------------------------------------------------------------------------- #
# Tiered model policy
# --------------------------------------------------------------------------- #
def test_default_tier_map():
    assert DEFAULT_LANE_MODELS["build"] == "claude-fable-5"
    assert DEFAULT_LANE_MODELS["plan"] == "claude-fable-5"
    assert DEFAULT_LANE_MODELS["review"] == "claude-fable-5"
    assert DEFAULT_LANE_MODELS["test"] == "claude-sonnet-4-6"
    assert DEFAULT_LANE_MODELS["spec"] == "claude-sonnet-4-6"


def test_resolve_lane_model_defaults_and_override():
    assert resolve_lane_model("build") == "claude-fable-5"
    assert resolve_lane_model(None) == DEFAULT_LANE_MODELS["default"]
    assert resolve_lane_model("nonexistent") == DEFAULT_LANE_MODELS["default"]
    # conductor.json override wins
    cfg = {"lane_models": {"build": "claude-opus-4-8"}}
    assert resolve_lane_model("build", cfg) == "claude-opus-4-8"
    assert resolve_lane_model("review", cfg) == "claude-fable-5"  # untouched tiers stay


# --------------------------------------------------------------------------- #
# Adapter.launch — safety gate + command construction
# --------------------------------------------------------------------------- #
def test_launch_sends_model_command_into_shell(store):
    tmux = FakeTmux(transcript=SHELL_T, after_launch=READY_CLAUDE_T)
    adapter = LaneAdapter(store, tmux=tmux)
    result = adapter.launch("Conductor:claude", model="claude-fable-5", wait_seconds=0)
    assert result["launched"] is True
    assert result["command"] == "claude --model claude-fable-5"
    assert tmux.sent[-1][1] == "claude --model claude-fable-5"
    assert result["state"] == "provider_ready"
    # model persisted on the lane record
    rec = store.list_lane_records()[0]
    assert rec.model == "claude-fable-5"


def test_launch_refuses_busy_and_ready_and_absent(store):
    # busy pane: refuse
    adapter = LaneAdapter(store, tmux=FakeTmux(transcript=BUSY_T))
    with pytest.raises(LaneError):
        adapter.launch("Conductor:claude", model="claude-fable-5", wait_seconds=0)
    # absent pane: refuse
    adapter = LaneAdapter(store, tmux=FakeTmux(capture_ok=False))
    with pytest.raises(LaneError):
        adapter.launch("Conductor:claude", wait_seconds=0)


def test_launch_noop_when_provider_already_ready(store):
    tmux = FakeTmux(transcript=READY_CLAUDE_T)
    adapter = LaneAdapter(store, tmux=tmux)
    result = adapter.launch("Conductor:claude", model="claude-fable-5", wait_seconds=0)
    assert result["launched"] is False
    assert tmux.sent == []  # nothing typed into a running provider


def test_launch_model_rejected_for_provider_without_flag(store):
    adapter = LaneAdapter(store, tmux=FakeTmux(transcript=SHELL_T))
    with pytest.raises(LaneError):
        adapter.launch("Conductor:codex", model="some-model", wait_seconds=0)


def test_launch_bare_command_for_provider_without_model(store):
    tmux = FakeTmux(transcript=SHELL_T)
    adapter = LaneAdapter(store, tmux=tmux)
    result = adapter.launch("Conductor:codex", wait_seconds=0)
    assert result["command"] == "codex"


def test_launch_unknown_provider_refused(store):
    adapter = LaneAdapter(store, tmux=FakeTmux(transcript=SHELL_T))
    with pytest.raises(LaneError):
        adapter.launch("Conductor:window7", wait_seconds=0)


# --------------------------------------------------------------------------- #
# CLI: lane ensure --launch
# --------------------------------------------------------------------------- #
def _run(capsys, *argv):
    code = main(list(argv))
    out = capsys.readouterr().out
    try:
        return code, (json.loads(out) if out.strip() else None)
    except json.JSONDecodeError:
        return code, None


def _patched_adapter(monkeypatch, tmux):
    import conductor.cli as climod
    real = LaneAdapter
    monkeypatch.setattr(climod, "LaneAdapter", lambda store: real(store, tmux=tmux))
    return tmux


def test_cli_ensure_launch_with_method_tier(tmp_path, capsys, monkeypatch):
    _patched_adapter(monkeypatch, FakeTmux(transcript=SHELL_T,
                                           after_launch=READY_CLAUDE_T))
    root = ["--root", str(tmp_path)]
    _run(capsys, *root, "init")
    code, data = _run(capsys, *root, "lane", "ensure", "--target", "Conductor:claude",
                      "--launch", "--method", "build", "--launch-wait", "0", "--json")
    assert code == 0
    assert data["launched"] is True
    assert data["model"] == "claude-fable-5"
    assert "claude --model claude-fable-5" in data["command"]


def test_cli_ensure_launch_explicit_model_wins(tmp_path, capsys, monkeypatch):
    _patched_adapter(monkeypatch, FakeTmux(transcript=SHELL_T,
                                           after_launch=READY_CLAUDE_T))
    root = ["--root", str(tmp_path)]
    _run(capsys, *root, "init")
    code, data = _run(capsys, *root, "lane", "ensure", "--target", "Conductor:claude",
                      "--launch", "--model", "claude-opus-4-8",
                      "--method", "build", "--launch-wait", "0", "--json")
    assert code == 0
    assert data["model"] == "claude-opus-4-8"


def test_cli_ensure_launch_config_override(tmp_path, capsys, monkeypatch):
    _patched_adapter(monkeypatch, FakeTmux(transcript=SHELL_T,
                                           after_launch=READY_CLAUDE_T))
    root = ["--root", str(tmp_path)]
    _run(capsys, *root, "init")
    config_path = tmp_path / ".conductor" / "conductor.json"
    cfg = json.loads(config_path.read_text())
    cfg["lane_models"] = {"test": "claude-haiku-4-5"}
    config_path.write_text(json.dumps(cfg))

    code, data = _run(capsys, *root, "lane", "ensure", "--target", "Conductor:claude",
                      "--launch", "--method", "test", "--launch-wait", "0", "--json")
    assert code == 0
    assert data["model"] == "claude-haiku-4-5"


def test_cli_ensure_without_launch_unchanged(tmp_path, capsys, monkeypatch):
    tmux = _patched_adapter(monkeypatch, FakeTmux(transcript=SHELL_T))
    root = ["--root", str(tmp_path)]
    _run(capsys, *root, "init")
    code, data = _run(capsys, *root, "lane", "ensure", "--target", "Conductor:claude", "--json")
    assert code == 0
    assert "launched" not in data
    assert tmux.sent == []  # ensure alone never types into the pane
