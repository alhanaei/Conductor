"""Phase A runtime contract over the existing tmux lane adapter."""

import pytest

from conductor.lanes import LaneAdapter, LaneError
from conductor.models import LaneState
from conductor.runtime import TmuxLaneRuntime
from conductor.store import ConductorStore


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


class RecordingAdapter:
    def __init__(self):
        self.calls = []

    def ensure(self, target):
        self.calls.append(("ensure", target))
        return {"op": "ensure", "target": target}

    def launch(self, target, model=None, wait_seconds=15.0, poll=1.0):
        self.calls.append(("launch", target, model, wait_seconds, poll))
        return {"op": "launch", "target": target, "model": model}

    def status(self, target):
        self.calls.append(("status", target))
        return {"op": "status", "target": target}

    def capture(self, target, lines=200):
        self.calls.append(("capture", target, lines))
        return {"op": "capture", "target": target, "lines": lines}

    def submit(self, target, task_file, force=False):
        self.calls.append(("submit", target, task_file, force))
        return {"op": "submit", "target": target, "task_file": task_file, "force": force}

    def send_instruction(self, target, instruction, force=False, kind="lane_instruction"):
        self.calls.append(("send_instruction", target, instruction, force, kind))
        return {"op": "send_instruction", "target": target, "instruction": instruction}


@pytest.fixture()
def store(tmp_path):
    return ConductorStore.resolve(root=tmp_path, create=True)


READY_CLAUDE_T = "│ > type here │\n? for shortcuts"
SHELL_T = "user@host:~/repo$ "
BUSY_T = "✻ Thinking… (esc to interrupt)\n"
BLOCKED_T = "Do you want to proceed?\n❯ 1. Yes\n  2. No"
UNKNOWN_T = "plain output\nwithout a provider prompt"


def test_tmux_runtime_delegates_adapter_operations_without_reshaping():
    adapter = RecordingAdapter()
    runtime = TmuxLaneRuntime(adapter)

    assert runtime.ensure("Conductor:claude") == {"op": "ensure", "target": "Conductor:claude"}
    assert runtime.launch("Conductor:claude", model="m", wait_seconds=2.0, poll=0.25) == {
        "op": "launch",
        "target": "Conductor:claude",
        "model": "m",
    }
    assert runtime.status("Conductor:claude") == {"op": "status", "target": "Conductor:claude"}
    assert runtime.capture("Conductor:claude", lines=25) == {
        "op": "capture",
        "target": "Conductor:claude",
        "lines": 25,
    }
    assert runtime.submit("Conductor:claude", "task.md", force=True) == {
        "op": "submit",
        "target": "Conductor:claude",
        "task_file": "task.md",
        "force": True,
    }
    assert runtime.send_instruction("Conductor:claude", "Read task.md", kind="followup") == {
        "op": "send_instruction",
        "target": "Conductor:claude",
        "instruction": "Read task.md",
    }

    assert adapter.calls == [
        ("ensure", "Conductor:claude"),
        ("launch", "Conductor:claude", "m", 2.0, 0.25),
        ("status", "Conductor:claude"),
        ("capture", "Conductor:claude", 25),
        ("submit", "Conductor:claude", "task.md", True),
        ("send_instruction", "Conductor:claude", "Read task.md", False, "followup"),
    ]


def test_tmux_runtime_does_not_catch_or_weaken_lane_errors():
    class FailingAdapter(RecordingAdapter):
        def submit(self, target, task_file, force=False):
            raise LaneError("exact refusal")

    runtime = TmuxLaneRuntime(FailingAdapter())

    with pytest.raises(LaneError, match="exact refusal"):
        runtime.submit("Conductor:claude", "task.md")


@pytest.mark.parametrize(
    "transcript,capture_ok,expected",
    [
        (SHELL_T, True, LaneState.SHELL),
        (BUSY_T, True, LaneState.BUSY),
        (BLOCKED_T, True, LaneState.BLOCKED_PROMPT),
        (UNKNOWN_T, True, LaneState.UNKNOWN),
        ("", False, LaneState.ABSENT),
    ],
)
def test_tmux_runtime_preserves_lane_adapter_safe_delivery_refusals(
    store, tmp_path, transcript, capture_ok, expected
):
    task = tmp_path / "task.md"
    task.write_text("body")
    fake = FakeTmux(transcript=transcript, capture_ok=capture_ok)
    adapter = LaneAdapter(store, tmux=fake)
    runtime = TmuxLaneRuntime(adapter)

    with pytest.raises(LaneError, match="refusing to submit"):
        runtime.submit("Conductor:claude", str(task))

    assert fake.sent == []
    record = store.read_lane_record_path(store.lanes_dir / "Conductor_claude.json")
    assert record.state is expected


def test_tmux_runtime_submits_ready_lane_through_adapter(store, tmp_path):
    task = tmp_path / "task.md"
    task.write_text("body")
    fake = FakeTmux(transcript=READY_CLAUDE_T)
    adapter = LaneAdapter(store, tmux=fake)
    runtime = TmuxLaneRuntime(adapter)

    result = runtime.submit("Conductor:claude", str(task))

    assert result["submitted"] is True
    assert result["state"] == "provider_ready"
    assert len(fake.sent) == 1
    assert fake.entered == 1
