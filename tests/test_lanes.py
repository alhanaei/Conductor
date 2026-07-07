"""Phase 3 lane adapter: target parsing, registry, classifier, adapter safety."""

import pytest

from conductor.lanes import (
    FUTURE_PROVIDERS,
    PROVIDERS,
    LaneAdapter,
    LaneError,
    classify,
    escape_target,
    list_lane_status,
    parse_target,
    provider_profile,
)
from conductor.models import LaneState
from conductor.store import ConductorStore, read_jsonl


# --------------------------------------------------------------------------- #
# Fake tmux seam — same shape as TmuxClient, zero real processes.
# --------------------------------------------------------------------------- #
class FakeTmux:
    def __init__(self, available=True, transcript="", capture_ok=True, ensure_ok=True):
        self._available = available
        self.transcript = transcript
        self.capture_ok = capture_ok
        self.ensure_ok = ensure_ok
        self.sent = []        # list of (target, text)
        self.entered = 0
        self.ensured = []     # list of (session, window)

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
        self.ensured.append((session, window))
        return self.ensure_ok


# Sample transcripts per readiness state.
SHELL_T = "Last login: ...\nalh@host:~/projects/Conductor$ "
READY_CLAUDE_T = (
    "╭──────────────────────────────╮\n"
    "│ > Try \"refactor this file\"   │\n"
    "╰──────────────────────────────╯\n"
    "? for shortcuts"
)
BUSY_CLAUDE_T = "✻ Thinking… (esc to interrupt)\n"
BLOCKED_T = "Do you want to proceed?\n❯ 1. Yes\n  2. No, tell Claude what to do differently"
UNKNOWN_T = "some build output line\nanother line of text\nfinished step"


@pytest.fixture()
def store(tmp_path):
    return ConductorStore.resolve(root=tmp_path, create=True)


# --------------------------------------------------------------------------- #
# Target parsing + escaping
# --------------------------------------------------------------------------- #
def test_parse_target_basic():
    t = parse_target("Conductor:claude")
    assert t.session == "Conductor"
    assert t.window == "claude"
    assert t.provider == "claude"


def test_parse_target_unknown_provider_is_none():
    t = parse_target("proj:window7")
    assert t.provider is None


@pytest.mark.parametrize("bad", ["", "   ", "noseparator", "a:b:c", "a:", ":b", ": "])
def test_parse_target_rejects_bad(bad):
    with pytest.raises(LaneError):
        parse_target(bad)


def test_escape_target_is_stable_and_safe():
    assert escape_target("Conductor:claude") == "Conductor_claude"
    assert escape_target("a b/c:d") == "a_b_c_d"
    # stable across calls
    assert escape_target("x:y") == escape_target("x:y")


# --------------------------------------------------------------------------- #
# Provider registry
# --------------------------------------------------------------------------- #
def test_provider_registry_entries():
    for name in ("claude", "codex", "gemini", "grok"):
        assert name in PROVIDERS
        assert PROVIDERS[name].name == name
    # future extension points are declared but not first-class yet
    assert set(FUTURE_PROVIDERS) == {"cursor", "opencode"}


def test_provider_profile_fallback_is_generic():
    assert provider_profile("nope").name == "generic"
    assert provider_profile(None).name == "generic"


# --------------------------------------------------------------------------- #
# Classifier — one sample per state
# --------------------------------------------------------------------------- #
def test_classify_absent_when_session_missing():
    assert classify("anything", provider_profile("claude"), session_exists=False) is LaneState.ABSENT


def test_classify_shell():
    assert classify(SHELL_T, provider_profile("claude")) is LaneState.SHELL


def test_classify_provider_ready():
    assert classify(READY_CLAUDE_T, provider_profile("claude")) is LaneState.PROVIDER_READY


