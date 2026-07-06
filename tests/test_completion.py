"""Phase 5: verification gate, fix-loop, merge approval, close, reconciliation."""

import pytest

from conductor.completion import CompletionEngine, CompletionError
from conductor.dispatch import Dispatcher
from conductor.intake import approve_plan, create_planned_track
from conductor.lanes import LaneAdapter
from conductor.models import TaskState, TrackState, VerificationStatus
from conductor.store import ConductorStore


class FakeTmux:
    def __init__(self, capture_ok=False, transcript=""):
        self.capture_ok = capture_ok
        self.transcript = transcript

    def available(self):
        return True

    def capture(self, target, lines=200):
        return (self.capture_ok, self.transcript if self.capture_ok else "")

    def send_text(self, target, text):
        return True

    def send_enter(self, target):
        return True

    def ensure(self, session, window):
        return True


class FakeGit:
    def available(self):
        return True

    def is_repo(self, path):
        return False

    def add_worktree(self, repo, worktree_path, branch):
        return True


@pytest.fixture()
def store(tmp_path):
    return ConductorStore.resolve(root=tmp_path, create=True)


def _dispatched(store):
    rec = create_planned_track(store, "Build a small dashboard")
    approve_plan(store, rec.track.track_id)
    disp = Dispatcher(store, lane_adapter=LaneAdapter(store, tmux=FakeTmux()),
                      git=FakeGit(), default_session="proj")
    res = disp.dispatch(rec.track.track_id)
    return rec.track.track_id, res["dispatched"][0]["task_id"]


def _write_result(store, track_id, task_id, text="TASK_COMPLETE\nworker says done\n"):
    store.task_result_path(track_id, task_id).write_text(text, encoding="utf-8")


def _mark_remaining_tasks_complete(store, track_id, except_task_id):
    """Make a fixture track finalizable without exercising every DAG task."""
    record = store.read_track_record(track_id)
    for task in record.tasks:
        if task.task_id != except_task_id and task.state is TaskState.PENDING:
            task.state = TaskState.COMPLETE
    store.write_track_record(record)


# --------------------------------------------------------------------------- #
# Worker claim is not completion
# --------------------------------------------------------------------------- #
def test_worker_result_alone_does_not_complete(store):
    track_id, task_id = _dispatched(store)
    _write_result(store, track_id, task_id)  # worker claim, no verifier proof

    drec = store.read_dispatch_record(track_id, task_id)
    assert drec.task_state is TaskState.DISPATCHED      # NOT complete
    assert drec.verification_status is None             # no verdict yet
    assert drec.ready_for_merge is False

    # And the merge/close gates refuse.
    engine = CompletionEngine(store)
    with pytest.raises(CompletionError):
        engine.approve_merge(track_id)
    with pytest.raises(CompletionError):
        engine.close(track_id)


# --------------------------------------------------------------------------- #
# verify
# --------------------------------------------------------------------------- #
def test_verify_pass_writes_artifacts_and_sets_ready_for_merge(store):
    track_id, task_id = _dispatched(store)
    _write_result(store, track_id, task_id)
    engine = CompletionEngine(store)

    result = engine.verify(track_id)
    assert result["verified_count"] == 1
    assert result["failed_count"] == 0

    gate = store.read_verification(track_id, task_id)
    assert gate is not None
    assert gate.status is VerificationStatus.PASSED
    assert gate.verifier == "conductor"
    assert gate.evidence_level.value == "tool_verified"
    assert any(c["name"] == "definition_of_done_present" and c["passed"] for c in gate.checks)
    assert (store.task_dir(track_id, task_id) / "verification.md").exists()

    drec = store.read_dispatch_record(track_id, task_id)
    assert drec.task_state is TaskState.READY_FOR_MERGE
    assert drec.ready_for_merge is True
    assert drec.verified_at is not None


def test_advance_verified_completes_task_and_releases_successor(store):
    track_id, task_id = _dispatched(store)
    _write_result(store, track_id, task_id)
    engine = CompletionEngine(store)
    engine.verify(track_id)

    result = engine.advance_verified(track_id)

    assert result["advanced"] == [task_id]
    assert result["newly_ready_count"] == 1
    assert store.read_dispatch_record(track_id, task_id).task_state is TaskState.COMPLETE
    record = store.read_track_record(track_id)
    states = {t.task_id: t.state for t in record.tasks}
    assert states[task_id] is TaskState.COMPLETE
    assert states[result["newly_ready"][0]] is TaskState.READY


def test_verify_ready_results_skips_missing_result_artifact(store):
    track_id, task_id = _dispatched(store)
    engine = CompletionEngine(store)

    result = engine.verify_ready_results(track_id)

    assert result["verified_count"] == 0
    assert result["skipped"] == [{"task_id": task_id, "reason": "result_artifact_missing"}]
    assert store.read_dispatch_record(track_id, task_id).task_state is TaskState.DISPATCHED


def test_verify_fail_writes_evidence_and_needs_fix(store):
    track_id, task_id = _dispatched(store)  # no result artifact written
    engine = CompletionEngine(store)
    result = engine.verify(track_id)
    assert result["failed_count"] == 1

    gate = store.read_verification(track_id, task_id)
    assert gate.status is VerificationStatus.FAILED
    assert any(c["name"] == "result_artifact_present" and not c["passed"] for c in gate.checks)

    drec = store.read_dispatch_record(track_id, task_id)
    assert drec.task_state is TaskState.NEEDS_FIX
    assert drec.ready_for_merge is False


