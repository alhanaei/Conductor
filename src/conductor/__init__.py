"""Conductor — local-first, artifact-driven control plane for coding-agent CLIs.

Phase 1 kernel: state root, tracks, append-only message bus, OS-level file
locks, worker-status/heartbeat projections, and a JSON-first CLI.
"""

from .models import SCHEMA_VERSION

__version__ = "0.1.0"

__all__ = ["SCHEMA_VERSION", "__version__"]
