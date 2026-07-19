"""Internal lane runtime interface.

This is a Conductor-owned contract over lane operations. It intentionally does
not expose an external runtime plug-in surface; Phase A only normalizes the
existing tmux adapter behavior behind a small internal interface.
"""

from __future__ import annotations

from typing import Any, Dict, Optional, Protocol


class LaneRuntime(Protocol):
    """Operations a Conductor lane runtime must provide."""

    def ensure(self, target: str) -> Dict[str, Any]:
        ...

    def launch(
        self,
        target: str,
        model: Optional[str] = None,
        wait_seconds: float = 15.0,
        poll: float = 1.0,
    ) -> Dict[str, Any]:
        ...

    def status(self, target: str) -> Dict[str, Any]:
        ...

    def capture(self, target: str, lines: int = 200) -> Dict[str, Any]:
        ...

    def submit(self, target: str, task_file: str, force: bool = False) -> Dict[str, Any]:
        ...

    def send_instruction(
        self,
        target: str,
        instruction: str,
        force: bool = False,
        kind: str = "lane_instruction",
    ) -> Dict[str, Any]:
        ...