def test_classify_claude_ready_with_mcp_auth_warning():
    transcript = (
        "▐▛███▜▌   Claude Code v2.1.195\n"
        "▝▜█████▛▘  Opus 4.8 (1M context) · Claude Max\n"
        " ⚠ 5 MCP servers need authentication · run /mcp\n"
        "────────────────────────────────\n"
        "❯\u00a0\n"
        "  [Opus 4.8 (1M context)] │ market-relations git:(feat/simulation-engine*)\n"
        "  ⏵⏵ auto mode on (shift+tab to cycle) · ← for agents\n"
    )
    assert classify(transcript, provider_profile("claude")) is LaneState.PROVIDER_READY


def test_classify_claude_ready_after_completed_output_with_prompt_text():
    transcript = (
        "● Done. The Claude lane is complete and verified.\n"
        "  The plan mentions merge approval and a trustworthy scope check.\n"
        "  You can run python -m pytest -q and grep TASK_COMPLETE.\n"
        "\n"
        "✻ Worked for 54s\n"
        "────────────────────────────────\n"
        "❯\u00a0verify the codex lane finished\n"
        "────────────────────────────────\n"
        "  [Opus 4.8 (1M context)] │ conductor-test\n"
        "  Context █░░░░░░░░░ 5%\n"
        "  ⏵⏵ auto mode on (shift+tab to cycle) · ← for agents\n"
    )
    assert classify(transcript, provider_profile("claude")) is LaneState.PROVIDER_READY


def test_classify_auth_prompt_blocks_without_ready_ui():
    transcript = "Please log in to continue. Visit the URL and authenticate."
    assert classify(transcript, provider_profile("claude")) is LaneState.BLOCKED_PROMPT


def test_classify_busy():
    assert classify(BUSY_CLAUDE_T, provider_profile("claude")) is LaneState.BUSY


def test_classify_blocked_prompt():
    assert classify(BLOCKED_T, provider_profile("claude")) is LaneState.BLOCKED_PROMPT


def test_classify_unknown():
    assert classify(UNKNOWN_T, provider_profile("claude")) is LaneState.UNKNOWN


def test_classify_blocked_beats_busy():
    # An approval prompt that also shows a spinner must classify as blocked.
    mixed = "✻ Thinking… (esc to interrupt)\nDo you want to proceed? [y/n]"
    assert classify(mixed, provider_profile("claude")) is LaneState.BLOCKED_PROMPT


# --------------------------------------------------------------------------- #
# Adapter: status / absence / persistence
# --------------------------------------------------------------------------- #
def test_status_absent_when_tmux_unavailable(store):
    adapter = LaneAdapter(store, tmux=FakeTmux(available=False))
    result = adapter.status("missing:claude")
    assert result["state"] == "absent"
    assert result["tmux_available"] is False


def test_status_absent_when_capture_fails(store):
    adapter = LaneAdapter(store, tmux=FakeTmux(capture_ok=False))
    result = adapter.status("missing:claude")
    assert result["state"] == "absent"
    assert result["tmux_available"] is True  # tmux present, session is not


def test_status_persists_record(store, tmp_path):
    adapter = LaneAdapter(store, tmux=FakeTmux(transcript=READY_CLAUDE_T))
    adapter.status("Conductor:claude")
    # Fresh store object = restart; record read back from disk.
    reloaded = ConductorStore.resolve(root=tmp_path, create=False)
    records = reloaded.list_lane_records()
    assert len(records) == 1
    assert records[0].target == "Conductor:claude"
    assert records[0].state is LaneState.PROVIDER_READY
    assert records[0].last_heartbeat_at is not None


def test_capture_returns_transcript_and_writes_artifact(store):
    adapter = LaneAdapter(store, tmux=FakeTmux(transcript=READY_CLAUDE_T))
    result = adapter.capture("Conductor:claude")
    assert result["state"] == "provider_ready"
    assert result["line_count"] == len(READY_CLAUDE_T.splitlines())
    assert "? for shortcuts" in result["transcript"]
    assert result["transcript_ref"] is not None
    from pathlib import Path
    assert Path(result["transcript_ref"]).exists()


