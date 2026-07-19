"""Tmux-backed lane runtime."""

from __future__ import annotations

from typing import Any, Dict, Optional

from ..lanes import LaneAdapter


class TmuxLaneRuntime:
    """Internal runtime wrapper that delegates directly to :class:`LaneAdapter`."""

    def __init__(self, adapter: LaneAdapter):
        self.adapter = adapter

    def ensure(self, target: str) -> Dict[str, Any]:
        return self.adapter.ensure(target)

    def launch(
        self,
        target: str,
        model: Optional[str] = None,
        wait_seconds: float = 15.0,
        poll: float = 1.0,
    ) -> Dict[str, Any]:
        return self.adapter.launch(
            target, model=model, wait_seconds=wait_seconds, poll=poll
        )

    def status(self, target: str) -> Dict[str, Any]:
        return self.adapter.status(target)

    def capture(self, target: str, lines: int = 200) -> Dict[str, Any]:
        return self.adapter.capture(target, lines=lines)

    def submit(self, target: str, task_file: str, force: bool = False) -> Dict[str, Any]:
        return self.adapter.submit(target, task_file, force=force)

    def send_instruction(
        self,
        target: str,
        instruction: str,
        force: bool = False,
        kind: str = "lane_instruction",
    ) -> Dict[str, Any]:
        return self.adapter.send_instruction(
            target, instruction, force=force, kind=kind
        )
