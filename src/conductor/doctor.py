"""Health checks for a Conductor state root (the Ruflo-style ``doctor``).

Each check returns a small dict ``{name, ok, detail}``. The aggregate ``ok`` is
the AND of all checks. ``doctor`` is intentionally read-only: it diagnoses, it
does not repair. Exit-code mapping lives in the CLI.
"""

from __future__ import annotations

import json
import os
from typing import Any, Dict, List

from .runtime.fs_events import InotifyWatcher
from .store import ConductorStore, read_json
from .tmux import control_mode_supported


def _check(name: str, ok: bool, detail: str) -> Dict[str, Any]:
    return {"name": name, "ok": bool(ok), "detail": detail}


def run_doctor(store: ConductorStore) -> Dict[str, Any]:
    checks: List[Dict[str, Any]] = []

    # 1. state root exists
    root_ok = store.root.is_dir()
    checks.append(_check("state_root_exists", root_ok, str(store.root)))

    # 2. config present and parseable
    config: Dict[str, Any] = {}
    if store.config_path.exists():
        try:
            config = read_json(store.config_path, {})
            checks.append(_check("config_readable", True, str(store.config_path)))
        except json.JSONDecodeError as exc:
            checks.append(_check("config_readable", False, f"corrupt conductor.json: {exc}"))
    else:
        checks.append(_check("config_readable", False, "conductor.json missing"))

    # 3. core directories
    for label, path in (("tracks_dir", store.tracks_dir), ("lanes_dir", store.lanes_dir)):
        checks.append(_check(label, path.is_dir(), str(path)))

    # 4. events log writable
    checks.append(_check("events_log", store.events_path.exists(), str(store.events_path)))

    # 5. write permission probe (does not leave a file behind)
    writable = os.access(str(store.root), os.W_OK) if root_ok else False
    checks.append(_check("root_writable", writable, "W_OK on state root"))

    # 6. native event-source capabilities
    tmux_ok, tmux_detail = control_mode_supported()
    checks.append(_check("tmux_control_mode", tmux_ok, tmux_detail))
    fs_ok, fs_detail = InotifyWatcher.probe()
    checks.append(_check("filesystem_notifications", fs_ok, fs_detail))

    # 7. per-track integrity: metadata + bus files parseable
    track_reports: List[Dict[str, Any]] = []
    for tid in store.list_track_ids():
        issues: List[str] = []
        if read_json(store.track_metadata_path(tid)) is None:
            issues.append("metadata.json unreadable")
        for label, path in (
            ("queue.jsonl", store.queue_path(tid)),
            ("worker-status.json", store.worker_status_path(tid)),
            ("locks.json", store.locks_path(tid)),
        ):
            if path.suffix == ".json" and path.exists():
                try:
                    read_json(path)
                except json.JSONDecodeError:
                    issues.append(f"{label} corrupt")
            elif path.suffix == ".jsonl" and not path.exists():
                issues.append(f"{label} missing")
        track_reports.append({"track_id": tid, "ok": not issues, "issues": issues})

    tracks_ok = all(t["ok"] for t in track_reports)
    checks.append(_check("tracks_integrity", tracks_ok,
                         f"{len(track_reports)} track(s) checked"))

    overall_ok = all(c["ok"] for c in checks)
    return {
        "ok": overall_ok,
        "state_root": str(store.root),
        "schema_version": config.get("schema_version"),
        "checks": checks,
        "tracks": track_reports,
    }
