"""Phase 5 verification-gated completion.

Worker completion != true completion. This module is the independent evaluator
and the gatekeeper:

* ``verify``        — inspects each dispatched task's *result artifact* and writes
                      a conductor-authored ``verification.json``/``.md`` verdict.
                      A worker's ``TASK_COMPLETE`` marker never advances state by
                      itself; only the verifier's verdict does.
* ``fix``           — bounded fix-loop (default 3 attempts) that writes an
                      artifact-reference follow-up, never a pasted body.
* ``approve_merge`` — separate gate; requires every dispatched task to be
                      verified/ready_for_merge, refuses with evidence otherwise.
* ``close``         — requires merge approval; writes a final operator summary and
                      closes the track.
* ``reconcile``     — deterministic state reconstruction from plan + metadata +
                      message bus + task status + lane/worktree, flagging
                      inconsistencies (missing artifacts, claims without proof).

MVP verification is a deterministic artifact check (result present and non-empty)
plus any safe configured commands; it is intentionally separate from worker claims.
"""

from __future__ import annotations

import functools
from pathlib import Path
from typing import Any, Dict, List, Optional

from .message_bus import MessageBus
from .models import (
    ApprovalKind,
    ApprovalRequest,
    ApprovalState,
    DispatchRecord,
    EvidenceLevel,
    MessageType,
    RecipientType,
    SenderType,
    TaskState,
    TrackState,
    VerificationGate,
    VerificationStatus,
    utc_now_iso,
)
from .store import ConductorStore, atomic_write_text, read_json
from .verify_commands import load_allowlist, run_verification_commands


class CompletionError(RuntimeError):
    """Raised on invalid completion-lifecycle operations. May carry evidence."""

    def __init__(self, message: str, evidence: Optional[Any] = None):
        super().__init__(message)
        self.evidence = evidence


def _with_track_mutex(fn):
    """Serialize a track-scoped read-modify-write operation under the track mutex.

    Prevents lost updates when ``loop --watch`` and an operator command mutate the
    same TrackRecord concurrently. Guarded methods must not call each other
    (flock does not nest across fds in one process).
    """

    @functools.wraps(fn)
    def wrapper(self, track_id: str, *args, **kwargs):
        with self.store.track_mutex(track_id):
            return fn(self, track_id, *args, **kwargs)

    return wrapper


def auto_fix_failed_tasks(engine: CompletionEngine, lane_adapter,
                          track_id: str, verify_results: Dict[str, Any]) -> Dict[str, Any]:
    """Route freshly failed verifications into the bounded fix-loop (loop tick).

    For each task that just failed verification:

    1. **Archive** the failing ``result.md`` to ``result-attempt-N.md``. This is
       what makes the loop convergent: ``verify_ready_results`` skips tasks with
       no result, so the same stale failing result is never re-verified (which
       would otherwise burn one fix attempt per tick). The worker must produce a
       *fresh* result to re-enter verification.
    2. Open a bounded fix via :meth:`CompletionEngine.fix` (writes ``fix-N.md`` +
       FOLLOWUP message; refuses past ``max_fix_attempts``).
    3. Best-effort **deliver** a short artifact-reference instruction to the lane
       (readiness-gated; never pastes bodies; pending if the lane is not ready).
    4. When attempts are exhausted, **escalate**: set a blocker on the dispatch
       record and append a ``fix_attempts_exhausted`` event so the operator
       surface flags it. No further fixes are attempted without ``--force``.

    Called *outside* any track mutex (``fix`` acquires its own).
    """
    from .lanes import LaneError  # local import avoids a module cycle

    store = engine.store
    fixed: List[Dict[str, Any]] = []
    exhausted: List[Dict[str, Any]] = []

    for result in verify_results.get("results", []):
        if result.get("passed"):
            continue
        task_id = result["task_id"]
        drec = store.read_dispatch_record(track_id, task_id)
        if drec is None or drec.task_state is not TaskState.NEEDS_FIX:
            continue

        if drec.fix_attempts >= drec.max_fix_attempts:
            if not (drec.blocker or "").startswith("fix attempts exhausted"):
                drec.blocker = ("fix attempts exhausted "
                                f"({drec.fix_attempts}/{drec.max_fix_attempts}); "
                                "operator intervention required")
                store.write_dispatch_record(drec)
                store.append_event({"event": "fix_attempts_exhausted",
                                    "track_id": track_id, "task_id": task_id,
                                    "attempts": drec.fix_attempts})
            exhausted.append({"task_id": task_id, "attempts": drec.fix_attempts})
            continue

        # 1. Archive the failing result so only a fresh result re-enters verify.
        attempt_n = drec.fix_attempts + 1
        result_path = store.task_result_path(track_id, task_id)
        archive_ref = None
        if result_path.exists():
            archive_path = result_path.with_name(f"result-attempt-{attempt_n}.md")
            result_path.replace(archive_path)
            archive_ref = str(archive_path)

        # 2. Bounded fix (self-guarded by the track mutex).
        fix_result = engine.fix(track_id, task_id)

        # 3. Best-effort lane delivery of a short reference.
        delivered = False
        delivery_note = None
        if lane_adapter is not None and drec.lane_target:
            instruction = (f"Fix required for task {task_id}: read "
                           f"{fix_result['artifact_ref']} and address the failing "
                           f"checks, then write a fresh result to "
                           f"{drec.result_artifact_ref}.")
            try:
                lane_adapter.send_instruction(drec.lane_target, instruction,
                                              kind="task_fix_delivery")
                delivered = True
            except LaneError as exc:
                delivery_note = f"pending: {exc}"

        fixed.append({"task_id": task_id, "fix_attempt": fix_result["fix_attempt"],
                      "archived_result_ref": archive_ref,
                      "fix_artifact_ref": fix_result["artifact_ref"],
                      "delivered": delivered, "delivery_note": delivery_note})

    return {"ok": True, "track_id": track_id, "fixed_count": len(fixed),
            "fixed": fixed, "exhausted_count": len(exhausted), "exhausted": exhausted}


