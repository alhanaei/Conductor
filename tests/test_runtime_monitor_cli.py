"""T5 CLI contracts for event-assisted monitor lifecycle and recovery."""

import json
import time

import conductor.cli as cli
import conductor.doctor as doctor_module
from conductor.cli import main
from conductor.runtime.events import (
    EventCursor,
    RuntimeEvent,
    RuntimeEventKind,
    RuntimeEventLedger,
)
from conductor.store import ConductorStore


def _run(capsys, *argv):
    code = main(list(argv))
    output = capsys.readouterr().out
    return code, json.loads(output) if output.strip() else None, output


def _store(tmp_path, capsys):
    code, _, _ = _run(capsys, "--root", str(tmp_path), "init", "--json")
    assert code == 0
    return ConductorStore(tmp_path / ".conductor")


def test_monitor_status_reports_health_cursor_freshness_and_gaps(
    tmp_path, capsys, monkeypatch
):
    store = _store(tmp_path, capsys)
    ledger = RuntimeEventLedger(store)
    ledger.append(
        RuntimeEvent(
            source="fs_artifact",
            source_key="artifact:one",
            kind=RuntimeEventKind.ARTIFACT_MODIFIED,
            observed_at="2026-07-21T00:00:00+00:00",
            track_id="track_1",
            payload={"artifact": "message_bus"},
        )
    )
    ledger.write_cursor(EventCursor(source_id="fs_artifact", position="artifact:one"))
    ledger.record_gap("fs_artifact", "filesystem watcher overflow")
    monkeypatch.setattr(cli, "control_mode_supported", lambda: (True, "tmux 3.4"))
    monkeypatch.setattr(
        cli.InotifyWatcher, "probe", classmethod(lambda cls: (True, "inotify available"))
    )

    code, data, raw = _run(
        capsys,
        "--root",
        str(tmp_path),
        "monitor",
        "status",
        "--track",
        "track_1",
        "--json",
    )

    assert code == 0, raw
    assert data["ok"] is True
    assert data["track_id"] == "track_1"
    assert data["source_health"]["tmux_control"]["ok"] is True
    assert data["source_health"]["filesystem"]["ok"] is True
    assert data["cursors"]["fs_artifact"]["position"] == "artifact:one"
    assert data["event_freshness"]["last_event_at"]
    assert data["gaps"]["count"] == 1
    assert data["gaps"]["latest"]["payload"]["reason"] == "filesystem watcher overflow"


def test_monitor_run_owns_sources_records_missing_cursor_and_never_sleeps(
    tmp_path, capsys, monkeypatch
):
    store = _store(tmp_path, capsys)
    event = RuntimeEvent(
        source="fake_source",
        source_key="message:one",
        kind=RuntimeEventKind.ARTIFACT_CREATED,
        track_id="track_1",
        payload={"artifact": "message_bus"},
    )

    class FakeSource:
        source_id = "fake_source"

        def __init__(self):
            self.started = 0
            self.closed = 0
            self._events = [event]

        def start(self):
            self.started += 1

        def read_events(self, timeout):
            events = list(self._events)
            self._events.clear()
            return events

        def gap_reason(self):
            return None

        def close(self):
            self.closed += 1

    source = FakeSource()
    monkeypatch.setattr(cli, "_build_monitor_sources", lambda store, track_id: [source])

    def fail_sleep(_seconds):
        raise AssertionError("monitor run must not use time.sleep")

    monkeypatch.setattr(time, "sleep", fail_sleep)
    code, data, raw = _run(
        capsys,
        "--root",
        str(tmp_path),
        "monitor",
        "run",
        "--track",
        "track_1",
        "--once",
        "--event-timeout",
        "0",
        "--json",
    )

    assert code == 0, raw
    assert source.started == 1
    assert source.closed == 1
    assert data["foreground"] is True
    assert data["processed_count"] == 1
    assert data["missing_cursor_gaps"] == 1
    kinds = [item.kind for item in RuntimeEventLedger(store).iter_events()]
    assert kinds.count(RuntimeEventKind.EVENT_STREAM_GAP) == 1
    assert kinds.count(RuntimeEventKind.RECONCILIATION) == 1
    assert RuntimeEventLedger(store).read_cursor("fake_source").position == event.event_id


def test_monitor_refresh_and_reconcile_are_explicit_audited_single_passes(
    tmp_path, capsys
):
    store = _store(tmp_path, capsys)

    for command in ("refresh", "reconcile"):
        code, data, raw = _run(
            capsys,
            "--root",
            str(tmp_path),
            "monitor",
            command,
            "--track",
            "track_1",
            "--reason",
            f"operator {command}",
            "--json",
        )
        assert code == 0, raw
        assert data["reconciled"] is True
        assert data["lanes_checked"] == 0
        assert data["gap_event_id"]
        assert data["reconciliation_event_id"]

    events = list(RuntimeEventLedger(store).iter_events())
    assert sum(e.kind is RuntimeEventKind.EVENT_STREAM_GAP for e in events) == 2
    assert sum(e.kind is RuntimeEventKind.RECONCILIATION for e in events) == 2


def test_doctor_reports_tmux_control_and_filesystem_notification_health(
    tmp_path, capsys, monkeypatch
):
    _store(tmp_path, capsys)
    monkeypatch.setattr(
        doctor_module, "control_mode_supported", lambda: (True, "tmux 3.4")
    )
    monkeypatch.setattr(
        doctor_module.InotifyWatcher,
        "probe",
        classmethod(lambda cls: (True, "inotify available")),
    )

    code, data, raw = _run(
        capsys, "--root", str(tmp_path), "doctor", "--json"
    )

    assert code == 0, raw
    checks = {check["name"]: check for check in data["checks"]}
    assert checks["tmux_control_mode"] == {
        "name": "tmux_control_mode",
        "ok": True,
        "detail": "tmux 3.4",
    }
    assert checks["filesystem_notifications"] == {
        "name": "filesystem_notifications",
        "ok": True,
        "detail": "inotify available",
    }
