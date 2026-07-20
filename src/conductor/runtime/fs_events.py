"""Filesystem notification source for Conductor artifact changes."""

from __future__ import annotations

import ctypes
import errno
import hashlib
import os
import select
import struct
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Protocol, Tuple

from ..store import ConductorStore
from .events import RuntimeEvent, RuntimeEventKind


@dataclass(frozen=True)
class WatcherEvent:
    path: Path
    kind: str
    at: str


class Watcher(Protocol):
    def add(self, path: Path) -> None:
        ...

    def read(self, timeout: float) -> List[WatcherEvent]:
        ...

    def close(self) -> None:
        ...


class FakeWatcher:
    """Deterministic watcher used by unit tests and disposable proofs."""

    def __init__(self, events: Optional[List[WatcherEvent]] = None):
        self.events = list(events or [])
        self.added: List[Path] = []
        self.close_calls = 0

    def add(self, path: Path) -> None:
        self.added.append(Path(path))

    def push(self, event: WatcherEvent) -> None:
        self.events.append(event)

    def read(self, timeout: float) -> List[WatcherEvent]:
        events = list(self.events)
        self.events.clear()
        return events

    def close(self) -> None:
        self.close_calls += 1


class InotifyWatcher:
    """Small stdlib-only Linux inotify adapter."""

    _EVENT = struct.Struct("iIII")
    _IN_MODIFY = 0x00000002
    _IN_CLOSE_WRITE = 0x00000008
    _IN_MOVED_TO = 0x00000080
    _IN_CREATE = 0x00000100
    _IN_Q_OVERFLOW = 0x00004000
    _WATCH_MASK = _IN_MODIFY | _IN_CLOSE_WRITE | _IN_MOVED_TO | _IN_CREATE

    def __init__(self):
        self._libc = ctypes.CDLL(None, use_errno=True)
        init = getattr(self._libc, "inotify_init1", None)
        add_watch = getattr(self._libc, "inotify_add_watch", None)
        if init is None or add_watch is None:
            raise OSError("libc inotify functions are unavailable")
        init.argtypes = [ctypes.c_int]
        init.restype = ctypes.c_int
        add_watch.argtypes = [ctypes.c_int, ctypes.c_char_p, ctypes.c_uint32]
        add_watch.restype = ctypes.c_int
        flags = os.O_NONBLOCK | getattr(os, "O_CLOEXEC", 0)
        self._fd = init(flags)
        if self._fd < 0:
            code = ctypes.get_errno()
            raise OSError(code, os.strerror(code))
        self._add_watch = add_watch
        self._paths: Dict[int, Path] = {}
        self._watched: Dict[Path, int] = {}
        self._closed = False

    @classmethod
    def probe(cls) -> Tuple[bool, str]:
        try:
            watcher = cls()
        except OSError as exc:
            return False, f"inotify unavailable: {exc}"
        watcher.close()
        return True, "inotify available"

    def add(self, path: Path) -> None:
        directory = Path(path).resolve()
        if directory in self._watched:
            return
        if not directory.is_dir():
            raise NotADirectoryError(str(directory))
        wd = self._add_watch(
            self._fd,
            os.fsencode(directory),
            self._WATCH_MASK,
        )
        if wd < 0:
            code = ctypes.get_errno()
            raise OSError(code, os.strerror(code), str(directory))
        self._paths[wd] = directory
        self._watched[directory] = wd

    def read(self, timeout: float) -> List[WatcherEvent]:
        if self._closed:
            return []
        ready, _, _ = select.select([self._fd], [], [], max(0.0, timeout))
        if not ready:
            return []
        try:
            data = os.read(self._fd, 65536)
        except BlockingIOError:
            return []
        events: List[WatcherEvent] = []
        offset = 0
        while offset + self._EVENT.size <= len(data):
            wd, mask, _, name_len = self._EVENT.unpack_from(data, offset)
            offset += self._EVENT.size
            raw_name = data[offset:offset + name_len]
            offset += name_len
            if mask & self._IN_Q_OVERFLOW:
                events.append(WatcherEvent(Path(), "overflow", "inotify"))
                continue
            base = self._paths.get(wd)
            if base is None:
                continue
            name = os.fsdecode(raw_name.split(b"\0", 1)[0])
            path = base / name if name else base
            if mask & (self._IN_CREATE | self._IN_MOVED_TO):
                kind = "created"
            elif mask & (self._IN_MODIFY | self._IN_CLOSE_WRITE):
                kind = "modified"
            else:
                continue
            events.append(WatcherEvent(path, kind, "inotify"))
        return events

    def close(self) -> None:
        if self._closed:
            return
        self._closed = True
        os.close(self._fd)


