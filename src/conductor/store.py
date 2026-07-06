"""State-root resolution, atomic IO primitives, and the on-disk layout.

This module owns the ``.conductor/`` contract. Nothing above it should build
paths by hand. The two foundational guarantees it provides:

* **Atomic JSON projections** — :func:`atomic_write_json` writes to a temp file
  in the same directory, fsyncs, then ``os.replace``s it into place. A reader
  therefore never observes a half-written projection, even if the process dies
  mid-write.
* **Append-only logs** — :func:`append_jsonl` opens for append under an
  advisory ``flock`` so concurrent writers can't interleave partial lines.

Resolution precedence for the state root (highest first):
    explicit ``root=`` arg  >  ``$CONDUCTOR_HOME``  >  nearest ``.conductor/``
    walking up from ``cwd``  >  ``<cwd>/.conductor``.
"""

from __future__ import annotations

import json
import os
import tempfile
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Callable, Dict, Iterator, List, Optional

from .models import (
    SCHEMA_VERSION,
    DispatchRecord,
    LaneRecord,
    RouteDecision,
    Track,
    TrackRecord,
    TrackState,
    VerificationGate,
    utc_now_iso,
)

STATE_DIR_NAME = ".conductor"
ENV_HOME = "CONDUCTOR_HOME"

SPEC_TEMPLATE = """# Spec — {goal}

- track_id: {track_id}
- created_at: {created_at}
- status: draft (Phase 1 placeholder)

## Goal

{goal}

## Non-Goals

- _to be filled during planning (Phase 2)_

## Acceptance Criteria

- _to be filled during planning (Phase 2)_
"""

PLAN_TEMPLATE = """# Plan — {goal}

- track_id: {track_id}
- created_at: {created_at}
- status: draft (Phase 1 placeholder)

## Tasks

- [ ] _no tasks planned yet (Phase 2 will populate the DAG)_

## Verification

- _to be filled during planning (Phase 2)_
"""


# --------------------------------------------------------------------------- #
# Atomic / append-only IO primitives
# --------------------------------------------------------------------------- #
def _fsync_dir(directory: Path) -> None:
    """Best-effort directory fsync so a rename is durable. No-op where unsupported."""
    try:
        fd = os.open(str(directory), os.O_RDONLY)
    except OSError:
        return
    try:
        os.fsync(fd)
    except OSError:  # pragma: no cover - platform dependent
        pass
    finally:
        os.close(fd)


