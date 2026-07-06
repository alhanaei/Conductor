"""State-root resolution, atomic IO, init layout, and reload-after-restart."""


import pytest

from conductor.store import (
    ConductorStore,
    append_jsonl,
    atomic_write_json,
    default_state_root,
    find_state_root,
    read_json,
    read_jsonl,
)


def test_init_creates_layout(tmp_path):
    store = ConductorStore(tmp_path / ".conductor")
    store.init()
    assert store.config_path.exists()
    assert store.tracks_dir.is_dir()
    assert store.lanes_dir.is_dir()
    assert store.events_path.exists()
    config = read_json(store.config_path)
    assert config["schema_version"] == 1


def test_init_is_idempotent(tmp_path):
    store = ConductorStore(tmp_path / ".conductor")
    first = store.init()
    second = store.init()
    assert first["created_at"] == second["created_at"]  # config not rewritten


def test_resolve_uses_root_parent(tmp_path):
    store = ConductorStore.resolve(root=tmp_path, create=True)
    assert store.root == tmp_path / ".conductor"
    assert store.exists()


def test_resolve_missing_raises(tmp_path):
    with pytest.raises(FileNotFoundError):
        ConductorStore.resolve(root=tmp_path, create=False)


def test_find_state_root_walks_up(tmp_path):
    root = tmp_path / ".conductor"
    ConductorStore(root).init()
    nested = tmp_path / "a" / "b" / "c"
    nested.mkdir(parents=True)
    found = find_state_root(nested)
    assert found == root


def test_env_home_override(tmp_path, monkeypatch):
    home = tmp_path / "custom-home"
    ConductorStore(home).init()
    monkeypatch.setenv("CONDUCTOR_HOME", str(home))
    assert find_state_root(tmp_path / "elsewhere") == home
    assert default_state_root() == home


def test_atomic_write_json_replaces(tmp_path):
    path = tmp_path / "x.json"
    atomic_write_json(path, {"a": 1})
    atomic_write_json(path, {"a": 2})
    assert read_json(path) == {"a": 2}
    # no leftover temp files
    leftovers = [p for p in tmp_path.iterdir() if p.name != "x.json"]
    assert leftovers == []


def test_append_and_read_jsonl(tmp_path):
    path = tmp_path / "log.jsonl"
    append_jsonl(path, {"i": 1})
    append_jsonl(path, {"i": 2})
    records = read_jsonl(path)
    assert [r["i"] for r in records] == [1, 2]


def test_read_jsonl_tolerates_corrupt_tail(tmp_path):
    path = tmp_path / "log.jsonl"
    append_jsonl(path, {"i": 1})
    with path.open("a", encoding="utf-8") as fh:
        fh.write("{not valid json\n")
    records = read_jsonl(path)
    assert [r["i"] for r in records] == [1]  # bad line skipped, good one survives


def test_create_track_layout_and_reload(tmp_path):
    store = ConductorStore.resolve(root=tmp_path, create=True)
    track = store.create_track("phase 1 smoke goal")

    tdir = store.track_dir(track.track_id)
    assert (tdir / "spec.md").exists()
    assert (tdir / "plan.md").exists()
    assert (tdir / "metadata.json").exists()
    assert store.queue_path(track.track_id).exists()
    assert store.worker_status_path(track.track_id).exists()
    assert store.locks_path(track.track_id).exists()

    # Simulate a process restart: brand-new store object, no shared memory.
    reloaded = ConductorStore.resolve(root=tmp_path, create=False)
    again = reloaded.read_track(track.track_id)
    assert again is not None
    assert again.goal == "phase 1 smoke goal"
    assert again.track_id == track.track_id
    assert reloaded.list_track_ids() == [track.track_id]


def test_set_track_state_persists(tmp_path):
    from conductor.models import TrackState

    store = ConductorStore.resolve(root=tmp_path, create=True)
    track = store.create_track("goal")
    store.set_track_state(track.track_id, TrackState.APPROVED)
    reloaded = ConductorStore.resolve(root=tmp_path, create=False)
    assert reloaded.read_track(track.track_id).state is TrackState.APPROVED