_RECOGNIZED_TASK_ARTIFACTS = {
    "result.md",
    "status.json",
    "verification.json",
    "verification.md",
    "verdict.json",
}


class ArtifactEventSource:
    """Convert watched Conductor artifact paths into normalized runtime events."""

    def __init__(self, store: ConductorStore, watcher: Watcher):
        self.store = store
        self.watcher = watcher
        self._root = store.root.resolve()
        self._gap: Optional[str] = None
        self._started = False
        self._closed = False

    @property
    def source_id(self) -> str:
        return "fs_artifact"

    def _add_known_directories(self) -> None:
        self.watcher.add(self.store.tracks_dir)
        if not self.store.tracks_dir.exists():
            return
        for track_dir in sorted(self.store.tracks_dir.iterdir()):
            if not track_dir.is_dir():
                continue
            self.watcher.add(track_dir)
            tasks_dir = track_dir / "tasks"
            if tasks_dir.is_dir():
                self.watcher.add(tasks_dir)
                for task_dir in sorted(tasks_dir.iterdir()):
                    if task_dir.is_dir():
                        self.watcher.add(task_dir)
            bus_dir = track_dir / ".message-bus"
            if bus_dir.is_dir():
                for directory, subdirs, _ in os.walk(bus_dir):
                    self.watcher.add(Path(directory))
                    subdirs.sort()

    def start(self) -> None:
        if self._started:
            return
        self._add_known_directories()
        self._started = True

    def _relative(self, path: Path) -> Optional[Path]:
        try:
            return Path(path).resolve().relative_to(self._root)
        except (OSError, ValueError):
            return None

    @staticmethod
    def _content_hash(path: Path) -> str:
        digest = hashlib.sha256()
        try:
            with path.open("rb") as handle:
                for chunk in iter(lambda: handle.read(65536), b""):
                    digest.update(chunk)
        except (FileNotFoundError, IsADirectoryError, PermissionError):
            digest.update(b"missing")
        return digest.hexdigest()

    def _event_for(self, watched: WatcherEvent) -> Optional[RuntimeEvent]:
        relative = self._relative(watched.path)
        if relative is None:
            return None
        parts = relative.parts
        track_id: Optional[str] = None
        task_id: Optional[str] = None
        artifact: Optional[str] = None
        if (
            len(parts) == 5
            and parts[0] == "tracks"
            and parts[2] == "tasks"
            and parts[4] in _RECOGNIZED_TASK_ARTIFACTS
        ):
            track_id, task_id, artifact = parts[1], parts[3], parts[4]
        elif len(parts) >= 4 and parts[0] == "tracks" and parts[2] == ".message-bus":
            track_id, artifact = parts[1], "message_bus"
        else:
            return None
        if watched.kind not in ("created", "modified"):
            return None
        kind = (
            RuntimeEventKind.ARTIFACT_CREATED
            if watched.kind == "created"
            else RuntimeEventKind.ARTIFACT_MODIFIED
        )
        relative_text = relative.as_posix()
        digest = self._content_hash(watched.path)
        return RuntimeEvent(
            source=self.source_id,
            source_key=f"{relative_text}:{digest}",
            kind=kind,
            observed_at=watched.at,
            track_id=track_id,
            task_id=task_id,
            evidence_ref=relative_text,
            payload={"artifact": artifact, "path": relative_text},
        )

    def read_events(self, timeout: float = 1.0) -> List[RuntimeEvent]:
        if not self._started:
            raise RuntimeError("filesystem event source is not started")
        events: List[RuntimeEvent] = []
        for watched in self.watcher.read(timeout):
            if watched.kind == "overflow":
                if self._gap is None:
                    self._gap = "filesystem watcher overflow"
                continue
            path = Path(watched.path)
            if watched.kind == "created" and path.is_dir():
                relative = self._relative(path)
                if relative is not None:
                    self.watcher.add(path)
                continue
            event = self._event_for(watched)
            if event is not None:
                events.append(event)
        return events

    def gap_reason(self) -> Optional[str]:
        return self._gap

    def close(self) -> None:
        if self._closed:
            return
        self._closed = True
        self.watcher.close()
        self._started = False