def atomic_write_text(path: Path, text: str) -> None:
    """Atomically replace ``path`` with ``text`` (temp file + fsync + os.replace)."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=str(path.parent), prefix=path.name + ".", suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            fh.write(text)
            fh.flush()
            os.fsync(fh.fileno())
        os.replace(tmp, path)
        _fsync_dir(path.parent)
    finally:
        if os.path.exists(tmp):
            os.unlink(tmp)


def atomic_write_json(path: Path, data: Any) -> None:
    """Atomically write ``data`` as pretty, stable-key JSON."""
    atomic_write_text(Path(path), json.dumps(data, indent=2, sort_keys=True) + "\n")


def read_json(path: Path, default: Any = None) -> Any:
    path = Path(path)
    if not path.exists():
        return default
    with path.open("r", encoding="utf-8") as fh:
        return json.load(fh)


def append_jsonl(path: Path, record: Dict[str, Any]) -> None:
    """Append one JSON record as a line, guarded by an advisory exclusive lock.

    The ``flock`` makes the append safe under concurrent writers: even if two
    processes append at once, neither sees a torn line. Each record is written
    on a single ``write()`` call followed by fsync for durability.
    """
    import fcntl  # local import keeps the module importable on non-POSIX for type checks

    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    line = json.dumps(record, sort_keys=True) + "\n"
    with path.open("a", encoding="utf-8") as fh:
        fcntl.flock(fh.fileno(), fcntl.LOCK_EX)
        try:
            fh.write(line)
            fh.flush()
            os.fsync(fh.fileno())
        finally:
            fcntl.flock(fh.fileno(), fcntl.LOCK_UN)


def read_jsonl(path: Path) -> List[Dict[str, Any]]:
    """Read every well-formed JSON line; blank lines are skipped.

    A trailing partial/corrupt line (possible if a writer was killed) is
    tolerated by skipping it rather than failing the whole read — the log is the
    source of truth and one bad tail line should not blind the operator.
    """
    path = Path(path)
    if not path.exists():
        return []
    out: List[Dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as fh:
        for raw in fh:
            raw = raw.strip()
            if not raw:
                continue
            try:
                out.append(json.loads(raw))
            except json.JSONDecodeError:
                continue
    return out


def iter_jsonl(path: Path) -> Iterator[Dict[str, Any]]:
    yield from read_jsonl(path)


@contextmanager
def file_mutex(path: Path, timeout: float = 10.0, poll: float = 0.02) -> Iterator[None]:
    """Hold an exclusive advisory ``flock`` on ``path`` for the block.

    Same non-blocking poll-loop pattern as :class:`conductor.locks.LockManager`:
    a wedged holder cannot pin us forever — we raise :class:`TimeoutError` after
    ``timeout``. Used to serialize read-modify-write cycles on JSON projections
    (the writes themselves are atomic; this prevents lost updates between two
    concurrent RMW sequences, e.g. ``loop --watch`` vs. an operator command).
    """
    import errno
    import fcntl
    import time

    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd = os.open(str(path), os.O_CREAT | os.O_RDWR, 0o644)
    deadline = time.monotonic() + timeout
    acquired = False
    try:
        while True:
            try:
                fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
                acquired = True
                break
            except OSError as exc:
                if exc.errno not in (errno.EAGAIN, errno.EACCES):
                    raise
                if time.monotonic() >= deadline:
                    raise TimeoutError(
                        f"could not acquire mutex {path} within {timeout}s"
                    ) from exc
                time.sleep(poll)
        yield
    finally:
        if acquired:
            import fcntl as _fcntl
            _fcntl.flock(fd, _fcntl.LOCK_UN)
        os.close(fd)


# --------------------------------------------------------------------------- #
# State-root resolution
# --------------------------------------------------------------------------- #
def find_state_root(start: Optional[Path] = None) -> Optional[Path]:
    """Return the nearest existing ``.conductor/`` walking up from ``start``."""
    if os.environ.get(ENV_HOME):
        candidate = Path(os.environ[ENV_HOME]).expanduser()
        return candidate if candidate.exists() else None
    cur = Path(start or Path.cwd()).resolve()
    for directory in [cur, *cur.parents]:
        candidate = directory / STATE_DIR_NAME
        if candidate.is_dir():
            return candidate
    return None


def default_state_root(start: Optional[Path] = None) -> Path:
    """Where a fresh ``.conductor/`` would be created if none exists yet."""
    if os.environ.get(ENV_HOME):
        return Path(os.environ[ENV_HOME]).expanduser()
    return Path(start or Path.cwd()).resolve() / STATE_DIR_NAME


# --------------------------------------------------------------------------- #
# Store
# --------------------------------------------------------------------------- #
class ConductorStore:
    """Thin filesystem facade over a single ``.conductor/`` root.

    A store instance does not cache mutable state in memory; every accessor
    reads from disk so two store objects (or two processes) always agree. That
    is what makes "state survives process restart" true by construction.
    """

    def __init__(self, root: Path):
        self.root = Path(root)

    # -- resolution helpers ------------------------------------------------- #
    @classmethod
    def resolve(cls, root: Optional[Path] = None, create: bool = False,
                start: Optional[Path] = None) -> ConductorStore:
        if root is not None:
            resolved = Path(root)
            if resolved.name != STATE_DIR_NAME:
                resolved = resolved / STATE_DIR_NAME
        else:
            existing = find_state_root(start)
            resolved = existing if existing is not None else default_state_root(start)
        store = cls(resolved)
        if create:
            store.init()
        elif not store.exists():
            raise FileNotFoundError(
                f"No Conductor state root found at {resolved}. Run 'conductor init' first."
            )
        return store

    def exists(self) -> bool:
        return (self.root / "conductor.json").exists()

    # -- path helpers ------------------------------------------------------- #
    @property
    def config_path(self) -> Path:
        return self.root / "conductor.json"

    @property
    def events_path(self) -> Path:
        return self.root / "events.jsonl"

    @property
    def tracks_dir(self) -> Path:
        return self.root / "tracks"

    @property
    def lanes_dir(self) -> Path:
        return self.root / "lanes"

    def track_dir(self, track_id: str) -> Path:
        return self.tracks_dir / track_id

    def message_bus_dir(self, track_id: str) -> Path:
        return self.track_dir(track_id) / ".message-bus"

    def queue_path(self, track_id: str) -> Path:
        return self.message_bus_dir(track_id) / "queue.jsonl"

    def events_dir(self, track_id: str) -> Path:
        return self.message_bus_dir(track_id) / "events"

    def worker_status_path(self, track_id: str) -> Path:
        return self.message_bus_dir(track_id) / "worker-status.json"

    def locks_path(self, track_id: str) -> Path:
        return self.message_bus_dir(track_id) / "locks.json"

    def lock_mutex_path(self, track_id: str) -> Path:
        return self.message_bus_dir(track_id) / ".lock_mutex"

    def track_metadata_path(self, track_id: str) -> Path:
        return self.track_dir(track_id) / "metadata.json"

    def track_mutex_path(self, track_id: str) -> Path:
        return self.track_dir(track_id) / ".metadata_mutex"

    def track_mutex(self, track_id: str, timeout: float = 10.0):
        """Per-track mutex guarding TrackRecord read-modify-write cycles.

        Hold this around any read → mutate → ``write_track_record`` sequence so a
        concurrent ``loop --watch`` and an operator command cannot silently lose
        each other's updates. Do NOT nest (flock on a second fd would deadlock);
        acquire only at the outermost operation level.
        """
        return file_mutex(self.track_mutex_path(track_id), timeout=timeout)

    def update_track_record(self, track_id: str,
                            mutate: Callable[[TrackRecord], None]) -> TrackRecord:
        """Atomically read-modify-write the track aggregate under the track mutex."""
        with self.track_mutex(track_id):
            record = self.read_track_record(track_id)
            if record is None:
                raise KeyError(f"unknown track: {track_id}")
            mutate(record)
            self.write_track_record(record)
            return record

    def definition_of_done_path(self, track_id: str) -> Path:
        return self.track_dir(track_id) / "definition_of_done.md"

    def quality_gates_path(self, track_id: str) -> Path:
        return self.track_dir(track_id) / "quality_gates.json"

    # -- init --------------------------------------------------------------- #
    def planned_layout(self) -> List[Path]:
        """Directories/files that :meth:`init` would create (for ``--dry-run``)."""
        return [
            self.root,
            self.tracks_dir,
            self.lanes_dir,
            self.config_path,
            self.events_path,
        ]

    def init(self) -> Dict[str, Any]:
        """Create the ``.conductor/`` skeleton; idempotent."""
        self.root.mkdir(parents=True, exist_ok=True)
        self.tracks_dir.mkdir(parents=True, exist_ok=True)
        self.lanes_dir.mkdir(parents=True, exist_ok=True)
        if not self.events_path.exists():
            self.events_path.touch()
        if not self.config_path.exists():
            config = {
                "schema_version": SCHEMA_VERSION,
                "state_dir": STATE_DIR_NAME,
                "created_at": utc_now_iso(),
                "project_root": str(self.root.parent),
            }
            atomic_write_json(self.config_path, config)
        return read_json(self.config_path, {})

    # -- tracks ------------------------------------------------------------- #
    def create_track(self, goal: str, track: Optional[Track] = None) -> Track:
        """Create a track directory with spec/plan placeholders, metadata, and bus."""
        if track is None:
            track = Track(goal=goal)
        else:
            track.goal = goal or track.goal
        track.validate()

        tdir = self.track_dir(track.track_id)
        tdir.mkdir(parents=True, exist_ok=True)
        self.message_bus_dir(track.track_id).mkdir(parents=True, exist_ok=True)
        self.events_dir(track.track_id).mkdir(parents=True, exist_ok=True)

        # spec / plan placeholders
        atomic_write_text(tdir / "spec.md", SPEC_TEMPLATE.format(
            goal=track.goal, track_id=track.track_id, created_at=track.created_at))
        atomic_write_text(tdir / "plan.md", PLAN_TEMPLATE.format(
            goal=track.goal, track_id=track.track_id, created_at=track.created_at))

        # metadata projection
        self.write_track(track)

        # empty projections so readers find well-formed files immediately
        if not self.worker_status_path(track.track_id).exists():
            atomic_write_json(self.worker_status_path(track.track_id),
                              {"track_id": track.track_id, "workers": {}, "updated_at": track.created_at})
        if not self.locks_path(track.track_id).exists():
            atomic_write_json(self.locks_path(track.track_id),
                              {"track_id": track.track_id, "locks": {}, "updated_at": track.created_at})
        if not self.queue_path(track.track_id).exists():
            self.queue_path(track.track_id).touch()

        self.append_event({"event": "track_created", "track_id": track.track_id,
                           "goal": track.goal, "at": track.created_at})
        return track

    def write_track(self, track: Track) -> None:
        track.updated_at = utc_now_iso()
        track.validate()
        atomic_write_json(self.track_metadata_path(track.track_id), track.to_dict())

    def read_track(self, track_id: str) -> Optional[Track]:
        data = read_json(self.track_metadata_path(track_id))
        if data is None:
            return None
        return Track.from_dict(data)

    def write_track_record(self, record: TrackRecord) -> None:
        """Persist the Phase 2 aggregate (track + plan + tasks + approvals)."""
        record.track.updated_at = utc_now_iso()
        record.validate()
        atomic_write_json(self.track_metadata_path(record.track.track_id), record.to_dict())

    def read_track_record(self, track_id: str) -> Optional[TrackRecord]:
        data = read_json(self.track_metadata_path(track_id))
        if data is None:
            return None
        return TrackRecord.from_dict(data)

    def list_track_ids(self) -> List[str]:
        if not self.tracks_dir.exists():
            return []
        return sorted(p.name for p in self.tracks_dir.iterdir()
                      if p.is_dir() and (p / "metadata.json").exists())

    def list_tracks(self) -> List[Track]:
        tracks = []
        for tid in self.list_track_ids():
            t = self.read_track(tid)
            if t is not None:
                tracks.append(t)
        return tracks

    def set_track_state(self, track_id: str, state: TrackState) -> Track:
        track = self.read_track(track_id)
        if track is None:
            raise KeyError(f"unknown track: {track_id}")
        track.state = state
        self.write_track(track)
        return track

    # -- tasks (Phase 4) ---------------------------------------------------- #
    def tasks_dir(self, track_id: str) -> Path:
        return self.track_dir(track_id) / "tasks"

    def task_dir(self, track_id: str, task_id: str) -> Path:
        return self.tasks_dir(track_id) / task_id

    def task_artifact_path(self, track_id: str, task_id: str) -> Path:
        return self.task_dir(track_id, task_id) / "task.md"

    def task_status_path(self, track_id: str, task_id: str) -> Path:
        return self.task_dir(track_id, task_id) / "status.json"

    def task_route_path(self, track_id: str, task_id: str) -> Path:
        return self.task_dir(track_id, task_id) / "route.json"

    def task_result_path(self, track_id: str, task_id: str) -> Path:
        return self.task_dir(track_id, task_id) / "result.md"

    def write_dispatch_record(self, record: DispatchRecord) -> None:
        record.updated_at = utc_now_iso()
        record.validate()
        self.task_dir(record.track_id, record.task_id).mkdir(parents=True, exist_ok=True)
        atomic_write_json(self.task_status_path(record.track_id, record.task_id), record.to_dict())

    def read_dispatch_record(self, track_id: str, task_id: str) -> Optional[DispatchRecord]:
        data = read_json(self.task_status_path(track_id, task_id))
        if data is None:
            return None
        return DispatchRecord.from_dict(data)

    def write_route_decision(self, decision: RouteDecision) -> None:
        decision.validate()
        self.task_dir(decision.track_id, decision.task_id).mkdir(parents=True, exist_ok=True)
        atomic_write_json(self.task_route_path(decision.track_id, decision.task_id), decision.to_dict())

    def read_route_decision(self, track_id: str, task_id: str) -> Optional[RouteDecision]:
        data = read_json(self.task_route_path(track_id, task_id))
        if data is None:
            return None
        return RouteDecision.from_dict(data)

    def list_dispatch_records(self, track_id: str) -> List[DispatchRecord]:
        """Every task that has a dispatch projection (status.json) for this track."""
        tdir = self.tasks_dir(track_id)
        if not tdir.exists():
            return []
        out: List[DispatchRecord] = []
        for status_file in sorted(tdir.glob("*/status.json")):
            data = read_json(status_file)
            if data is not None:
                out.append(DispatchRecord.from_dict(data))
        return out

    # -- verification (Phase 5) -------------------------------------------- #
    def task_verification_path(self, track_id: str, task_id: str) -> Path:
        return self.task_dir(track_id, task_id) / "verification.json"

    def write_verification(self, gate: VerificationGate) -> None:
        gate.validate()
        self.task_dir(gate.track_id, gate.task_id).mkdir(parents=True, exist_ok=True)
        atomic_write_json(self.task_verification_path(gate.track_id, gate.task_id), gate.to_dict())

    def read_verification(self, track_id: str, task_id: str) -> Optional[VerificationGate]:
        data = read_json(self.task_verification_path(track_id, task_id))
        if data is None:
            return None
        return VerificationGate.from_dict(data)

    # track-level Phase 5 artifacts
    def summary_path(self, track_id: str) -> Path:
        return self.track_dir(track_id) / "summary.md"

    def summary_json_path(self, track_id: str) -> Path:
        return self.track_dir(track_id) / "summary.json"

    def reconciliation_path(self, track_id: str) -> Path:
        return self.track_dir(track_id) / "reconciliation.json"

    def reconciliation_md_path(self, track_id: str) -> Path:
        return self.track_dir(track_id) / "reconciliation.md"

    # operator-surface memos (Phase 6)
    def operator_dir(self, track_id: str) -> Path:
        return self.track_dir(track_id) / "operator"

    def operator_heartbeat_path(self, track_id: str) -> Path:
        return self.operator_dir(track_id) / "heartbeat.json"

    # -- lanes (Phase 3) ---------------------------------------------------- #
    def write_lane_record(self, path: Path, record: LaneRecord) -> None:
        record.updated_at = utc_now_iso()
        record.validate()
        atomic_write_json(Path(path), record.to_dict())

    def read_lane_record_path(self, path: Path) -> Optional[LaneRecord]:
        data = read_json(Path(path))
        if data is None:
            return None
        return LaneRecord.from_dict(data)

    def list_lane_records(self) -> List[LaneRecord]:
        if not self.lanes_dir.exists():
            return []
        out: List[LaneRecord] = []
        for p in sorted(self.lanes_dir.glob("*.json")):
            rec = self.read_lane_record_path(p)
            if rec is not None:
                out.append(rec)
        return out

    # -- global event log --------------------------------------------------- #
    def append_event(self, record: Dict[str, Any]) -> None:
        record = {"at": utc_now_iso(), **record}
        append_jsonl(self.events_path, record)
