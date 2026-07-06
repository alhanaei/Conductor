"""OS-level file lock manager: one writer per file, per track.

Two-layer locking (see module-level design note in the codebase):

1. ``.lock_mutex`` guarded by ``fcntl.flock`` — a short critical-section mutex
   held only while we read-modify-write the projection. It serializes
   concurrent acquirers so the check-then-set on ``locks.json`` is atomic.
2. ``locks.json`` — the durable projection mapping ``path -> FileLock``. This is
   the real claim and it survives process exit.

Acquisition is idempotent for the *same* worker (re-acquiring your own lock
succeeds and refreshes it) and conflicts for a *different* worker.
"""

from __future__ import annotations

import errno
import fcntl
import os
import time
from contextlib import contextmanager
from typing import Any, Dict, Iterator, List, Optional

from .models import FileLock, utc_now_iso
from .store import ConductorStore, atomic_write_json, read_json


class LockConflict(RuntimeError):
    """Raised when a file is already locked by a different worker."""

    def __init__(self, path: str, holder: str):
        super().__init__(f"file {path!r} is already locked by worker {holder!r}")
        self.path = path
        self.holder = holder


class LockError(RuntimeError):
    """Raised on lock-management failures (e.g. releasing a non-existent lock)."""


class LockManager:
    def __init__(self, store: ConductorStore, track_id: str):
        self.store = store
        self.track_id = track_id

    # -- mutex -------------------------------------------------------------- #
    @contextmanager
    def _mutex(self, timeout: float = 10.0, poll: float = 0.02) -> Iterator[None]:
        """Hold an exclusive advisory lock on ``.lock_mutex`` for the block.

        Uses non-blocking ``flock`` in a poll loop so a wedged holder can't pin
        us forever — we give up with a :class:`TimeoutError` after ``timeout``.
        """
        mutex_path = self.store.lock_mutex_path(self.track_id)
        mutex_path.parent.mkdir(parents=True, exist_ok=True)
        fd = os.open(str(mutex_path), os.O_CREAT | os.O_RDWR, 0o644)
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
                            f"could not acquire lock mutex for track {self.track_id!r} "
                            f"within {timeout}s"
                        ) from exc
                    time.sleep(poll)
            yield
        finally:
            if acquired:
                fcntl.flock(fd, fcntl.LOCK_UN)
            os.close(fd)

    # -- projection helpers ------------------------------------------------- #
    def _read_locks(self) -> Dict[str, Any]:
        return read_json(
            self.store.locks_path(self.track_id),
            {"track_id": self.track_id, "locks": {}, "updated_at": utc_now_iso()},
        )

    def _write_locks(self, doc: Dict[str, Any]) -> None:
        doc["track_id"] = self.track_id
        doc["updated_at"] = utc_now_iso()
        atomic_write_json(self.store.locks_path(self.track_id), doc)

    # -- public API --------------------------------------------------------- #
    def acquire(self, path: str, worker_id: str, task_id: Optional[str] = None) -> FileLock:
        """Acquire an exclusive lock on ``path`` for ``worker_id``.

        Raises :class:`LockConflict` if another worker holds it.
        """
        if not path:
            raise LockError("lock path is required")
        if not worker_id:
            raise LockError("worker_id is required")
        with self._mutex():
            doc = self._read_locks()
            locks = doc.setdefault("locks", {})
            existing = locks.get(path)
            if existing is not None and existing.get("worker_id") != worker_id:
                raise LockConflict(path, existing.get("worker_id", "?"))
            lock = FileLock(
                path=path,
                worker_id=worker_id,
                track_id=self.track_id,
                task_id=task_id,
                acquired_at=utc_now_iso(),
            )
            lock.validate()
            locks[path] = lock.to_dict()
            self._write_locks(doc)
            return lock

    def release(self, path: str, worker_id: str) -> bool:
        """Release ``worker_id``'s lock on ``path``.

        Returns ``True`` if a lock was removed. Raises :class:`LockConflict` if
        the lock is held by a *different* worker (you can't steal a release).
        """
        with self._mutex():
            doc = self._read_locks()
            locks = doc.setdefault("locks", {})
            existing = locks.get(path)
            if existing is None:
                return False
            if existing.get("worker_id") != worker_id:
                raise LockConflict(path, existing.get("worker_id", "?"))
            del locks[path]
            self._write_locks(doc)
            return True

    def list_locks(self) -> List[FileLock]:
        doc = self._read_locks()
        out = []
        for entry in doc.get("locks", {}).values():
            try:
                out.append(FileLock.from_dict(entry))
            except Exception:
                continue
        return sorted(out, key=lambda fl: fl.path)

    def is_locked(self, path: str) -> Optional[str]:
        """Return the holding worker_id if ``path`` is locked, else ``None``."""
        doc = self._read_locks()
        entry = doc.get("locks", {}).get(path)
        return entry.get("worker_id") if entry else None
