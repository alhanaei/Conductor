"""Incremental tmux control-mode source for runtime pane events."""

from __future__ import annotations

import hashlib
import select
import subprocess
from dataclasses import dataclass
from typing import Any, Callable, Dict, List, Optional

from ..tmux import control_attach_args
from .events import RuntimeEvent, RuntimeEventKind


@dataclass(frozen=True)
class ControlLine:
    kind: str
    pane_id: Optional[str] = None
    data: Optional[bytes] = None
    raw: str = ""


_FRAME_RECORDS = {"%begin", "%end", "%error"}
_LIFECYCLE_PREFIXES = (
    "%window-",
    "%session-",
    "%pane-",
    "%layout-change",
    "%client-session-changed",
    "%sessions-changed",
)


def _decode_control_bytes(value: str) -> bytes:
    decoded = bytearray()
    index = 0
    while index < len(value):
        if (
            value[index] == "\\"
            and index + 3 < len(value)
            and all(char in "01234567" for char in value[index + 1:index + 4])
        ):
            decoded.append(int(value[index + 1:index + 4], 8))
            index += 4
            continue
        decoded.extend(value[index].encode("utf-8"))
        index += 1
    return bytes(decoded)


def parse_control_line(raw: str) -> ControlLine:
    """Parse one tmux control-mode line without mutating client state."""
    line = raw.rstrip("\r\n")
    if not line:
        return ControlLine(kind="malformed", raw=line)
    parts = line.split(" ", 2)
    notification = parts[0]
    if notification == "%output" and len(parts) == 3 and parts[1].startswith("%"):
        return ControlLine(
            kind="output",
            pane_id=parts[1],
            data=_decode_control_bytes(parts[2]),
            raw=line,
        )
    if notification in _FRAME_RECORDS:
        return ControlLine(kind="frame", raw=line)
    if notification == "%exit":
        reason = line.partition(" ")[2].encode("utf-8")
        return ControlLine(kind="exit", data=reason, raw=line)
    if notification.startswith(_LIFECYCLE_PREFIXES):
        pane_id = next((part for part in parts[1:] if part.startswith("%")), None)
        return ControlLine(kind="lifecycle", pane_id=pane_id, raw=line)
    return ControlLine(kind="malformed", raw=line)


class TmuxControlClient:
    """Own one tmux control-mode process for one tmux session."""

    tail_limit = 4096

    def __init__(
        self,
        session: str,
        spawn: Optional[Callable[[], Any]] = None,
        reader: Optional[Callable[[float], Optional[str]]] = None,
        pane_loader: Optional[Callable[[], Dict[str, str]]] = None,
        binary: str = "tmux",
    ):
        if not session:
            raise ValueError("tmux control session is required")
        self.session = session
        self.binary = binary
        self._spawn = spawn or self._spawn_process
        self._reader = reader
        self._pane_loader = pane_loader or self._load_pane_targets
        self._process: Optional[Any] = None
        self._pane_targets: Dict[str, str] = {}
        self._gap: Optional[str] = None
        self.malformed_records = 0
        self.started = False

    @property
    def source_id(self) -> str:
        return f"tmux_control:{self.session}"

    def _spawn_process(self) -> subprocess.Popen:
        return subprocess.Popen(
            [self.binary, *control_attach_args(self.session)],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            bufsize=1,
        )

    def _load_pane_targets(self) -> Dict[str, str]:
        result = subprocess.run(
            [
                self.binary,
                "list-panes",
                "-t",
                f"={self.session}",
                "-F",
                "#{pane_id}\t#{session_name}:#{window_name}",
            ],
            capture_output=True,
            text=True,
            timeout=5.0,
            check=False,
        )
        if result.returncode != 0:
            return {}
        targets: Dict[str, str] = {}
        for line in result.stdout.splitlines():
            pane_id, separator, target = line.partition("\t")
            if separator and pane_id.startswith("%") and target:
                targets[pane_id] = target
        return targets

    def start(self) -> None:
        if self.started:
            return
        process = self._spawn()
        self._process = process
        try:
            self._pane_targets = dict(self._pane_loader())
        except Exception:
            self._process = None
            if process is not None and getattr(process, "poll", lambda: 0)() is None:
                process.terminate()
            raise
        self._gap = None
        self.started = True

    def _read_line(self, timeout: float) -> Optional[str]:
        if self._reader is not None:
            return self._reader(timeout)
        if self._process is None or self._process.stdout is None:
            return ""
        ready, _, _ = select.select([self._process.stdout], [], [], max(0.0, timeout))
        if not ready:
            return None
        return self._process.stdout.readline()

    def _set_gap(self, reason: str) -> None:
        if self._gap is None:
            self._gap = reason

    def _output_event(self, record: ControlLine) -> RuntimeEvent:
        assert record.pane_id is not None and record.data is not None
        digest = hashlib.sha256(record.data).hexdigest()
        tail = record.data.decode("utf-8", errors="replace")[-self.tail_limit:]
        return RuntimeEvent(
            source=self.source_id,
            source_key=f"{record.pane_id}:{digest}",
            kind=RuntimeEventKind.PANE_OUTPUT,
            lane_target=self._pane_targets.get(record.pane_id),
            payload={"tail": tail, "pane_id": record.pane_id},
        )

    def _lifecycle_event(self, record: ControlLine) -> RuntimeEvent:
        notification = record.raw.split(" ", 1)[0]
        lane_target = self._pane_targets.get(record.pane_id or "")
        if notification in ("%pane-exited", "%pane-died") and record.pane_id:
            self._pane_targets.pop(record.pane_id, None)
        digest = hashlib.sha256(record.raw.encode("utf-8")).hexdigest()
        return RuntimeEvent(
            source=self.source_id,
            source_key=f"lifecycle:{digest}",
            kind=RuntimeEventKind.PANE_LIFECYCLE,
            lane_target=lane_target,
            payload={
                "notification": notification,
                "pane_id": record.pane_id,
                "raw": record.raw[-self.tail_limit:],
            },
        )

    def read_events(self, timeout: float = 1.0) -> List[RuntimeEvent]:
        if not self.started:
            raise RuntimeError("tmux control client is not started")
        if self._gap is not None:
            return []
        if self._process is not None:
            returncode = self._process.poll()
            if returncode is not None:
                self._set_gap(f"tmux control process exited with status {returncode}")
                return []

        events: List[RuntimeEvent] = []
        next_timeout = timeout
        while True:
            line = self._read_line(next_timeout)
            next_timeout = 0.0
            if line is None:
                break
            if line == "":
                self._set_gap("tmux control stream EOF")
                break
            record = parse_control_line(line)
            if record.kind == "output":
                events.append(self._output_event(record))
            elif record.kind == "lifecycle":
                events.append(self._lifecycle_event(record))
            elif record.kind == "exit":
                reason = (record.data or b"").decode("utf-8", errors="replace")
                suffix = f": {reason}" if reason else ""
                self._set_gap(f"tmux control mode exited{suffix}")
                break
            elif record.kind == "malformed":
                self.malformed_records += 1
        return events

    def gap_reason(self) -> Optional[str]:
        return self._gap

    def stop(self) -> None:
        if not self.started:
            return
        process = self._process
        self.started = False
        self._process = None
        if process is None or process.poll() is not None:
            return
        process.terminate()
        try:
            process.wait(timeout=1.0)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=1.0)