# --------------------------------------------------------------------------- #
# Adapter: submit safety — the headline behavior
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize("transcript,capture_ok", [
    (SHELL_T, True),
    (BUSY_CLAUDE_T, True),
    (BLOCKED_T, True),
    (UNKNOWN_T, True),
    ("", False),  # absent
])
def test_submit_refuses_non_ready(store, tmp_path, transcript, capture_ok):
    task = tmp_path / "task.md"
    task.write_text("SECRET TASK BODY")
    adapter = LaneAdapter(store, tmux=FakeTmux(transcript=transcript, capture_ok=capture_ok))
    with pytest.raises(LaneError):
        adapter.submit("Conductor:claude", str(task))


def test_submit_sends_only_short_reference_when_ready(store, tmp_path, monkeypatch):
    task = tmp_path / "task.md"
    task.write_text("SECRET TASK BODY that must NOT be pasted into the pane")
    fake = FakeTmux(transcript=READY_CLAUDE_T)
    adapter = LaneAdapter(store, tmux=fake)
    sleeps = []
    monkeypatch.setattr("conductor.lanes.time.sleep", sleeps.append)

    result = adapter.submit("Conductor:claude", str(task))
    assert result["submitted"] is True
    assert result["state"] == "provider_ready"

    # Exactly one literal send + one Enter.
    assert len(fake.sent) == 1
    assert fake.entered == 1
    assert sleeps == []
    sent_text = fake.sent[0][1]
    # The instruction references the path, never the body.
    assert str(task) in sent_text
    assert "SECRET TASK BODY" not in sent_text
    assert sent_text == result["instruction"]


def test_submit_delays_enter_for_codex_tui(store, tmp_path, monkeypatch):
    task = tmp_path / "task.md"
    task.write_text("body")
    ready_codex = "╭ OpenAI Codex ╮\n› Use /skills to list available skills\n"
    fake = FakeTmux(transcript=ready_codex)
    adapter = LaneAdapter(store, tmux=fake)
    sleeps = []
    monkeypatch.setattr("conductor.lanes.time.sleep", sleeps.append)

    result = adapter.submit("Conductor:codex", str(task))

    assert result["submitted"] is True
    assert len(fake.sent) == 1
    assert fake.entered == 1
    assert sleeps == [0.5]


def test_submit_force_overrides_gate(store, tmp_path):
    task = tmp_path / "task.md"
    task.write_text("body")
    fake = FakeTmux(transcript=SHELL_T)  # would normally refuse
    adapter = LaneAdapter(store, tmux=fake)
    result = adapter.submit("Conductor:claude", str(task), force=True)
    assert result["submitted"] is True
    assert result["forced"] is True


def test_submit_missing_task_file_errors_even_when_ready(store):
    adapter = LaneAdapter(store, tmux=FakeTmux(transcript=READY_CLAUDE_T))
    with pytest.raises(LaneError):
        adapter.submit("Conductor:claude", "/no/such/task.md")


# --------------------------------------------------------------------------- #
# Delivery events / heartbeat
# --------------------------------------------------------------------------- #
def test_submit_records_delivery_event(store, tmp_path):
    task = tmp_path / "task.md"
    task.write_text("body")
    adapter = LaneAdapter(store, tmux=FakeTmux(transcript=READY_CLAUDE_T))
    adapter.submit("Conductor:claude", str(task))

    events = read_jsonl(store.events_path)
    assert any(e.get("event") == "lane_submit" for e in events)

    rec = store.read_lane_record_path(store.lanes_dir / "Conductor_claude.json")
    assert rec.last_submit_at is not None
    assert rec.last_event["event"] == "lane_submit"


