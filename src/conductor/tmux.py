"""Thin tmux client — the single seam between Conductor and the tmux process.

Every method shells out to ``tmux`` via an **argument array** (`subprocess.run`
with a list, no shell string), so untrusted target text can never be
interpreted by a shell. The :class:`LaneAdapter` depends only on this narrow
interface, which lets unit tests inject a fake with the same shape and never
touch a real tmux server.

Design constraint (from the build plan): no retry framework, no daemon
supervisor — just direct, inspectable calls that degrade cleanly when tmux is
absent.
"""

from __future__ import annotations

import shutil
import subprocess
from typing import List, Tuple


def control_attach_args(session: str) -> List[str]:
    """Return argument-array tokens for a read-only tmux control client."""
    if not session or "\0" in session:
        raise ValueError("tmux control session must be non-empty and contain no NUL")
    return ["-C", "attach-session", "-t", f"={session}"]


def control_mode_supported(binary: str = "tmux", timeout: float = 2.0) -> Tuple[bool, str]:
    """Probe whether the configured tmux supports control mode."""
    import re

    if shutil.which(binary) is None:
        return False, f"{binary} is not available"
    try:
        result = subprocess.run(
            [binary, "-V"], capture_output=True, text=True, timeout=timeout, check=False
        )
    except (OSError, subprocess.SubprocessError) as exc:
        return False, f"tmux version probe failed: {exc}"
    detail = (result.stdout or result.stderr).strip()
    if result.returncode != 0:
        return False, detail or f"tmux version probe exited {result.returncode}"
    match = re.search(r"tmux (\d+)\.(\d+)", detail)
    if match and (int(match.group(1)), int(match.group(2))) < (1, 8):
        return False, f"{detail}; control mode requires tmux >= 1.8"
    return True, detail or "tmux control mode available"


class TmuxClient:
    def __init__(self, binary: str = "tmux", timeout: float = 5.0):
        self.binary = binary
        self.timeout = timeout

    # -- availability ------------------------------------------------------- #
    def available(self) -> bool:
        """True if a ``tmux`` binary is on PATH."""
        return shutil.which(self.binary) is not None

    def _run(self, args: List[str]) -> subprocess.CompletedProcess:
        return subprocess.run(
            [self.binary, *args],
            capture_output=True,
            text=True,
            timeout=self.timeout,
            check=False,
        )

    # -- reads -------------------------------------------------------------- #
    def capture(self, target: str, lines: int = 200) -> Tuple[bool, str]:
        """Capture up to ``lines`` of recent pane history for ``target``.

        Returns ``(ok, text)``. ``ok`` is False when the session/window/pane does
        not exist (tmux exits non-zero) — the caller treats that as ``absent``.
        """
        args = ["capture-pane", "-p", "-t", target]
        if lines and lines > 0:
            args += ["-S", f"-{int(lines)}"]
        try:
            res = self._run(args)
        except (OSError, subprocess.SubprocessError):
            return False, ""
        return (res.returncode == 0, res.stdout if res.returncode == 0 else "")

    def has_session(self, session: str) -> bool:
        try:
            return self._run(["has-session", "-t", session]).returncode == 0
        except (OSError, subprocess.SubprocessError):
            return False

    def list_windows(self, session: str) -> List[str]:
        try:
            res = self._run(["list-windows", "-t", session, "-F", "#{window_name}"])
        except (OSError, subprocess.SubprocessError):
            return []
        if res.returncode != 0:
            return []
        return [w for w in res.stdout.splitlines() if w]

    # -- writes ------------------------------------------------------------- #
    def send_text(self, target: str, text: str) -> bool:
        """Send literal text (no key interpretation) to the pane."""
        try:
            # '--' terminates options so text starting with '-' is safe.
            res = self._run(["send-keys", "-t", target, "-l", "--", text])
            return res.returncode == 0
        except (OSError, subprocess.SubprocessError):
            return False

    def send_enter(self, target: str) -> bool:
        try:
            return self._run(["send-keys", "-t", target, "Enter"]).returncode == 0
        except (OSError, subprocess.SubprocessError):
            return False

    def ensure(self, session: str, window: str) -> bool:
        """Ensure ``session:window`` exists, creating a detached shell if needed.

        Note: this creates a *shell* window only. Launching a provider CLI
        (claude/codex/...) inside it is deliberately out of scope for Phase 3.
        """
        try:
            if not self.has_session(session):
                res = self._run(["new-session", "-d", "-s", session, "-n", window])
                return res.returncode == 0
            if window not in self.list_windows(session):
                res = self._run(["new-window", "-t", session, "-n", window])
                return res.returncode == 0
            return True
        except (OSError, subprocess.SubprocessError):
            return False
