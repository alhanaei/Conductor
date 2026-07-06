"""Phase 6 operator surface: chat-safe summaries, notifications, heartbeats,
approval payloads, artifact links, and the Hermes verify-hook.

This is a pure projection layer over the artifacts written by Phases 1-5. It adds
no authoritative state (only a small heartbeat memo for dedupe) and grounds every
claim in an on-disk artifact. There is no Telegram API, no daemon, no network —
just deterministic rendering of state the operator (or Hermes) can act on.

Design: a single ``_track_view`` derives the canonical state fingerprint and the
one most-important ``signal``/``next_action``; the summary/notify/approval/hook
renderers are thin formatters over that view.
"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from .blocked_prompts import active_blocked_prompts
from .models import (
    NotificationSeverity,
    TaskState,
    TrackState,
    VerificationStatus,
)
from .store import ConductorStore, read_json

# Default heartbeat cadence (seconds): 5 minutes.
HEARTBEAT_CADENCE_SECONDS = 300
# Hard cap on rendered chat text so Telegram never receives a massive message.
TELEGRAM_MAX_CHARS = 3500
_GOAL_TRUNC = 80


class OperatorError(RuntimeError):
    """Raised on invalid operator queries (e.g. unknown track)."""


# --------------------------------------------------------------------------- #
# Small pure helpers
# --------------------------------------------------------------------------- #
def _trunc(text: str, limit: int) -> str:
    text = (text or "").replace("\n", " ").strip()
    return text if len(text) <= limit else text[: limit - 1].rstrip() + "…"


def _bound(text: str, limit: int = TELEGRAM_MAX_CHARS) -> str:
    if len(text) <= limit:
        return text
    return text[: limit - len("\n… (truncated)")].rstrip() + "\n… (truncated)"


def _parse_iso(value: Optional[str]) -> Optional[datetime]:
    if not value:
        return None
    try:
        dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


# --------------------------------------------------------------------------- #
# Artifact link collection (deliverable 5)
# --------------------------------------------------------------------------- #
def collect_artifacts(store: ConductorStore, track_id: str, drecs) -> Dict[str, Any]:
    """Collect stable references to *existing* known Conductor artifacts only.

    Never exposes raw logs or anything outside the track's artifact set.
    """
    tdir = store.track_dir(track_id)

    def present(p: Path) -> Optional[str]:
        return str(p) if p.exists() else None

    track_level = {
        "spec": present(tdir / "spec.md"),
        "plan": present(tdir / "plan.md"),
        "metadata": present(store.track_metadata_path(track_id)),
        "summary": present(store.summary_path(track_id)),
        "reconciliation": present(store.reconciliation_md_path(track_id)),
    }
    track_level = {k: v for k, v in track_level.items() if v}

    tasks = []
    for d in drecs:
        tid = d.task_id
        refs = {
            "task": present(store.task_artifact_path(track_id, tid)),
            "result": present(store.task_result_path(track_id, tid)),
            "route": present(store.task_route_path(track_id, tid)),
            "status": present(store.task_status_path(track_id, tid)),
            "verification": present(store.task_dir(track_id, tid) / "verification.md"),
        }
        tasks.append({"task_id": tid, "refs": {k: v for k, v in refs.items() if v}})

    return {"track": track_level, "tasks": tasks}


# --------------------------------------------------------------------------- #
# Canonical track view + signal derivation
# --------------------------------------------------------------------------- #
def _derive_signal(plan_approved: bool, dispatched: int, needs_fix: int,
                   unverified: int, verified: int, merge_approved: bool,
                   closed: bool, blocked: bool, blocked_prompt: bool,
                   ready_tasks: int, pending_tasks: int,
                   ready_for_merge_tasks: int,
                   all_tasks_finalizable: bool) -> Tuple[str, str, str]:
    """Return (signal, severity, next_action). Single most-important state."""
    if closed:
        return "closed", NotificationSeverity.SUCCESS.value, "none — track closed"
    if not plan_approved:
        return "needs_approval", NotificationSeverity.WARNING.value, "approve the plan"
    if dispatched == 0:
        return "needs_dispatch", NotificationSeverity.INFO.value, "dispatch ready tasks"
    if blocked_prompt:
        return "blocked_prompt", NotificationSeverity.ERROR.value, "approve provider prompt in tmux lane"
    if blocked:
        return "blocked", NotificationSeverity.ERROR.value, "resolve blocked task / lane"
    if needs_fix > 0:
        return "needs_fix", NotificationSeverity.WARNING.value, "open a fix for failed task(s)"
    if ready_for_merge_tasks > 0 and not all_tasks_finalizable:
        return "needs_advance", NotificationSeverity.INFO.value, "advance verified task(s) and continue the loop"
    if ready_tasks > 0:
        return "needs_dispatch", NotificationSeverity.INFO.value, "dispatch ready task(s)"
    if unverified > 0:
        return "needs_verification", NotificationSeverity.INFO.value, "run verification when worker result artifacts are ready"
    if pending_tasks > 0:
        return "waiting_on_dependencies", NotificationSeverity.INFO.value, "wait for dependencies or run the engineering loop"
    if not merge_approved:
        return "ready_for_merge", NotificationSeverity.SUCCESS.value, "approve the merge"
    return "ready_to_close", NotificationSeverity.SUCCESS.value, "close the track"


# next-action command per signal (exact CLI the operator/Hermes can run)
def _next_command(signal: str, track_id: str) -> Optional[str]:
    base = "python -m conductor"
    return {
        "needs_approval": f"{base} approve plan --track {track_id} --json",
        "needs_dispatch": f"{base} loop --track {track_id} --watch --json",
        "needs_advance": f"{base} loop --track {track_id} --watch --json",
        "waiting_on_dependencies": f"{base} loop --track {track_id} --watch --json",
        "needs_verification": f"{base} loop --track {track_id} --watch --stop-on-blocked-prompt --json",
        "blocked_prompt": f"{base} lane blocked --track {track_id} --json",
        "needs_fix": f"{base} fix --track {track_id} --task <task_id> --json",
        "blocked": f"{base} task status --track {track_id} --task <task_id> --json",
        "ready_for_merge": f"{base} approve merge --track {track_id} --json",
        "ready_to_close": f"{base} close --track {track_id} --json",
        "closed": None,
    }.get(signal)


def _track_view(store: ConductorStore, track_id: str) -> Dict[str, Any]:
    record = store.read_track_record(track_id)
    if record is None:
        raise OperatorError(f"unknown track: {track_id}")
    drecs = store.list_dispatch_records(track_id)

    dispatched = len(drecs)
    ready_tasks = sum(1 for t in record.tasks if t.state is TaskState.READY)
    pending_tasks = sum(1 for t in record.tasks if t.state is TaskState.PENDING)
    ready_for_merge_tasks = sum(1 for t in record.tasks if t.state is TaskState.READY_FOR_MERGE)
    all_tasks_finalizable = bool(record.tasks) and all(
        t.state in (TaskState.COMPLETE, TaskState.READY_FOR_MERGE)
        for t in record.tasks
    )
    verified = sum(1 for d in drecs
                   if d.verification_status is VerificationStatus.PASSED and d.ready_for_merge)
    needs_fix = sum(1 for d in drecs
                    if d.verification_status is VerificationStatus.FAILED
                    or d.task_state is TaskState.NEEDS_FIX)
    unverified = sum(1 for d in drecs if d.verification_status is None)
    blocked = any(d.task_state is TaskState.BLOCKED for d in drecs)
    blocked_prompts = active_blocked_prompts(store, track_id)

    closed = record.track.state is TrackState.COMPLETE
    plan_approved = record.is_plan_approved()
    merge_approved = record.is_merge_approved()

    signal, severity, next_action = _derive_signal(
        plan_approved, dispatched, needs_fix, unverified, verified,
        merge_approved, closed, blocked, bool(blocked_prompts), ready_tasks, pending_tasks,
        ready_for_merge_tasks, all_tasks_finalizable)
    next_command = _next_command(signal, track_id)

    artifacts = collect_artifacts(store, track_id, drecs)
    # Deterministic fingerprint: changes iff operator-relevant state changes.
    fingerprint = (f"{record.track.state.value}|plan={record.plan_status.value}|"
                   f"disp={dispatched}|ver={verified}|fix={needs_fix}|unv={unverified}|"
                   f"merge={merge_approved}|blocked_prompts={len(blocked_prompts)}|sig={signal}")

    return {
        "track_id": track_id,
        "goal": record.track.goal,
        "track_state": record.track.state.value,
        "plan_status": record.plan_status.value,
        "plan_approved": plan_approved,
        "merge_approved": merge_approved,
        "closed": closed,
        "counts": {
            "tasks": len(record.tasks),
            "ready": ready_tasks,
            "pending": pending_tasks,
            "ready_for_merge_tasks": ready_for_merge_tasks,
            "dispatched": dispatched,
            "verified": verified,
            "needs_fix": needs_fix,
            "unverified": unverified,
        },
        "signal": signal,
        "severity": severity,
        "next_action": next_action,
        "next_command": next_command,
        "blocked_prompts": blocked_prompts,
        "artifacts": artifacts,
        "fingerprint": fingerprint,
        "_drecs": drecs,
        "_record": record,
    }


def _public_view(view: Dict[str, Any]) -> Dict[str, Any]:
    """Strip private (underscore) keys for JSON output."""
    return {k: v for k, v in view.items() if not k.startswith("_")}


# --------------------------------------------------------------------------- #
# Operator surface
# --------------------------------------------------------------------------- #
class OperatorView:
    def __init__(self, store: ConductorStore):
        self.store = store

    # -- summary (deliverable 1) ------------------------------------------- #
    def summary(self, track_id: Optional[str] = None) -> Dict[str, Any]:
        if track_id is not None:
            view = _public_view(_track_view(self.store, track_id))
            return {"ok": True, "scope": "track", **view}
        tracks = []
        for tid in self.store.list_track_ids():
            v = _track_view(self.store, tid)
            tracks.append({
                "track_id": tid, "goal": _trunc(v["goal"], _GOAL_TRUNC),
                "track_state": v["track_state"], "signal": v["signal"],
                "next_action": v["next_action"], "counts": v["counts"],
            })
        return {"ok": True, "scope": "all", "track_count": len(tracks), "tracks": tracks}

    def render_telegram(self, track_id: Optional[str] = None) -> str:
        if track_id is None:
            data = self.summary(None)
            lines = [f"Conductor • {data['track_count']} track(s)"]
            for t in data["tracks"]:
                lines.append(f"- {t['track_id']} [{t['track_state']}] {t['signal']} "
                             f"— {t['goal']}")
                lines.append(f"    next: {t['next_action']}")
            return _bound("\n".join(lines))

        v = _track_view(self.store, track_id)
        c = v["counts"]
        lines = [
            f"Conductor • {_trunc(v['goal'], _GOAL_TRUNC)}",
            f"track: {v['track_id']}",
            f"state: {v['track_state']} | plan: {v['plan_status']} | signal: {v['signal']}",
            f"tasks: {c['tasks']} | dispatched: {c['dispatched']} | "
            f"verified: {c['verified']}"
            + (f" | needs_fix: {c['needs_fix']}" if c["needs_fix"] else "")
            + (f" | unverified: {c['unverified']}" if c["unverified"] else ""),
            f"next: {v['next_action']}",
        ]
        if v["next_command"]:
            lines.append(f"  $ {v['next_command']}")
        track_arts = v["artifacts"]["track"]
        if track_arts:
            lines.append("artifacts:")
            for name, path in track_arts.items():
                lines.append(f"  - {name}: {path}")
        task_count = len(v["artifacts"]["tasks"])
        if task_count:
            lines.append(f"  - task artifact sets: {task_count}")
        return _bound("\n".join(lines))

    # -- artifact links (deliverable 5) ------------------------------------ #
    def artifacts(self, track_id: str) -> Dict[str, Any]:
        v = _track_view(self.store, track_id)
        return {"ok": True, "track_id": track_id, "artifacts": v["artifacts"]}

    # -- notify (deliverable 2) -------------------------------------------- #
    def notify(self, track_id: str) -> Dict[str, Any]:
        v = _track_view(self.store, track_id)
        signal = v["signal"]
        c = v["counts"]
        summary = (f"{v['track_id']} [{v['track_state']}]: {signal} — {v['next_action']} "
                   f"(dispatched={c['dispatched']}, verified={c['verified']})")
        telegram_text = self.render_telegram(track_id)
        dedupe_key = f"{track_id}:{signal}:{v['fingerprint']}"
        # Most relevant task (first needs_fix/unverified) for task_id, if any.
        task_id = None
        for d in v["_drecs"]:
            if d.task_state is TaskState.NEEDS_FIX or d.verification_status is None:
                task_id = d.task_id
                break
        flat_refs = list(v["artifacts"]["track"].values())
        return {
            "ok": True,
            "signal": signal,
            "severity": v["severity"],
            "track_id": track_id,
            "task_id": task_id,
            "summary": summary,
            "next_action": v["next_action"],
            "next_command": v["next_command"],
            "blocked_prompts": v["blocked_prompts"],
            "artifact_refs": flat_refs,
            "telegram_text": telegram_text,
            "dedupe_key": dedupe_key,
        }

    # -- heartbeat (deliverable 3) ----------------------------------------- #
    def heartbeat(self, track_id: str, now: Optional[str] = None,
                  force: bool = False) -> Dict[str, Any]:
        from .models import utc_now_iso
        from .store import atomic_write_json

        v = _track_view(self.store, track_id)
        now_iso = now or utc_now_iso()
        terminal = v["closed"] or v["track_state"] == TrackState.CANCELLED.value

        memo = read_json(self.store.operator_heartbeat_path(track_id), {}) or {}
        last_at = memo.get("last_heartbeat_at")
        last_fingerprint = memo.get("last_fingerprint")

        due = heartbeat_due(last_at, now_iso, HEARTBEAT_CADENCE_SECONDS, terminal, force)
        changed = last_fingerprint != v["fingerprint"]
        body = ("no change" if (not changed and last_fingerprint is not None)
                else f"{v['signal']} — {v['next_action']}")

        payload = {
            "ok": True,
            "track_id": track_id,
            "due": due,
            "now": now_iso,
            "cadence_seconds": HEARTBEAT_CADENCE_SECONDS,
            "terminal": terminal,
            "changed": changed,
            "signal": v["signal"],
            "body": body if due else "not due",
            "last_heartbeat_at": last_at,
        }
        if due:
            self.store.operator_dir(track_id).mkdir(parents=True, exist_ok=True)
            atomic_write_json(self.store.operator_heartbeat_path(track_id), {
                "last_heartbeat_at": now_iso,
                "last_fingerprint": v["fingerprint"],
                "last_signal": v["signal"],
            })
            payload["telegram_text"] = _bound(
                f"Conductor heartbeat • {track_id}\n"
                f"state: {v['track_state']} | signal: {v['signal']}\n"
                f"{body}")
        return payload

    # -- approval payloads (deliverable 4) --------------------------------- #
    def approval(self, track_id: str, kind: str) -> Dict[str, Any]:
        v = _track_view(self.store, track_id)
        if kind == "plan":
            return self._plan_approval(v)
        if kind == "merge":
            return self._merge_approval(v)
        raise OperatorError(f"unknown approval kind {kind!r}; expected 'plan' or 'merge'")

    def _plan_approval(self, v: Dict[str, Any]) -> Dict[str, Any]:
        tid = v["track_id"]
        arts = v["artifacts"]["track"]
        if v["plan_approved"]:
            return {"ok": True, "kind": "plan", "track_id": tid, "needed": False,
                    "status": "approved",
                    "message": "plan already approved; no action needed"}
        return {
            "ok": True, "kind": "plan", "track_id": tid, "needed": True, "ready": True,
            "status": v["plan_status"],
            "command": f"python -m conductor approve plan --track {tid} --json",
            "context": _trunc(v["goal"], 200),
            "risk": "low — plan approval gates dispatch; no work runs before it",
            "artifact_refs": [p for p in (arts.get("spec"), arts.get("plan")) if p],
        }

    def _merge_approval(self, v: Dict[str, Any]) -> Dict[str, Any]:
        tid = v["track_id"]
        if v["merge_approved"]:
            return {"ok": True, "kind": "merge", "track_id": tid, "needed": False,
                    "status": "approved",
                    "message": "merge already approved; no action needed"}

        drecs = v["_drecs"]
        evidence = [
            {"task_id": d.task_id,
             "verification_status": d.verification_status.value if d.verification_status else None,
             "ready_for_merge": d.ready_for_merge}
            for d in drecs
        ]
        unverified = [e for e in evidence if not (e["ready_for_merge"]
                                                  and e["verification_status"] == "passed")]
        unfinalized = [
            {"task_id": t.task_id, "task_state": t.state.value}
            for t in v["_record"].tasks
            if t.state not in (TaskState.COMPLETE, TaskState.READY_FOR_MERGE)
        ]
        if not drecs:
            return {"ok": True, "kind": "merge", "track_id": tid, "needed": True,
                    "ready": False, "reason": "no dispatched tasks to merge",
                    "verification_evidence": evidence}
        if unverified:
            return {
                "ok": True, "kind": "merge", "track_id": tid, "needed": True, "ready": False,
                "reason": f"{len(unverified)} task(s) not verified; run verify first",
                "blocking_command": f"python -m conductor verify --track {tid} --json",
                "command": f"python -m conductor approve merge --track {tid} --json",
                "verification_evidence": evidence,
            }
        if unfinalized:
            return {
                "ok": True, "kind": "merge", "track_id": tid, "needed": True,
                "ready": False,
                "reason": f"{len(unfinalized)} plan task(s) still not complete; continue the loop first",
                "blocking_command": f"python -m conductor loop --track {tid} --watch --stop-on-blocked-prompt --json",
                "command": f"python -m conductor approve merge --track {tid} --json",
                "verification_evidence": evidence,
                "unfinalized_tasks": unfinalized,
            }
        return {
            "ok": True, "kind": "merge", "track_id": tid, "needed": True, "ready": True,
            "command": f"python -m conductor approve merge --track {tid} --json",
            "risk": "medium — gates close; ensure verification evidence is sound",
            "verification_evidence": evidence,
        }

    # -- Hermes verify-hook (deliverable 6) -------------------------------- #
    def verify_hook(self, track_id: str) -> Dict[str, Any]:
        v = _track_view(self.store, track_id)
        tid = track_id
        commands: List[Dict[str, Any]] = []

        def add(cmd, purpose, expected, auto_run=True):
            commands.append({"command": cmd, "purpose": purpose,
                             "expected": expected, "auto_run": auto_run})

        c = v["counts"]
        if v["closed"]:
            add(f"python -m conductor reconcile --track {tid} --json",
                "confirm closed track is internally consistent",
                "consistent=true, track_issues=[]")
            add(f"python -m conductor operator summary --track {tid} --json",
                "read the final summary", "track_state=complete", auto_run=True)
        elif not v["plan_approved"]:
            add(f"python -m conductor operator approval --track {tid} --kind plan --json",
                "surface the plan-approval request", "needed=true", auto_run=True)
        elif c["dispatched"] == 0:
            add(f"python -m conductor loop --track {tid} --watch --stop-on-blocked-prompt --json",
                "run the supervised long-task loop until progress, finalization, or max cycles",
                "progress, closure, or bounded no-op evidence")
        elif v["signal"] == "needs_advance":
            add(f"python -m conductor loop --track {tid} --watch --stop-on-blocked-prompt --json",
                "continue the supervised long-task loop without stopping at the advance gate",
                "verified slices advance and dependent work dispatches when ready")
        elif c["ready"] > 0:
            add(f"python -m conductor loop --track {tid} --watch --stop-on-blocked-prompt --json",
                "continue the long-horizon engineering loop", "progress or no-op with evidence")
        elif c["unverified"] > 0 or c["needs_fix"] > 0:
            add(f"python -m conductor loop --track {tid} --watch --stop-on-blocked-prompt --json",
                "poll for worker results and verify available artifacts without marking active work failed",
                "available results verified; missing results skipped until later poll")
        elif not v["merge_approved"]:
            add(f"python -m conductor approve merge --track {tid} --json",
                "delegated operator action — approve merge after verification gates pass",
                "merge_approved=true", auto_run=True)
        else:
            add(f"python -m conductor close --track {tid} --json",
                "delegated operator action — close the verified and merged track",
                "closed=true", auto_run=True)

        # Always offer reconcile as a non-mutating grounding check.
        if not v["closed"]:
            add(f"python -m conductor reconcile --track {tid} --json",
                "grounding consistency check", "report consistent flag", auto_run=True)

        return {"ok": True, "track_id": tid, "track_state": v["track_state"],
                "signal": v["signal"], "commands": commands}


# --------------------------------------------------------------------------- #
# Pure heartbeat policy (deliverable 3 — testable in isolation)
# --------------------------------------------------------------------------- #
def heartbeat_due(last_heartbeat_at: Optional[str], now: str,
                  cadence_seconds: int = HEARTBEAT_CADENCE_SECONDS,
                  terminal: bool = False, force: bool = False) -> bool:
    """Deterministically decide whether a heartbeat is due.

    - Terminal tracks never heartbeat unless ``force``.
    - First-ever heartbeat (no prior) is due.
    - Otherwise due once ``cadence_seconds`` have elapsed since the last one.
    """
    if force:
        return True
    if terminal:
        return False
    if not last_heartbeat_at:
        return True
    last = _parse_iso(last_heartbeat_at)
    current = _parse_iso(now)
    if last is None or current is None:
        return True
    return (current - last).total_seconds() >= cadence_seconds
