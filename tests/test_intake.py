"""Intake orchestration + TrackRecord persistence and restart behavior."""

import pytest

from conductor.intake import PlanError, approve_plan, create_planned_track, review_plan
from conductor.models import (
    ApprovalState,
    PlanStatus,
    TrackRecord,
    TrackState,
)
from conductor.store import ConductorStore


@pytest.fixture()
def store(tmp_path):
    return ConductorStore.resolve(root=tmp_path, create=True)


def test_create_planned_track_writes_artifacts(store):
    record = create_planned_track(store, "Build a small dashboard")
    tid = record.track.track_id
    tdir = store.track_dir(tid)

    assert (tdir / "spec.md").exists()
    assert (tdir / "plan.md").exists()
    assert (tdir / "metadata.json").exists()
    assert record.plan_status is PlanStatus.PENDING_REVIEW
    assert record.track.state is TrackState.PLAN_REVIEW
    assert len(record.tasks) == 5
    assert len(record.approvals) == 1
    assert record.approvals[0].state is ApprovalState.PENDING

    spec = (tdir / "spec.md").read_text()
    assert "Build a small dashboard" in spec


def test_create_rejects_empty_goal(store):
    with pytest.raises(PlanError):
        create_planned_track(store, "   ")


def test_metadata_round_trips_as_track_record(store):
    record = create_planned_track(store, "goal x")
    reloaded = store.read_track_record(record.track.track_id)
    assert reloaded is not None
    assert reloaded.track.goal == "goal x"
    assert len(reloaded.tasks) == 5
    assert reloaded.plan_status is PlanStatus.PENDING_REVIEW


def test_phase1_read_track_still_works(store):
    """Enriched metadata.json must remain readable by the Phase 1 Track loader."""
    record = create_planned_track(store, "goal y")
    track = store.read_track(record.track.track_id)  # Phase 1 path
    assert track is not None
    assert track.goal == "goal y"


def test_review_reports_pending_then_approved(store):
    tid = create_planned_track(store, "goal").track.track_id

    review = review_plan(store, tid)
    assert review["approval_pending"] is True
    assert review["approved"] is False
    assert review["task_count"] == 5

    approve_plan(store, tid)
    review2 = review_plan(store, tid)
    assert review2["approved"] is True
    assert review2["approval_pending"] is False


def test_approve_is_idempotent(store):
    tid = create_planned_track(store, "goal").track.track_id
    first = approve_plan(store, tid)
    assert first["already_approved"] is False
    second = approve_plan(store, tid)
    assert second["already_approved"] is True
    assert second["plan_status"] == "approved"


def test_approve_unknown_track_raises(store):
    with pytest.raises(PlanError):
        approve_plan(store, "track_does_not_exist")


def test_approval_persists_across_restart(store, tmp_path):
    tid = create_planned_track(store, "persistent goal").track.track_id
    approve_plan(store, tid)

    # Fresh store object = simulated process restart; state comes from disk.
    reloaded = ConductorStore.resolve(root=tmp_path, create=False)
    rec = reloaded.read_track_record(tid)
    assert rec.is_plan_approved()
    assert rec.track.state is TrackState.APPROVED
    appr = rec.plan_approval()
    assert appr.state is ApprovalState.APPROVED
    assert appr.decided_at is not None


def test_track_record_validation_round_trip():
    record = TrackRecord(track=__import__("conductor.models", fromlist=["Track"]).Track(goal="g"))
    restored = TrackRecord.from_dict(record.to_dict())
    assert restored.track.goal == "g"
    assert restored.plan_status is PlanStatus.NONE
