"""T2 tests for the tmux control-mode event source."""

import hashlib
import os
import subprocess
import time

import pytest

from conductor.runtime.events import RuntimeEventKind
from conductor.runtime.tmux_control import (
    TmuxControlClient,
    parse_control_line,
)
from conductor.tmux import control_attach_args


class SequenceReader:
    def __init__(self, lines):
        self.lines = list(lines)
        self.timeouts = []

    def __call__(self, timeout):
        self.timeouts.append(timeout)
        if not self.lines:
            return None
        return self.lines.pop(0)


class FakeProcess:
    def __init__(self):
        self.returncode = None
        self.terminate_calls = 0
        self.kill_calls = 0
        self.wait_calls = 0

    def poll(self):
        return self.returncode

    def terminate(self):
        self.terminate_calls += 1
        self.returncode = 0

    def wait(self, timeout=None):
        self.wait_calls += 1
        return self.returncode

    def kill(self):
        self.kill_calls += 1
        self.returncode = -9


def test_control_attach_args_are_read_only_and_session_exact():
    assert control_attach_args("Project") == [
        "-C",
        "attach-session",
        "-t",
        "=Project",
    ]


@pytest.mark.parametrize(
    "raw,kind",
    [
        ("%begin 1 2 3", "frame"),
        ("%end 1 2 3", "frame"),
        ("%error 1 2 3", "frame"),
        ("%window-close @1", "lifecycle"),
        ("%window-renamed @1 work", "lifecycle"),
        ("%session-changed $1 Project", "lifecycle"),
        ("%exit detached", "exit"),
        ("not-control-mode", "malformed"),
    ],
)
def test_parse_control_line_classifies_records(raw, kind):
    assert parse_control_line(raw).kind == kind


def test_parse_control_line_decodes_output_bytes():
    parsed = parse_control_line(r"%output %7 hello\040world\012")

    assert parsed.kind == "output"
    assert parsed.pane_id == "%7"
    assert parsed.data == b"hello world\n"


def test_mapped_output_becomes_bounded_runtime_event():
    data = "x" * 5000
    reader = SequenceReader([f"%output %1 {data}", None])
    process = FakeProcess()
    client = TmuxControlClient(
        "Project",
        spawn=lambda: process,
        reader=reader,
        pane_loader=lambda: {"%1": "Project:codex"},
    )
    client.start()

    events = client.read_events(timeout=0.25)

    assert len(events) == 1
    event = events[0]
    digest = hashlib.sha256(data.encode("utf-8")).hexdigest()
    assert event.kind is RuntimeEventKind.PANE_OUTPUT
    assert event.source == "tmux_control:Project"
    assert event.source_key == f"%1:{digest}"
    assert event.lane_target == "Project:codex"
    assert event.payload["pane_id"] == "%1"
    assert event.payload["tail"] == data[-4096:]
    assert reader.timeouts == [0.25, 0.0]


def test_unmapped_pane_never_invents_lane_owner():
    reader = SequenceReader(["%output %9 hello", None])
    client = TmuxControlClient(
        "Project",
        spawn=FakeProcess,
        reader=reader,
        pane_loader=lambda: {},
    )
    client.start()

    event = client.read_events()[0]

    assert event.kind is RuntimeEventKind.PANE_OUTPUT
    assert event.lane_target is None
    assert event.payload["pane_id"] == "%9"


def test_lifecycle_event_is_normalized_and_pane_exit_removes_mapping():
    reader = SequenceReader(["%pane-exited %1", "%output %1 stale", None])
    client = TmuxControlClient(
        "Project",
        spawn=FakeProcess,
        reader=reader,
        pane_loader=lambda: {"%1": "Project:codex"},
    )
    client.start()

    lifecycle, output = client.read_events()

    assert lifecycle.kind is RuntimeEventKind.PANE_LIFECYCLE
    assert lifecycle.payload["notification"] == "%pane-exited"
    assert output.lane_target is None


def test_frames_and_malformed_lines_are_skipped_nonfatally():
    reader = SequenceReader(["%begin 1 2 3", "bad", "%end 1 2 3", None])
    client = TmuxControlClient(
        "Project",
        spawn=FakeProcess,
        reader=reader,
        pane_loader=lambda: {},
    )
    client.start()

    assert client.read_events() == []
    assert client.malformed_records == 1
    assert client.gap_reason() is None


def test_exit_and_reader_eof_set_gap_without_event_owner():
    exit_reader = SequenceReader(["%exit server exited"])
    exit_client = TmuxControlClient(
        "Project",
        spawn=FakeProcess,
        reader=exit_reader,
        pane_loader=lambda: {},
    )
    exit_client.start()

    assert exit_client.read_events() == []
    assert exit_client.gap_reason() == "tmux control mode exited: server exited"

    eof_client = TmuxControlClient(
        "Project",
        spawn=FakeProcess,
        reader=SequenceReader([""]),
        pane_loader=lambda: {},
    )
    eof_client.start()

    assert eof_client.read_events() == []
    assert eof_client.gap_reason() == "tmux control stream EOF"


def test_spawn_death_sets_gap_once():
    process = FakeProcess()
    client = TmuxControlClient(
        "Project",
        spawn=lambda: process,
        reader=SequenceReader([]),
        pane_loader=lambda: {},
    )
    client.start()
    process.returncode = 7

    assert client.read_events() == []
    assert client.gap_reason() == "tmux control process exited with status 7"
    assert client.read_events() == []
    assert client.gap_reason() == "tmux control process exited with status 7"


def test_stop_is_explicit_and_idempotent():
    process = FakeProcess()
    client = TmuxControlClient(
        "Project",
        spawn=lambda: process,
        reader=SequenceReader([]),
        pane_loader=lambda: {},
    )
    client.start()

    client.stop()
    client.stop()

    assert process.terminate_calls == 1
    assert process.kill_calls == 0
    assert client.started is False


@pytest.mark.skipif(
    os.environ.get("CONDUCTOR_LIVE_TMUX") != "1",
    reason="set CONDUCTOR_LIVE_TMUX=1 for the gated real-tmux smoke",
)
def test_live_control_client_observes_its_session_output():
    session = f"conductor-live-{os.getpid()}"
    marker = f"CONDUCTOR_CONTROL_{os.getpid()}"
    subprocess.run(
        ["tmux", "new-session", "-d", "-s", session],
        check=True,
        capture_output=True,
        text=True,
    )
    client = TmuxControlClient(session)
    try:
        client.start()
        subprocess.run(
            ["tmux", "send-keys", "-t", f"{session}:0", f"printf {marker}", "Enter"],
            check=True,
            capture_output=True,
            text=True,
        )
        deadline = time.monotonic() + 3.0
        seen = []
        while time.monotonic() < deadline and not seen:
            seen.extend(client.read_events(timeout=0.2))
        assert any(
            event.kind is RuntimeEventKind.PANE_OUTPUT
            and marker in event.payload["tail"]
            for event in seen
        )
    finally:
        client.stop()
        subprocess.run(
            ["tmux", "kill-session", "-t", session],
            check=False,
            capture_output=True,
            text=True,
        )
