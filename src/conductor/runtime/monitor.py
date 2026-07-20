"""Targeted correlation and projection updates for runtime events."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from ..completion import CompletionEngine
from ..lanes import LaneAdapter, LaneError
from ..models import DispatchRecord, TaskState, utc_now_iso
from ..store import ConductorStore
from .events import RuntimeEvent, RuntimeEventKind, RuntimeEventLedger


_ACTIVE_TASK_STATES = {
    TaskState.DISPATCHED,
    TaskState.WORKING,
    TaskState.READY_FOR_REVIEW,
    TaskState.VERIFYING,
    TaskState.BLOCKED,
}
_TERMINAL_TASK_STATES = {
    TaskState.READY_FOR_MERGE,
    TaskState.COMPLETE,
    TaskState.FAILED,
    TaskState.CANCELLED,
}
_PANE_EVENT_KINDS = {
    RuntimeEventKind.PANE_OUTPUT,
    RuntimeEventKind.PANE_LIFECYCLE,
}
_ARTIFACT_EVENT_KINDS = {
    RuntimeEventKind.ARTIFACT_CREATED,
    RuntimeEventKind.ARTIFACT_MODIFIED,
}


def _parse_iso(value: Optional[str]) -> Optional[datetime]:
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed


def _same_path(left: str, right: str) -> bool:
    return Path(left).expanduser().resolve() == Path(right).expanduser().resolve()


class EventMonitor:
    """Consume normalized events and refresh only correlated projections."""

    def __init__(
        self,
        store: ConductorStore,
        *,
        ledger: Optional[RuntimeEventLedger] = None,
        lane_adapter: Optional[LaneAdapter] = None,
        completion_engine: Optional[CompletionEngine] = None,
    ):
        self.store = store
        self.ledger = ledger or RuntimeEventLedger(store)
        self.lane_adapter = lane_adapter or LaneAdapter(store)
        self.completion_engine = completion_engine or CompletionEngine(store)
        self._reconciling = False
        self._source_gaps: Dict[str, str] = {}

    def _dispatches(self) -> List[DispatchRecord]:
        records: List[DispatchRecord] = []
        track_ids = set(self.store.list_track_ids())
        if self.store.tracks_dir.exists():
            track_ids.update(
                path.name for path in self.store.tracks_dir.iterdir() if path.is_dir()
            )
        for track_id in sorted(track_ids):
            records.extend(self.store.list_dispatch_records(track_id))
        return records

    def _known(self, event_id: str) -> bool:
        return any(event.event_id == event_id for event in self.ledger.iter_events())

    def _candidate(self, event: RuntimeEvent) -> Tuple[Optional[DispatchRecord], str]:
        records = self._dispatches()
        if event.task_id:
            task_matches = [record for record in records if record.task_id == event.task_id]
            if event.track_id:
                exact = [record for record in task_matches if record.track_id == event.track_id]
                if len(exact) == 1:
                    return exact[0], ""
                if task_matches:
                    return None, "track/task provenance mismatch"
                return None, "no matching dispatch"
            if len(task_matches) == 1:
                return task_matches[0], ""
            if len(task_matches) > 1:
                return None, "ambiguous task correlation"
            return None, "no matching dispatch"

        if event.lane_target:
            lane_matches = [
                record for record in records if record.lane_target == event.lane_target
            ]
            active = [
                record for record in lane_matches if record.task_state in _ACTIVE_TASK_STATES
            ]
            if len(active) == 1:
                return active[0], ""
            if len(active) > 1:
                return None, "ambiguous active lane correlation"
            if len(lane_matches) == 1:
                return lane_matches[0], ""
            if len(lane_matches) > 1:
                return None, "ambiguous lane correlation"
            return None, "no matching active dispatch"

        return None, "event has no lane or task correlation key"

    def _record_unresolved(
        self,
        event: RuntimeEvent,
        kind: RuntimeEventKind,
        reason: str,
    ) -> Dict[str, Any]:
        if self._known(event.event_id):
            return {"accepted": False, "duplicate": True, "event_id": event.event_id}
        original_kind = event.kind.value
        event.kind = kind
        event.confidence = "unresolved"
        event.payload = {
            **event.payload,
            "original_kind": original_kind,
            "reason": reason,
        }
        path = self.ledger.record_unresolved(event)
        return {
            "accepted": True,
            "event_id": event.event_id,
            "unresolved": kind.value,
            "unresolved_ref": str(path),
        }

    def _correlate(
        self, event: RuntimeEvent
    ) -> Tuple[Optional[DispatchRecord], Optional[Dict[str, Any]]]:
        record, reason = self._candidate(event)
        if record is None:
            return None, self._record_unresolved(
                event, RuntimeEventKind.UNRESOLVED_EVENT, reason
            )

        if event.lane_target and record.lane_target != event.lane_target:
            return None, self._record_unresolved(
                event,
                RuntimeEventKind.UNRESOLVED_EVENT,
                "lane/task provenance mismatch",
            )
        expected_worktree = record.worktree_path or record.workspace
        if (
            event.worktree_path
            and expected_worktree
            and not _same_path(event.worktree_path, expected_worktree)
        ):
            return None, self._record_unresolved(
                event,
                RuntimeEventKind.WORKSPACE_PROVENANCE_MISMATCH,
                "event worktree does not match dispatch worktree",
            )

        was_indirect = event.track_id is None or event.task_id is None
        event.track_id = record.track_id
        event.task_id = record.task_id
        event.worktree_path = expected_worktree
        if was_indirect:
            event.confidence = "correlated"
        return record, None

    @staticmethod
    def _stale(event: RuntimeEvent, record: DispatchRecord) -> bool:
        observed = _parse_iso(event.observed_at)
        updated = _parse_iso(record.updated_at)
        return observed is not None and updated is not None and observed < updated

    def _append_lane_observation(
        self,
        record: DispatchRecord,
        lane_state: str,
        cause_event_id: str,
        *,
        reconciliation: bool = False,
    ) -> RuntimeEvent:
        observation = RuntimeEvent(
            source="monitor",
            source_key=f"lane:{cause_event_id}:{record.lane_target}",
            kind=RuntimeEventKind.PANE_OUTPUT,
            lane_target=record.lane_target,
            track_id=record.track_id,
            task_id=record.task_id,
            worktree_path=record.worktree_path or record.workspace,
            evidence_ref=cause_event_id,
            confidence="correlated",
            payload={
                "cause_event_id": cause_event_id,
                "lane_state": lane_state,
                "reconciliation": reconciliation,
            },
        )
        self.ledger.append(observation)
        return observation

    def process(self, event: RuntimeEvent) -> Dict[str, Any]:
        """Deduplicate one event, then perform only its targeted side effect."""
        if event.kind is RuntimeEventKind.EVENT_STREAM_GAP:
            if not self.ledger.append(event):
                return {
                    "accepted": False,
                    "duplicate": True,
                    "event_id": event.event_id,
                }
            recovery = self.reconcile(
                reason=event.payload.get("reason", "event stream gap"),
                cause_event_id=event.event_id,
            )
            return {"accepted": True, "event_id": event.event_id, **recovery}

        record: Optional[DispatchRecord] = None
        if event.kind in _PANE_EVENT_KINDS or event.task_id:
            record, unresolved = self._correlate(event)
            if unresolved is not None:
                return unresolved

        if record is not None and record.task_state in _TERMINAL_TASK_STATES:
            event.payload = {**event.payload, "ignored_reason": "terminal_task"}
            accepted = self.ledger.append(event)
            if not accepted:
                return {
                    "accepted": False,
                    "duplicate": True,
                    "event_id": event.event_id,
                }
            return {
                "accepted": True,
                "event_id": event.event_id,
                "ignored": "terminal_task",
            }

        if (
            record is not None
            and event.kind in _PANE_EVENT_KINDS
            and self._stale(event, record)
        ):
            event.payload = {**event.payload, "ignored_reason": "stale_event"}
            accepted = self.ledger.append(event)
            if not accepted:
                return {
                    "accepted": False,
                    "duplicate": True,
                    "event_id": event.event_id,
                }
            return {
                "accepted": True,
                "event_id": event.event_id,
                "ignored": "stale_event",
            }

        if not self.ledger.append(event):
            return {"accepted": False, "duplicate": True, "event_id": event.event_id}

        result: Dict[str, Any] = {
            "accepted": True,
            "event_id": event.event_id,
            "track_id": event.track_id,
            "task_id": event.task_id,
        }
        if event.kind is RuntimeEventKind.PANE_OUTPUT and record is not None:
            try:
                status = self.lane_adapter.status(record.lane_target or "")
            except LaneError as exc:
                result["lane_error"] = str(exc)
            else:
                lane_state = str(status.get("state", "unknown"))
                observation = self._append_lane_observation(
                    record, lane_state, event.event_id
                )
                result.update(
                    lane_state=lane_state,
                    observation_event_id=observation.event_id,
                )

        if (
            event.kind in _ARTIFACT_EVENT_KINDS
            and event.payload.get("artifact") == "result.md"
            and event.track_id
            and event.task_id
        ):
            result["verification"] = self.completion_engine.verify_ready_results(
                event.track_id
            )
            result["verification_requested"] = True
        return result

    def reconcile(self, *, reason: str, cause_event_id: str) -> Dict[str, Any]:
        """Perform one non-reentrant lane and result scan after a known gap."""
        if self._reconciling:
            return {"reconciled": False, "reason": "reconciliation_in_progress"}
        self._reconciling = True
        try:
            lanes_checked = 0
            lane_errors: List[Dict[str, str]] = []
            result_tracks = set()
            result_artifacts = 0
            for record in self._dispatches():
                if record.task_state not in _ACTIVE_TASK_STATES:
                    continue
                if record.lane_target:
                    lanes_checked += 1
                    try:
                        status = self.lane_adapter.status(record.lane_target)
                    except LaneError as exc:
                        lane_errors.append(
                            {"lane_target": record.lane_target, "error": str(exc)}
                        )
                    else:
                        self._append_lane_observation(
                            record,
                            str(status.get("state", "unknown")),
                            cause_event_id,
                            reconciliation=True,
                        )
                result_path = self.store.task_result_path(
                    record.track_id, record.task_id
                )
                try:
                    has_result = result_path.is_file() and bool(
                        result_path.read_text(encoding="utf-8").strip()
                    )
                except OSError:
                    has_result = False
                if has_result:
                    result_artifacts += 1
                    result_tracks.add(record.track_id)

            verification = {}
            for track_id in sorted(result_tracks):
                verification[track_id] = self.completion_engine.verify_ready_results(
                    track_id
                )

            summary = RuntimeEvent(
                source="monitor",
                source_key=f"reconcile:{cause_event_id}",
                kind=RuntimeEventKind.RECONCILIATION,
                evidence_ref=cause_event_id,
                payload={
                    "reason": reason,
                    "lanes_checked": lanes_checked,
                    "lane_errors": lane_errors,
                    "result_artifacts": result_artifacts,
                    "verification_tracks": sorted(result_tracks),
                },
            )
            self.ledger.append(summary)
            return {
                "reconciled": True,
                "reconciliation_event_id": summary.event_id,
                "lanes_checked": lanes_checked,
                "result_artifacts": result_artifacts,
                "verification": verification,
            }
        finally:
            self._reconciling = False

    def recover_gap(self, source_id: str, reason: str) -> Dict[str, Any]:
        """Audit a source gap and immediately run its single recovery pass."""
        gap = self.ledger.record_gap(source_id, reason)
        return {
            "gap_event_id": gap.event_id,
            **self.reconcile(reason=reason, cause_event_id=gap.event_id),
        }

    def poll_source(self, source: Any, timeout: float = 1.0) -> List[Dict[str, Any]]:
        """Read one source batch and recover once for each distinct source gap."""
        results = [self.process(event) for event in source.read_events(timeout)]
        reason = source.gap_reason()
        source_id = source.source_id
        if reason and self._source_gaps.get(source_id) != reason:
            self._source_gaps[source_id] = reason
            results.append(self.recover_gap(source_id, reason))
        return results