def test_refused_submit_records_event(store, tmp_path):
    task = tmp_path / "task.md"
    task.write_text("body")
    adapter = LaneAdapter(store, tmux=FakeTmux(transcript=SHELL_T))
    with pytest.raises(LaneError):
        adapter.submit("Conductor:claude", str(task))
    events = read_jsonl(store.events_path)
    assert any(e.get("event") == "lane_submit_refused" for e in events)


def test_ensure_creates_window_and_persists(store):
    fake = FakeTmux(transcript=SHELL_T)
    adapter = LaneAdapter(store, tmux=fake)
    result = adapter.ensure("Conductor:claude")
    assert ("Conductor", "claude") in fake.ensured
    assert result["state"] == "shell"
    assert list_lane_status(store)[0]["target"] == "Conductor:claude"


def test_ensure_without_tmux_raises(store):
    adapter = LaneAdapter(store, tmux=FakeTmux(available=False))
    with pytest.raises(LaneError):
        adapter.ensure("Conductor:claude")


# --------------------------------------------------------------------------- #
# Field regressions: codex update-menu incident (2026-07-07)
# --------------------------------------------------------------------------- #
CODEX_UPDATE_MENU_T = (
    "  ✨ Update available! 0.141.0 -> 0.142.4\n"
    "› 1. Update now (runs `npm install -g @openai/codex`)\n"
    "  2. Skip\n"
    "  Press enter to continue"
)
CODEX_DEAD_SCROLLBACK_T = (
    # Real shape from the incident: the update MENU is still in scrollback
    # (contains '\u203a ' and 'Press enter to continue'), followed by the
    # update output, a bare shell prompt, and viewport-padding blank lines.
    "\u203a 1. Update now (runs `npm install -g @openai/codex`)\n"
    "  2. Skip\n"
    "  Press enter to continue\n"
    "Updating Codex via `npm install -g @openai/codex`...\n"
    "changed 2 packages in 3s\n"
    "\U0001f389 Update ran successfully! Please restart Codex.\n"
    "user@host:~/projects/x$ \n" + "\n" * 39
)
CODEX_READY_T = (
    "─ Worked for 3s ────\n"
    "› Explain this codebase\n"
    "  esc again to edit previous message"
)


def test_codex_update_menu_is_blocked_not_ready():
    """The bare 'codex' ready-substring once classified an update menu as
    provider_ready; the submitted instruction's Enter selected 'Update now'."""
    state = classify(CODEX_UPDATE_MENU_T, provider_profile("codex"))
    assert state is LaneState.BLOCKED_PROMPT


def test_codex_dead_pane_with_scrollback_is_shell():
    """Scrollback containing the word 'codex' must not read as provider_ready
    once the CLI has exited back to a shell (this blocked relaunch recovery)."""
    state = classify(CODEX_DEAD_SCROLLBACK_T, provider_profile("codex"))
    assert state is LaneState.SHELL


def test_codex_real_ready_ui_classifies_ready():
    state = classify(CODEX_READY_T, provider_profile("codex"))
    assert state is LaneState.PROVIDER_READY


class DyingTmux(FakeTmux):
    """Provider accepts the send but the pane reads shell right after —
    reproduces codex exiting mid-submission."""

    def send_text(self, target, text):
        super().send_text(target, text)
        self.transcript = SHELL_T
        return True


def test_submit_delivery_confirmation_catches_dead_provider(store, tmp_path):
    task = tmp_path / "task.md"
    task.write_text("body")
    fake = DyingTmux(transcript=READY_CLAUDE_T)
    adapter = LaneAdapter(store, tmux=fake)
    with pytest.raises(LaneError, match="did not reach a provider"):
        adapter.submit("Conductor:claude", str(task))
    events = read_jsonl(store.events_path)
    assert any(e.get("event") == "lane_submit_delivery_failed" for e in events)
    # No lane_submit success event — the task stays retryable upstream.
    assert not any(e.get("event") == "lane_submit" for e in events)
