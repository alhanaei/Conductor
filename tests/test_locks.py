"""File lock semantics, including genuinely concurrent acquisition across processes."""

import multiprocessing as mp
from pathlib import Path

import pytest

from conductor.locks import LockConflict, LockError, LockManager
from conductor.store import ConductorStore


@pytest.fixture()
def track(tmp_path):
    store = ConductorStore.resolve(root=tmp_path, create=True)
    t = store.create_track("goal")
    return store, t.track_id


def test_acquire_then_conflict(track):
    store, track_id = track
    locks = LockManager(store, track_id)
    locks.acquire("src/app.py", "w1")
    with pytest.raises(LockConflict):
        locks.acquire("src/app.py", "w2")


def test_same_worker_reacquire_is_idempotent(track):
    store, track_id = track
    locks = LockManager(store, track_id)
    locks.acquire("src/app.py", "w1")
    # No conflict for the same holder; refreshes the lock.
    again = locks.acquire("src/app.py", "w1")
    assert again.worker_id == "w1"


def test_release_frees_lock(track):
    store, track_id = track
    locks = LockManager(store, track_id)
    locks.acquire("src/app.py", "w1")
    assert locks.release("src/app.py", "w1") is True
    # Now a different worker can take it.
    locks.acquire("src/app.py", "w2")
    assert locks.is_locked("src/app.py") == "w2"


def test_release_unheld_returns_false(track):
    store, track_id = track
    locks = LockManager(store, track_id)
    assert locks.release("nope.py", "w1") is False


def test_release_by_other_worker_conflicts(track):
    store, track_id = track
    locks = LockManager(store, track_id)
    locks.acquire("a.py", "w1")
    with pytest.raises(LockConflict):
        locks.release("a.py", "w2")


def test_acquire_requires_args(track):
    store, track_id = track
    locks = LockManager(store, track_id)
    with pytest.raises(LockError):
        locks.acquire("", "w1")
    with pytest.raises(LockError):
        locks.acquire("a.py", "")


def test_list_locks(track):
    store, track_id = track
    locks = LockManager(store, track_id)
    locks.acquire("b.py", "w1")
    locks.acquire("a.py", "w2")
    listed = locks.list_locks()
    assert [fl.path for fl in listed] == ["a.py", "b.py"]  # sorted


# --------------------------------------------------------------------------- #
# Concurrency: many processes race for the SAME file lock. Exactly one wins.
# --------------------------------------------------------------------------- #
def _acquire_worker(root_str: str, track_id: str, file_path: str, worker_id: str, q):
    """Run in a child process: attempt one acquisition, report outcome."""
    try:
        store = ConductorStore.resolve(root=Path(root_str), create=False)
        locks = LockManager(store, track_id)
        locks.acquire(file_path, worker_id)
        q.put(("ok", worker_id))
    except LockConflict:
        q.put(("conflict", worker_id))
    except Exception as exc:  # surface unexpected failures to the assertion
        q.put(("error", f"{worker_id}:{exc!r}"))


def test_concurrent_acquire_one_winner(tmp_path):
    store = ConductorStore.resolve(root=tmp_path, create=True)
    track_id = store.create_track("goal").track_id

    ctx = mp.get_context("spawn")  # spawn => independent interpreters, real concurrency
    q = ctx.Queue()
    n = 8
    procs = [
        ctx.Process(target=_acquire_worker,
                    args=(str(store.root), track_id, "hot/file.py", f"w{i}", q))
        for i in range(n)
    ]
    for p in procs:
        p.start()
    for p in procs:
        p.join(timeout=30)

    results = [q.get() for _ in range(n)]
    outcomes = [r[0] for r in results]
    assert "error" not in outcomes, results
    assert outcomes.count("ok") == 1, results
    assert outcomes.count("conflict") == n - 1, results

    # Durable projection agrees: exactly one holder recorded.
    holder = LockManager(store, track_id).is_locked("hot/file.py")
    winner = [r[1] for r in results if r[0] == "ok"][0]
    assert holder == winner