class CompletionEngine:
    def __init__(self, store: ConductorStore):
        self.store = store

    # -- helpers ------------------------------------------------------------ #
    def _require_track(self, track_id: str):
        record = self.store.read_track_record(track_id)
        if record is None:
            raise CompletionError(f"unknown track: {track_id}")
        return record

    def _sync_task_state(self, record, task_id: str, state: TaskState) -> None:
        for t in record.tasks:
            if t.task_id == task_id:
                t.state = state
                return

    # -- verify ------------------------------------------------------------- #
    @_with_track_mutex
    def verify(self, track_id: str) -> Dict[str, Any]:
        record = self._require_track(track_id)
        drecs = self.store.list_dispatch_records(track_id)
        if not drecs:
            return {"ok": True, "track_id": track_id, "verified_count": 0,
                    "failed_count": 0, "results": [], "note": "no dispatched tasks to verify"}

        results: List[Dict[str, Any]] = []
        for drec in drecs:
            if drec.task_state is TaskState.COMPLETE:
                results.append({
                    "task_id": drec.task_id,
                    "passed": True,
                    "status": (drec.verification_status.value
                               if drec.verification_status else VerificationStatus.PASSED.value),
                    "task_state": TaskState.COMPLETE.value,
                    "reason": "task already complete; verification retained",
                    "verification_ref": drec.verification_ref,
                })
                continue
            results.append(self._verify_task(record, drec))

        self.store.write_track_record(record)
        # Track enters verifying once any task has been evaluated.
        if record.track.state not in (TrackState.COMPLETE, TrackState.CANCELLED):
            record.track.state = TrackState.VERIFYING
            self.store.write_track_record(record)

        verified = sum(1 for r in results if r["passed"])
        return {"ok": True, "track_id": track_id, "verified_count": verified,
                "failed_count": len(results) - verified, "results": results}

    @_with_track_mutex
    def verify_ready_results(self, track_id: str) -> Dict[str, Any]:
        """Verify only dispatched tasks that have non-empty result artifacts.

        Long-running loops should not mark a still-working task ``needs_fix`` just
        because the worker has not produced ``result.md`` yet. This method is the
        non-blocking loop variant: it evaluates available worker results and skips
        tasks with no result artifact.
        """
        record = self._require_track(track_id)
        results: List[Dict[str, Any]] = []
        skipped: List[Dict[str, Any]] = []
        for drec in self.store.list_dispatch_records(track_id):
            if drec.task_state is TaskState.COMPLETE:
                skipped.append({"task_id": drec.task_id, "reason": "already_complete"})
                continue
            result_path = self.store.task_result_path(track_id, drec.task_id)
            if not (result_path.exists() and result_path.read_text(encoding="utf-8").strip()):
                skipped.append({"task_id": drec.task_id, "reason": "result_artifact_missing"})
                continue
            results.append(self._verify_task(record, drec))

        if results:
            self.store.write_track_record(record)
            if record.track.state not in (TrackState.COMPLETE, TrackState.CANCELLED):
                record.track.state = TrackState.VERIFYING
                self.store.write_track_record(record)

        verified = sum(1 for r in results if r["passed"])
        return {"ok": True, "track_id": track_id, "verified_count": verified,
                "failed_count": len(results) - verified, "results": results,
                "skipped": skipped}

    @_with_track_mutex
    def advance_verified(self, track_id: str) -> Dict[str, Any]:
        """Advance verified tasks and release dependency successors.

        This is the long-horizon engineering-loop primitive. It lets a verified
        task move from ``ready_for_merge`` to ``complete`` without requiring the
        final track-level merge gate on every DAG edge. The final merge/close
        approval remains separate; this method only advances already tool-verified
        task slices and marks newly unblocked dependent tasks ``ready``.
        """
        record = self._require_track(track_id)
        drecs = self.store.list_dispatch_records(track_id)
        drec_by_task = {d.task_id: d for d in drecs}

        advanced: List[str] = []
        for drec in drecs:
            if (drec.task_state is TaskState.READY_FOR_MERGE
                    and drec.ready_for_merge
                    and drec.verification_status is VerificationStatus.PASSED):
                drec.task_state = TaskState.COMPLETE
                self.store.write_dispatch_record(drec)
                self._sync_task_state(record, drec.task_id, TaskState.COMPLETE)
                advanced.append(drec.task_id)

        complete_ids = {t.task_id for t in record.tasks if t.state is TaskState.COMPLETE}
        for task_id, drec in drec_by_task.items():
            if drec.task_state is TaskState.COMPLETE:
                complete_ids.add(task_id)

        newly_ready: List[str] = []
        for task in record.tasks:
            if task.state is not TaskState.PENDING:
                continue
            if all(dep in complete_ids for dep in task.dependencies):
                task.state = TaskState.READY
                newly_ready.append(task.task_id)

        if advanced or newly_ready:
            if record.track.state not in (TrackState.COMPLETE, TrackState.CANCELLED):
                record.track.state = TrackState.APPROVED
            self.store.write_track_record(record)
            self.store.append_event({"event": "tasks_advanced", "track_id": track_id,
                                     "advanced": advanced, "newly_ready": newly_ready})

        all_complete = bool(record.tasks) and all(t.state is TaskState.COMPLETE for t in record.tasks)
        return {"ok": True, "track_id": track_id, "advanced_count": len(advanced),
                "advanced": advanced, "newly_ready_count": len(newly_ready),
                "newly_ready": newly_ready, "all_tasks_complete": all_complete,
                "final_merge_required": all_complete}

    def _verify_task(self, record, drec: DispatchRecord) -> Dict[str, Any]:
        now = utc_now_iso()
        track_id, task_id = drec.track_id, drec.task_id
        result_path = self.store.task_result_path(track_id, task_id)

        # Deterministic evidence — independent of the worker's claim text.
        has_result = result_path.exists() and result_path.read_text(encoding="utf-8").strip() != ""
        dod_path = self.store.definition_of_done_path(track_id)
        has_dod = dod_path.exists() and dod_path.read_text(encoding="utf-8").strip() != ""
        checks = [
            {
                "name": "result_artifact_present",
                "passed": has_result,
                "detail": str(result_path),
            },
            {
                "name": "definition_of_done_present",
                "passed": has_dod,
                "detail": str(dod_path),
            },
        ]
        # Run configured verification commands (real, allowlisted, no shell).
        # Each command is one deterministic check with exit-code + output evidence.
        command_evidence_ref = None
        if drec.verification_commands:
            config = read_json(self.store.config_path, {}) or {}
            allowlist = load_allowlist(config)
            workspace = Path(drec.workspace) if drec.workspace else self.store.root.parent
            if not workspace.is_dir():
                workspace = self.store.root.parent
            cmd_checks = run_verification_commands(
                drec.verification_commands, workspace, allowlist=allowlist)
            checks.extend(cmd_checks)
            # Persist full command output as durable evidence.
            out_path = self.store.task_dir(track_id, task_id) / "verification-output.txt"
            blocks = []
            for c in cmd_checks:
                verdict = "PASS" if c["passed"] else "FAIL"
                blocks.append(f"$ {c['command']}\n# {verdict} — {c['detail']}\n"
                              f"{c.get('output_tail', '')}\n")
            atomic_write_text(out_path, "\n".join(blocks))
            command_evidence_ref = str(out_path)

        passed = all(c["passed"] for c in checks)
        status = VerificationStatus.PASSED if passed else VerificationStatus.FAILED
        failed_names = [c["name"] for c in checks if not c["passed"]]
        reason = ("all verification checks passed"
                  + (f" including {len(drec.verification_commands)} command(s)"
                     if drec.verification_commands else "")
                  + "; conductor-verified"
                  if passed else
                  f"verification failed: {', '.join(failed_names)}")

        evidence_refs = [str(result_path)] if has_result else []
        if command_evidence_ref:
            evidence_refs.append(command_evidence_ref)
        gate = VerificationGate(
            track_id=track_id, task_id=task_id, name="phase5_artifact_check",
            commands=list(drec.verification_commands), status=status,
            evidence_level=EvidenceLevel.TOOL_VERIFIED,
            evidence_refs=evidence_refs,
            checks=checks, verifier="conductor", reason=reason,
        )
        self.store.write_verification(gate)
        self._write_verification_md(track_id, task_id, gate)

        # Advance state on the *verdict*, never on the worker claim.
        if passed:
            task_state = TaskState.READY_FOR_MERGE
            drec.ready_for_merge = True
        else:
            task_state = TaskState.NEEDS_FIX
            drec.ready_for_merge = False
        drec.verification_status = status
        drec.verification_ref = str(self.store.task_verification_path(track_id, task_id))
        drec.verifier = "conductor"
        drec.verified_at = now
        drec.task_state = task_state
        self.store.write_dispatch_record(drec)
        self._sync_task_state(record, task_id, task_state)

        self.store.append_event({"event": "task_verified", "track_id": track_id,
                                 "task_id": task_id, "status": status.value, "passed": passed})
        return {"task_id": task_id, "passed": passed, "status": status.value,
                "task_state": task_state.value, "reason": reason,
                "verification_ref": drec.verification_ref}

    def _write_verification_md(self, track_id: str, task_id: str, gate: VerificationGate) -> None:
        lines = [
            f"# Verification — {task_id}",
            "",
            f"- verifier: {gate.verifier}",
            f"- status: {gate.status.value}",
            f"- evidence_level: {gate.evidence_level.value}",
            f"- updated_at: {gate.updated_at}",
            f"- reason: {gate.reason}",
            "",
            "## Checks",
            "",
        ]
        for c in gate.checks:
            lines.append(f"- [{'pass' if c['passed'] else 'FAIL'}] {c['name']}: {c['detail']}")
        lines.append("")
        atomic_write_text(self.store.task_dir(track_id, task_id) / "verification.md",
                          "\n".join(lines))

    # -- fix ---------------------------------------------------------------- #
    @_with_track_mutex
    def fix(self, track_id: str, task_id: str, body_file: Optional[str] = None,
            force: bool = False) -> Dict[str, Any]:
        drec = self.store.read_dispatch_record(track_id, task_id)
        if drec is None:
            raise CompletionError(f"task {task_id} in track {track_id} has not been dispatched")
        if drec.fix_attempts >= drec.max_fix_attempts and not force:
            raise CompletionError(
                f"max fix attempts ({drec.max_fix_attempts}) reached for task {task_id}; "
                f"use --force to override",
                evidence={"fix_attempts": drec.fix_attempts, "max": drec.max_fix_attempts},
            )

        now = utc_now_iso()
        drec.fix_attempts += 1
        n = drec.fix_attempts

        fixes_dir = self.store.task_dir(track_id, task_id) / "fixes"
        fixes_dir.mkdir(parents=True, exist_ok=True)
        artifact = fixes_dir / f"fix-{n}.md"
        if body_file:
            from pathlib import Path
            body = Path(body_file).read_text(encoding="utf-8")
        else:
            verification_md = self.store.task_dir(track_id, task_id) / "verification.md"
            body = (f"# Fix request #{n} — {task_id}\n\n"
                    f"Verification did not pass. Review {verification_md} and the result "
                    f"artifact, address the failing checks, then re-run verification.\n")
        atomic_write_text(artifact, body)  # stored as artifact, never pasted whole

        bus = MessageBus(self.store, track_id)
        msg = bus.send_simple(
            type=MessageType.FOLLOWUP, sender_type=SenderType.CONDUCTOR, sender_id="conductor",
            recipient_type=RecipientType.TASK, recipient_id=task_id, task_id=task_id,
            summary=f"fix request #{n} for {task_id}", body_ref=str(artifact),
        )
        self.store.append_event({"event": "task_fix", "track_id": track_id, "task_id": task_id,
                                 "attempt": n, "artifact": str(artifact)})

        drec.last_fix_at = now
        drec.heartbeat_at = now
        drec.task_state = TaskState.NEEDS_FIX
        drec.ready_for_merge = False
        self.store.write_dispatch_record(drec)
        record = self._require_track(track_id)
        self._sync_task_state(record, task_id, TaskState.NEEDS_FIX)
        self.store.write_track_record(record)

        return {"ok": True, "track_id": track_id, "task_id": task_id, "fix_attempt": n,
                "max_fix_attempts": drec.max_fix_attempts, "artifact_ref": str(artifact),
                "message_id": msg.message_id, "pasted_body": False,
                "remaining_attempts": max(0, drec.max_fix_attempts - n)}

    # -- merge approval ----------------------------------------------------- #
    @_with_track_mutex
    def approve_merge(self, track_id: str, decided_by: str = "operator",
                      rationale: str = "", force: bool = False) -> Dict[str, Any]:
        record = self._require_track(track_id)
        drecs = self.store.list_dispatch_records(track_id)
        if not drecs:
            raise CompletionError(
                f"track {track_id} has no dispatched tasks to merge",
                evidence={"dispatched_tasks": 0},
            )

        unverified = [
            {"task_id": d.task_id, "task_state": d.task_state.value,
             "verification_status": d.verification_status.value if d.verification_status else None}
            for d in drecs
            if not (d.ready_for_merge and d.verification_status is VerificationStatus.PASSED)
        ]
        if unverified and not force:
            raise CompletionError(
                f"cannot approve merge: {len(unverified)} task(s) not verified/ready_for_merge",
                evidence={"unverified": unverified},
            )

        unfinalized_plan_tasks = [
            {"task_id": t.task_id, "task_state": t.state.value}
            for t in record.tasks
            if t.state not in (TaskState.COMPLETE, TaskState.READY_FOR_MERGE)
        ]
        if unfinalized_plan_tasks and not force:
            raise CompletionError(
                "cannot approve final merge: plan still has uncompleted task(s); "
                "run 'conductor advance' or 'conductor loop' to continue the DAG",
                evidence={"unfinalized_tasks": unfinalized_plan_tasks},
            )

        already = record.is_merge_approved()
        appr = record.merge_approval()
        if not already:
            appr = ApprovalRequest(
                track_id=track_id, kind=ApprovalKind.MERGE, state=ApprovalState.APPROVED,
                requested_by=decided_by, decided_by=decided_by, decided_at=utc_now_iso(),
                rationale=rationale or None,
            )
            record.approvals.append(appr)
            self.store.write_track_record(record)
            self.store.append_event({"event": "merge_approved", "track_id": track_id,
                                     "decided_by": decided_by})

        return {"ok": True, "track_id": track_id, "merge_approved": True,
                "already_approved": already, "approval_id": appr.approval_id,
                "decided_by": appr.decided_by, "decided_at": appr.decided_at,
                "verified_task_count": len(drecs)}

    # -- close -------------------------------------------------------------- #
    @_with_track_mutex
    def close(self, track_id: str, force: bool = False) -> Dict[str, Any]:
        record = self._require_track(track_id)
        if not record.is_merge_approved() and not force:
            raise CompletionError(
                f"cannot close track {track_id}: merge approval required first",
                evidence={"merge_approved": False},
            )

        unfinalized_plan_tasks = [
            {"task_id": t.task_id, "task_state": t.state.value}
            for t in record.tasks
            if t.state not in (TaskState.COMPLETE, TaskState.READY_FOR_MERGE)
        ]
        if unfinalized_plan_tasks and not force:
            raise CompletionError(
                f"cannot close track {track_id}: plan still has uncompleted task(s)",
                evidence={"unfinalized_tasks": unfinalized_plan_tasks},
            )

        now = utc_now_iso()
        drecs = self.store.list_dispatch_records(track_id)

        summary = self._build_summary(record, drecs, now)
        from .store import atomic_write_json  # local import to keep top tidy
        atomic_write_json(self.store.summary_json_path(track_id), summary)
        atomic_write_text(self.store.summary_path(track_id), self._render_summary_md(summary))

        # Only now do dispatched tasks become COMPLETE.
        for drec in drecs:
            drec.task_state = TaskState.COMPLETE
            self.store.write_dispatch_record(drec)
            self._sync_task_state(record, drec.task_id, TaskState.COMPLETE)
        record.track.state = TrackState.COMPLETE
        self.store.write_track_record(record)
        self.store.append_event({"event": "track_closed", "track_id": track_id})

        return {"ok": True, "track_id": track_id, "closed": True,
                "track_state": TrackState.COMPLETE.value,
                "summary_ref": str(self.store.summary_path(track_id)),
                "summary_json_ref": str(self.store.summary_json_path(track_id))}

    def _build_summary(self, record, drecs: List[DispatchRecord], now: str) -> Dict[str, Any]:
        appr = record.merge_approval()
        return {
            "track_id": record.track.track_id,
            "goal": record.track.goal,
            "generated_at": now,
            "plan": {
                "plan_status": record.plan_status.value,
                "task_count": len(record.tasks),
                "plan_approved": record.is_plan_approved(),
            },
            "dispatch": [
                {"task_id": d.task_id, "title": d.title, "provider": d.provider,
                 "lane_target": d.lane_target, "dispatch_state": d.dispatch_state.value if d.dispatch_state else None,
                 "worktree_mode": d.worktree_mode.value, "branch": d.branch}
                for d in drecs
            ],
            "verification": [
                {"task_id": d.task_id,
                 "verification_status": d.verification_status.value if d.verification_status else None,
                 "ready_for_merge": d.ready_for_merge, "verifier": d.verifier,
                 "verified_at": d.verified_at, "fix_attempts": d.fix_attempts}
                for d in drecs
            ],
            "merge_approval": {
                "approved": record.is_merge_approved(),
                "approval_id": appr.approval_id if appr else None,
                "decided_by": appr.decided_by if appr else None,
                "decided_at": appr.decided_at if appr else None,
            },
            "close": {"closed_at": now, "track_state": "complete"},
            "evidence_level": "tool_verified",
        }

    def _render_summary_md(self, summary: Dict[str, Any]) -> str:
        lines = [
            f"# Final Summary — {summary['goal']}",
            "",
            f"- track_id: {summary['track_id']}",
            f"- generated_at: {summary['generated_at']}",
            f"- plan_status: {summary['plan']['plan_status']} (approved={summary['plan']['plan_approved']})",
            f"- merge_approved: {summary['merge_approval']['approved']} "
            f"(by {summary['merge_approval']['decided_by']} at {summary['merge_approval']['decided_at']})",
            f"- track_state: {summary['close']['track_state']}",
            "",
            "## Dispatched tasks",
            "",
        ]
        for d in summary["dispatch"]:
            lines.append(f"- {d['task_id']} ({d['title']}) -> {d['lane_target']} "
                         f"[{d['dispatch_state']}] branch={d['branch']}")
        lines += ["", "## Verification", ""]
        for v in summary["verification"]:
            lines.append(f"- {v['task_id']}: {v['verification_status']} "
                         f"(ready_for_merge={v['ready_for_merge']}, fixes={v['fix_attempts']})")
        lines.append("")
        return "\n".join(lines)

    # -- reconcile ---------------------------------------------------------- #
    def reconcile(self, track_id: str) -> Dict[str, Any]:
        record = self._require_track(track_id)
        now = utc_now_iso()
        bus = MessageBus(self.store, track_id)
        message_count = bus.count()

        task_reports: List[Dict[str, Any]] = []
        dod_path = self.store.definition_of_done_path(track_id)
        has_dod = dod_path.exists() and dod_path.read_text(encoding="utf-8").strip() != ""
        quality_gates_path = self.store.quality_gates_path(track_id)
        has_quality_gates = quality_gates_path.exists() and quality_gates_path.read_text(encoding="utf-8").strip() != ""
        for task in record.tasks:
            tid = task.task_id
            has_task_md = self.store.task_artifact_path(track_id, tid).exists()
            has_route = self.store.task_route_path(track_id, tid).exists()
            has_status = self.store.task_status_path(track_id, tid).exists()
            result_path = self.store.task_result_path(track_id, tid)
            has_result = result_path.exists() and result_path.read_text(encoding="utf-8").strip() != ""
            verification = self.store.read_verification(track_id, tid)
            has_verification = verification is not None

            issues: List[str] = []
            if has_status:  # dispatched
                if not has_task_md:
                    issues.append("missing_task_artifact")
                if not has_route:
                    issues.append("missing_route")
                if has_result and not has_verification:
                    issues.append("worker_result_without_verification")
                if has_verification and verification.status is VerificationStatus.FAILED:
                    issues.append("verification_failed")

            task_reports.append({
                "task_id": tid,
                "task_state": task.state.value,
                "dispatched": has_status,
                "has_task_artifact": has_task_md,
                "has_route": has_route,
                "has_status": has_status,
                "has_worker_result": has_result,
                "has_verification": has_verification,
                "verification_status": verification.status.value if verification else None,
                "issues": issues,
            })

        dispatched = [t for t in task_reports if t["dispatched"]]
        track_issues: List[str] = []
        if not has_dod:
            track_issues.append("definition_of_done_missing")
        if not has_quality_gates:
            track_issues.append("quality_gates_missing")
        if dispatched and all(t["verification_status"] == "passed" for t in dispatched) \
                and not record.is_merge_approved():
            track_issues.append("merge_approval_missing")
        if record.is_merge_approved() and record.track.state is not TrackState.COMPLETE:
            track_issues.append("merge_approved_but_not_closed")

        consistent = not track_issues and all(not t["issues"] for t in task_reports)
        report = {
            "track_id": track_id,
            "generated_at": now,
            "goal": record.track.goal,
            "track_state": record.track.state.value,
            "plan_status": record.plan_status.value,
            "plan_approved": record.is_plan_approved(),
            "merge_approved": record.is_merge_approved(),
            "message_count": message_count,
            "dispatched_count": len(dispatched),
            "consistent": consistent,
            "track_issues": track_issues,
            "tasks": task_reports,
        }
        from .store import atomic_write_json
        atomic_write_json(self.store.reconciliation_path(track_id), report)
        atomic_write_text(self.store.reconciliation_md_path(track_id),
                          self._render_reconciliation_md(report))
        return report

    def _render_reconciliation_md(self, report: Dict[str, Any]) -> str:
        lines = [
            f"# Reconciliation — {report['track_id']}",
            "",
            f"- generated_at: {report['generated_at']}",
            f"- track_state: {report['track_state']}",
            f"- plan_approved: {report['plan_approved']}  merge_approved: {report['merge_approved']}",
            f"- consistent: {report['consistent']}",
            f"- track_issues: {', '.join(report['track_issues']) or 'none'}",
            "",
            "## Tasks",
            "",
        ]
        for t in report["tasks"]:
            flag = ", ".join(t["issues"]) or "ok"
            lines.append(f"- {t['task_id']} [{t['task_state']}] dispatched={t['dispatched']} "
                         f"verification={t['verification_status']} -> {flag}")
        lines.append("")
        return "\n".join(lines)