def test_verify_persists_across_restart(store, tmp_path):
    track_id, task_id = _dispatched(store)
    _write_result(store, track_id, task_id)
    CompletionEngine(store).verify(track_id)

    reloaded = ConductorStore.resolve(root=tmp_path, create=False)
    drec = reloaded.read_dispatch_record(track_id, task_id)
    assert drec.ready_for_merge is True
    assert reloaded.read_verification(track_id, task_id).status is VerificationStatus.PASSED


# --------------------------------------------------------------------------- #
# fix-loop
# --------------------------------------------------------------------------- #
def test_fix_increments_and_refuses_after_max(store):
    track_id, task_id = _dispatched(store)
    engine = CompletionEngine(store)

    for expected in (1, 2, 3):
        r = engine.fix(track_id, task_id)
        assert r["fix_attempt"] == expected
        assert r["pasted_body"] is False
        from pathlib import Path
        assert Path(r["artifact_ref"]).exists()

    with pytest.raises(CompletionError):
        engine.fix(track_id, task_id)  # 4th refused

    forced = engine.fix(track_id, task_id, force=True)
    assert forced["fix_attempt"] == 4


def test_fix_requires_dispatch(store):
    rec = create_planned_track(store, "g")
    engine = CompletionEngine(store)
    with pytest.raises(CompletionError):
        engine.fix(rec.track.track_id, "task_nope")


# --------------------------------------------------------------------------- #
# merge approval
# --------------------------------------------------------------------------- #
def test_approve_merge_refuses_before_verify(store):
    track_id, task_id = _dispatched(store)
    _write_result(store, track_id, task_id)
    engine = CompletionEngine(store)
    with pytest.raises(CompletionError) as exc:
        engine.approve_merge(track_id)
    assert exc.value.evidence is not None and "unverified" in exc.value.evidence


def test_approve_merge_passes_after_verify_and_is_idempotent(store):
    track_id, task_id = _dispatched(store)
    _write_result(store, track_id, task_id)
    engine = CompletionEngine(store)
    engine.verify(track_id)
    _mark_remaining_tasks_complete(store, track_id, task_id)

    first = engine.approve_merge(track_id)
    assert first["merge_approved"] is True
    assert first["already_approved"] is False
    second = engine.approve_merge(track_id)
    assert second["already_approved"] is True


# --------------------------------------------------------------------------- #
# close
# --------------------------------------------------------------------------- #
def test_close_refuses_before_merge_approval(store):
    track_id, task_id = _dispatched(store)
    _write_result(store, track_id, task_id)
    CompletionEngine(store).verify(track_id)
    with pytest.raises(CompletionError):
        CompletionEngine(store).close(track_id)


def test_close_writes_summary_after_approval(store, tmp_path):
    track_id, task_id = _dispatched(store)
    _write_result(store, track_id, task_id)
    engine = CompletionEngine(store)
    engine.verify(track_id)
    _mark_remaining_tasks_complete(store, track_id, task_id)
    engine.approve_merge(track_id)

    result = engine.close(track_id)
    assert result["closed"] is True
    assert store.summary_path(track_id).exists()
    assert store.summary_json_path(track_id).exists()

    reloaded = ConductorStore.resolve(root=tmp_path, create=False)
    rec = reloaded.read_track_record(track_id)
    assert rec.track.state is TrackState.COMPLETE
    assert reloaded.read_dispatch_record(track_id, task_id).task_state is TaskState.COMPLETE


# --------------------------------------------------------------------------- #
# reconciliation
# --------------------------------------------------------------------------- #
def test_reconcile_detects_worker_result_without_verification(store):
    track_id, task_id = _dispatched(store)
    _write_result(store, track_id, task_id)  # claim present, never verified
    report = CompletionEngine(store).reconcile(track_id)
    assert report["consistent"] is False
    task = next(t for t in report["tasks"] if t["task_id"] == task_id)
    assert "worker_result_without_verification" in task["issues"]
    assert store.reconciliation_path(track_id).exists()


def test_reconcile_detects_missing_definition_of_done(store):
    track_id, task_id = _dispatched(store)
    store.definition_of_done_path(track_id).unlink()

    report = CompletionEngine(store).reconcile(track_id)

    assert "definition_of_done_missing" in report["track_issues"]


def test_reconcile_detects_merge_approval_missing(store):
    track_id, task_id = _dispatched(store)
    _write_result(store, track_id, task_id)
    CompletionEngine(store).verify(track_id)  # all dispatched tasks verified, not merged
    report = CompletionEngine(store).reconcile(track_id)
    assert "merge_approval_missing" in report["track_issues"]


def test_reconcile_consistent_after_full_flow(store):
    track_id, task_id = _dispatched(store)
    _write_result(store, track_id, task_id)
    engine = CompletionEngine(store)
    engine.verify(track_id)
    _mark_remaining_tasks_complete(store, track_id, task_id)
    engine.approve_merge(track_id)
    engine.close(track_id)
    report = engine.reconcile(track_id)
    assert report["consistent"] is True
    assert report["track_issues"] == []
