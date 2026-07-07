"""Make ``src/`` importable for tests even without an editable install."""

import sys
from pathlib import Path

import pytest

SRC = Path(__file__).resolve().parents[1] / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))


@pytest.fixture(autouse=True)
def _no_delivery_settle(monkeypatch):
    """Skip the post-send TUI settle delay in tests (0.4s x many submits)."""
    from conductor.lanes import LaneAdapter
    monkeypatch.setattr(LaneAdapter, "delivery_settle_seconds", 0)
