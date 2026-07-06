"""Conductor command-line interface (stdlib ``argparse`` only).

CLI contract (swarm-cli inspired):

* Every command supports ``--json`` for machine-readable output (Hermes/Telegram).
* Non-JSON output is concise and human-friendly.
* Commands exit non-zero on failure so they compose in shells/CI.
* Global ``--root`` (or ``$CONDUCTOR_HOME``) selects the state root.

Resolution precedence for the state root: ``--root`` > ``$CONDUCTOR_HOME`` >
nearest ``.conductor/`` above cwd > ``<cwd>/.conductor``.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path
from typing import Any, Optional

from .blocked_prompts import active_blocked_prompts
from .completion import CompletionEngine, CompletionError
from .dispatch import Dispatcher, DispatchError
from .doctor import run_doctor
from .intake import PlanError, approve_plan, create_planned_track, review_plan
from .lanes import LaneAdapter, LaneError
from .locks import LockConflict, LockError, LockManager
from .message_bus import MessageBus
from .models import (
    MessageType,
    RecipientType,
    SenderType,
)
from .operator import OperatorError, OperatorView
from .status import build_status
from .store import ConductorStore, default_state_root, find_state_root


# --------------------------------------------------------------------------- #
# Output helpers
# --------------------------------------------------------------------------- #
def _emit(data: Any, as_json: bool, human: Optional[str] = None) -> None:
    if as_json:
        print(json.dumps(data, indent=2, sort_keys=True))
    else:
        print(human if human is not None else json.dumps(data, indent=2, sort_keys=True))


def _resolve_store(args: argparse.Namespace, create: bool = False) -> ConductorStore:
    root = Path(args.root) if getattr(args, "root", None) else None
    return ConductorStore.resolve(root=root, create=create)


def _resolve_or_emit_error(args: argparse.Namespace):
    """Resolve the store, or emit a clear actionable error and return None.

    Phase 2 commands need an initialized state root; this keeps the
    "run conductor init first" guidance JSON-friendly.
    """
    try:
        return _resolve_store(args)
    except FileNotFoundError as exc:
        _emit({"ok": False, "error": str(exc),
               "hint": "Run 'conductor init' in the project root first."},
              args.json, human=f"error: {exc}")
        return None


# --------------------------------------------------------------------------- #
# Commands
# --------------------------------------------------------------------------- #
def cmd_init(args: argparse.Namespace) -> int:
    root = Path(args.root) if args.root else None
    if root is not None and root.name != ".conductor":
        target = root / ".conductor"
    elif root is not None:
        target = root
    else:
        existing = find_state_root()
        target = existing if existing is not None else default_state_root()

    store = ConductorStore(target)

    if args.dry_run:
        layout = [str(p) for p in store.planned_layout()]
        _emit(
            {"dry_run": True, "state_root": str(target), "would_create": layout,
             "already_exists": store.exists()},
            args.json,
            human=f"DRY RUN — would create state root at {target}\n"
            + "\n".join(f"  + {p}" for p in layout),
        )
        return 0

    config = store.init()
    _emit(
        {"initialized": True, "state_root": str(store.root), "config": config},
        args.json,
        human=f"Initialized Conductor state root at {store.root}",
    )
    return 0


def cmd_track_new(args: argparse.Namespace) -> int:
    store = _resolve_store(args)
    track = store.create_track(args.goal)
    _emit(
        {"track_id": track.track_id, "goal": track.goal, "state": track.state.value,
         "dir": str(store.track_dir(track.track_id))},
        args.json,
        human=f"Created track {track.track_id}\n  goal: {track.goal}\n  dir:  {store.track_dir(track.track_id)}",
    )
    return 0


def cmd_track_list(args: argparse.Namespace) -> int:
    store = _resolve_store(args)
    tracks = store.list_tracks()
    data = [{"track_id": t.track_id, "goal": t.goal, "state": t.state.value} for t in tracks]
    human = "\n".join(f"{t['track_id']}  [{t['state']}]  {t['goal']}" for t in data) or "(no tracks)"
    _emit({"tracks": data}, args.json, human=human)
    return 0


def cmd_go(args: argparse.Namespace) -> int:
    store = _resolve_or_emit_error(args)
    if store is None:
        return 2
    # Phase 2 only supports plan-only mode; accept the flag and proceed.
    try:
        record = create_planned_track(store, args.goal,
                                      task_workflow_mode=args.task_workflow_mode)
    except PlanError as exc:
        _emit({"ok": False, "error": str(exc)}, args.json, human=f"error: {exc}")
        return 2
    track = record.track
    data = {
        "ok": True,
        "track_id": track.track_id,
        "goal": track.goal,
        "track_state": track.state.value,
        "plan_status": record.plan_status.value,
        "plan_revision": record.plan_revision,
        "task_count": len(record.tasks),
        "task_workflow_mode": args.task_workflow_mode,
        "spec_ref": str(store.track_dir(track.track_id) / "spec.md"),
        "plan_ref": str(store.track_dir(track.track_id) / "plan.md"),
        "tasks": [{"task_id": t.task_id, "title": t.title, "state": t.state.value,
                   "dependencies": t.dependencies} for t in record.tasks],
    }
    human = (f"Planned track {track.track_id}\n"
             f"  goal:        {track.goal}\n"
             f"  plan_status: {record.plan_status.value}\n"
             f"  tasks:       {len(record.tasks)}\n"
             f"  spec:        {data['spec_ref']}\n"
             f"  plan:        {data['plan_ref']}\n"
             "  approval is pending — run 'conductor approve plan --track "
             f"{track.track_id}'")
    _emit(data, args.json, human=human)
    return 0


def cmd_plan_review(args: argparse.Namespace) -> int:
    store = _resolve_or_emit_error(args)
    if store is None:
        return 2
    try:
        summary = review_plan(store, args.track)
    except PlanError as exc:
        _emit({"ok": False, "error": str(exc)}, args.json, human=f"error: {exc}")
        return 2
    if args.json:
        _emit({"ok": True, **summary}, True)
    else:
        lines = [
            f"Plan review — {summary['track_id']}",
            f"  goal:           {summary['goal']}",
            f"  plan_status:    {summary['plan_status']}",
            f"  track_state:    {summary['track_state']}",
            f"  tasks:          {summary['task_count']}",
            f"  approval:       {'pending' if summary['approval_pending'] else ('approved' if summary['approved'] else 'n/a')}",
        ]
        for t in summary["tasks"]:
            deps = ", ".join(t["dependencies"]) or "-"
            lines.append(f"    - [{t['state']}] {t['title']} (deps: {deps})")
        _emit(summary, False, human="\n".join(lines))
    return 0


def cmd_approve_plan(args: argparse.Namespace) -> int:
    store = _resolve_or_emit_error(args)
    if store is None:
        return 2
    try:
        result = approve_plan(store, args.track, rationale=args.rationale or "")
    except PlanError as exc:
        _emit({"ok": False, "error": str(exc)}, args.json, human=f"error: {exc}")
        return 2
    human = (
        f"Plan {'already ' if result['already_approved'] else ''}approved for track {result['track_id']}\n"
        f"  plan_status: {result['plan_status']}\n"
        f"  track_state: {result['track_state']}\n"
        f"  decided_at:  {result['decided_at']}"
    )
    _emit({"ok": True, **result}, args.json, human=human)
    return 0


def _lane_adapter(args: argparse.Namespace):
    store = _resolve_or_emit_error(args)
    if store is None:
        return None
    return LaneAdapter(store)


def cmd_lane_ensure(args: argparse.Namespace) -> int:
    adapter = _lane_adapter(args)
    if adapter is None:
        return 2
    try:
        result = adapter.ensure(args.target)
    except LaneError as exc:
        _emit({"ok": False, "error": str(exc)}, args.json, human=f"error: {exc}")
        return 1
    _emit(result, args.json,
          human=f"Lane {result['target']} ensured — state={result['state']}")
    return 0


def cmd_lane_status(args: argparse.Namespace) -> int:
    adapter = _lane_adapter(args)
    if adapter is None:
        return 2
    try:
        result = adapter.status(args.target)
    except LaneError as exc:
        _emit({"ok": False, "error": str(exc)}, args.json, human=f"error: {exc}")
        return 2
    human = (f"Lane {result['target']}\n"
             f"  provider:        {result['provider']}\n"
             f"  state:           {result['state']}\n"
             f"  tmux_available:  {result['tmux_available']}\n"
             f"  last_heartbeat:  {result['last_heartbeat_at']}")
    _emit(result, args.json, human=human)
    return 0


def cmd_lane_capture(args: argparse.Namespace) -> int:
    adapter = _lane_adapter(args)
    if adapter is None:
        return 2
    try:
        result = adapter.capture(args.target, lines=args.lines)
    except LaneError as exc:
        _emit({"ok": False, "error": str(exc)}, args.json, human=f"error: {exc}")
        return 2
    if args.json:
        _emit(result, True)
    else:
        head = "\n".join((result.get("transcript") or "").splitlines()[-20:])
        _emit(result, False,
              human=(f"Lane {result['target']} — state={result['state']} "
                     f"lines={result['line_count']}\n--- transcript (tail) ---\n{head}"))
    return 0


def cmd_lane_submit(args: argparse.Namespace) -> int:
    adapter = _lane_adapter(args)
    if adapter is None:
        return 2
    try:
        result = adapter.submit(args.target, args.task_file, force=args.force)
    except LaneError as exc:
        _emit({"ok": False, "submitted": False, "error": str(exc)}, args.json,
              human=f"REFUSED: {exc}")
        return 1
    _emit(result, args.json,
          human=(f"Submitted to {result['target']} (state={result['state']})\n"
                 f"  instruction: {result['instruction']}"))
    return 0


def cmd_lane_blocked(args: argparse.Namespace) -> int:
    store = _resolve_or_emit_error(args)
    if store is None:
        return 2
    blocked = active_blocked_prompts(store, args.track)
    payload = {"ok": True, "track_id": args.track, "blocked_count": len(blocked),
               "blocked": blocked}
    human = "\n".join(
        f"{b['task_id']} -> {b['lane_target']} ({b['provider']}): {b['operator_action']}"
        for b in blocked
    ) or "no active blocked provider prompts"
    _emit(payload, args.json, human=human)
    return 0


def cmd_dispatch(args: argparse.Namespace) -> int:
    store = _resolve_or_emit_error(args)
    if store is None:
        return 2
    dispatcher = Dispatcher(store)
    try:
        result = dispatcher.dispatch(args.track, lane_session=args.lane_session,
                                     force=args.force, create_worktree=args.create_worktree)
    except DispatchError as exc:
        _emit({"ok": False, "error": str(exc)}, args.json, human=f"REFUSED: {exc}")
        return 1
    if args.json:
        _emit(result, True)
    else:
        lines = [f"Dispatched {result['dispatched_count']} task(s) on track {result['track_id']}"]
        for t in result["dispatched"]:
            lines.append(f"  - {t['task_id']} -> {t['lane_target']} "
                         f"[{t['dispatch_state']}] worktree={t['worktree_mode']} "
                         f"stale={t['stale_risk']}")
        if result.get("note"):
            lines.append(f"  note: {result['note']}")
        _emit(result, False, human="\n".join(lines))
    return 0


def cmd_task_status(args: argparse.Namespace) -> int:
    store = _resolve_or_emit_error(args)
    if store is None:
        return 2
    dispatcher = Dispatcher(store)
    try:
        result = dispatcher.task_status(args.track, args.task)
    except DispatchError as exc:
        _emit({"ok": False, "error": str(exc)}, args.json, human=f"error: {exc}")
        return 2
    human = (f"Task {result['task_id']} ({result.get('title', '')})\n"
             f"  task_state:     {result['task_state']}\n"
             f"  dispatch_state: {result.get('dispatch_state')}\n"
             f"  lane_state:     {result.get('lane_state')}\n"
             f"  worktree_mode:  {result.get('worktree_mode')}\n"
             f"  stale_risk:     {result.get('stale_risk')}\n"
             f"  blocker:        {result.get('blocker')}")
    _emit(result, args.json, human=human)
    return 0


def cmd_followup(args: argparse.Namespace) -> int:
    store = _resolve_or_emit_error(args)
    if store is None:
        return 2
    dispatcher = Dispatcher(store)
    try:
        result = dispatcher.followup(args.track, args.task, args.body_file, force=args.force)
    except DispatchError as exc:
        _emit({"ok": False, "error": str(exc)}, args.json, human=f"error: {exc}")
        return 2
    _emit(result, args.json,
          human=(f"Follow-up #{result['followup_index']} for {result['task_id']} "
                 f"-> {result['artifact_ref']} (delivered={result['delivered']})"))
    return 0


def cmd_nudge(args: argparse.Namespace) -> int:
    store = _resolve_or_emit_error(args)
    if store is None:
        return 2
    dispatcher = Dispatcher(store)
    try:
        result = dispatcher.nudge(args.track, args.task, force=args.force)
    except DispatchError as exc:
        _emit({"ok": False, "error": str(exc)}, args.json, human=f"error: {exc}")
        return 2
    _emit(result, args.json,
          human=(f"Nudged {result['task_id']} (sent={result['sent']}, "
                 f"lane_state={result.get('lane_state')})"))
    return 0


def _completion_engine(args: argparse.Namespace):
    store = _resolve_or_emit_error(args)
    if store is None:
        return None
    return CompletionEngine(store)


def cmd_verify(args: argparse.Namespace) -> int:
    engine = _completion_engine(args)
    if engine is None:
        return 2
    try:
        result = engine.verify(args.track)
    except CompletionError as exc:
        _emit({"ok": False, "error": str(exc), "evidence": exc.evidence}, args.json,
              human=f"error: {exc}")
        return 2
    human = [f"Verified track {result['track_id']}: "
             f"{result['verified_count']} passed, {result['failed_count']} failed"]
    for r in result["results"]:
        human.append(f"  - {r['task_id']}: {r['status']} ({r['task_state']}) — {r['reason']}")
    _emit(result, args.json, human="\n".join(human))
    return 0


def cmd_advance(args: argparse.Namespace) -> int:
    engine = _completion_engine(args)
    if engine is None:
        return 2
    try:
        result = engine.advance_verified(args.track)
    except CompletionError as exc:
        _emit({"ok": False, "error": str(exc), "evidence": exc.evidence}, args.json,
              human=f"error: {exc}")
        return 2
    human = (f"Advanced track {result['track_id']}: "
             f"{result['advanced_count']} complete, "
             f"{result['newly_ready_count']} newly ready")
    _emit(result, args.json, human=human)
    return 0


def _sleep_with_prompt_scan(store: ConductorStore, track_id: str,
                            poll_interval: float,
                            prompt_poll_interval: float) -> list:
    """Sleep up to poll_interval while checking for blocked prompts."""
    if poll_interval <= 0:
        return active_blocked_prompts(store, track_id)
    prompt_interval = max(prompt_poll_interval, 0.01)
    deadline = time.monotonic() + poll_interval
    while time.monotonic() < deadline:
        remaining = deadline - time.monotonic()
        time.sleep(min(prompt_interval, max(0.0, remaining)))
        blocked = active_blocked_prompts(store, track_id)
        if blocked:
            return blocked
    return []


def cmd_loop(args: argparse.Namespace) -> int:
    store = _resolve_or_emit_error(args)
    if store is None:
        return 2
    engine = CompletionEngine(store)
    dispatcher = Dispatcher(store)
    cycles = []
    finalized = {"attempted": False, "merge_approved": False, "closed": False}
    stop_reason = "max_cycles"
    exit_code = 0
    blocked = []
    for cycle in range(1, args.max_cycles + 1):
        try:
            verified = engine.verify_ready_results(args.track)
            advanced = engine.advance_verified(args.track)
            dispatched = dispatcher.dispatch(
                args.track,
                lane_session=args.lane_session,
                force=args.force,
                create_worktree=args.create_worktree,
            )
        except (CompletionError, DispatchError) as exc:
            _emit({"ok": False, "error": str(exc), "cycles": cycles}, args.json,
                  human=f"error: {exc}")
            return 2
        cycle_result = {"cycle": cycle, "verified": verified,
                        "advanced": advanced, "dispatched": dispatched}
        cycles.append(cycle_result)

        if args.stop_on_blocked_prompt:
            blocked = active_blocked_prompts(store, args.track)
            if blocked:
                stop_reason = "blocked_prompt"
                break

        if (verified["verified_count"] == 0
                and advanced["advanced_count"] == 0
                and advanced["newly_ready_count"] == 0
                and dispatched["dispatched_count"] == 0):
            if not args.watch:
                stop_reason = "idle"
                break
        if advanced.get("all_tasks_complete"):
            try:
                merge_result = engine.approve_merge(
                    args.track,
                    decided_by="conductor",
                    rationale="auto-finalized by conductor loop after all planned tasks completed",
                )
                close_result = engine.close(args.track)
                finalized = {
                    "attempted": True,
                    "merge_approved": bool(merge_result.get("merge_approved")),
                    "closed": bool(close_result.get("closed")),
                    "merge_result": merge_result,
                    "closed_result": close_result,
                }
            except CompletionError as exc:
                finalized = {"attempted": True, "merge_approved": False,
                             "closed": False, "error": str(exc),
                             "evidence": exc.evidence}
                stop_reason = "finalization_failed"
                break
            stop_reason = "closed"
            break
        if args.watch and cycle < args.max_cycles:
            if args.stop_on_blocked_prompt:
                blocked = _sleep_with_prompt_scan(
                    store, args.track, args.poll_interval, args.prompt_poll_interval)
                if blocked:
                    stop_reason = "blocked_prompt"
                    break
            else:
                time.sleep(args.poll_interval)
    result = {"ok": True, "track_id": args.track, "cycles": cycles,
              "cycle_count": len(cycles), "finalized": finalized,
              "watch": bool(args.watch), "stop_reason": stop_reason,
              "blocked": blocked}
    human = (f"Loop tick for {args.track}: {len(cycles)} cycle(s); "
             f"last dispatch={cycles[-1]['dispatched']['dispatched_count'] if cycles else 0}")
    _emit(result, args.json, human=human)
    return exit_code


def cmd_fix(args: argparse.Namespace) -> int:
    engine = _completion_engine(args)
    if engine is None:
        return 2
    try:
        result = engine.fix(args.track, args.task, body_file=args.body_file, force=args.force)
    except CompletionError as exc:
        _emit({"ok": False, "error": str(exc), "evidence": exc.evidence}, args.json,
              human=f"REFUSED: {exc}")
        return 1
    _emit(result, args.json,
          human=(f"Fix #{result['fix_attempt']}/{result['max_fix_attempts']} for "
                 f"{result['task_id']} -> {result['artifact_ref']} "
                 f"({result['remaining_attempts']} attempt(s) left)"))
    return 0


def cmd_approve_merge(args: argparse.Namespace) -> int:
    engine = _completion_engine(args)
    if engine is None:
        return 2
    try:
        result = engine.approve_merge(args.track, rationale=args.rationale or "", force=args.force)
    except CompletionError as exc:
        _emit({"ok": False, "error": str(exc), "evidence": exc.evidence}, args.json,
              human=f"REFUSED: {exc}")
        return 1
    _emit({"ok": True, **result}, args.json,
          human=(f"Merge {'already ' if result['already_approved'] else ''}approved for "
                 f"{result['track_id']} ({result['verified_task_count']} verified task(s))"))
    return 0


def cmd_close(args: argparse.Namespace) -> int:
    engine = _completion_engine(args)
    if engine is None:
        return 2
    try:
        result = engine.close(args.track, force=args.force)
    except CompletionError as exc:
        _emit({"ok": False, "error": str(exc), "evidence": exc.evidence}, args.json,
              human=f"REFUSED: {exc}")
        return 1
    _emit(result, args.json,
          human=(f"Closed track {result['track_id']} (state={result['track_state']})\n"
                 f"  summary: {result['summary_ref']}"))
    return 0


def cmd_reconcile(args: argparse.Namespace) -> int:
    engine = _completion_engine(args)
    if engine is None:
        return 2
    try:
        result = engine.reconcile(args.track)
    except CompletionError as exc:
        _emit({"ok": False, "error": str(exc), "evidence": exc.evidence}, args.json,
              human=f"error: {exc}")
        return 2
    human = [f"Reconciliation for {result['track_id']}: "
             f"consistent={result['consistent']}",
             f"  track_issues: {', '.join(result['track_issues']) or 'none'}"]
    for t in result["tasks"]:
        human.append(f"  - {t['task_id']} [{t['task_state']}] "
                     f"verification={t['verification_status']} issues={', '.join(t['issues']) or 'none'}")
    _emit(result, args.json, human="\n".join(human))
    return 0


def _operator_view(args: argparse.Namespace):
    store = _resolve_or_emit_error(args)
    if store is None:
        return None
    return OperatorView(store)


def cmd_operator_summary(args: argparse.Namespace) -> int:
    view = _operator_view(args)
    if view is None:
        return 2
    fmt = getattr(args, "format", "text")
    try:
        if args.json or fmt == "json":
            print(json.dumps(view.summary(args.track), indent=2, sort_keys=True))
        else:
            print(view.render_telegram(args.track))
    except OperatorError as exc:
        _emit({"ok": False, "error": str(exc)}, args.json, human=f"error: {exc}")
        return 2
    return 0


def cmd_operator_notify(args: argparse.Namespace) -> int:
    view = _operator_view(args)
    if view is None:
        return 2
    try:
        payload = view.notify(args.track)
    except OperatorError as exc:
        _emit({"ok": False, "error": str(exc)}, args.json, human=f"error: {exc}")
        return 2
    _emit(payload, args.json,
          human=f"[{payload['severity']}] {payload['signal']}\n{payload['telegram_text']}")
    return 0


def cmd_operator_heartbeat(args: argparse.Namespace) -> int:
    view = _operator_view(args)
    if view is None:
        return 2
    try:
        payload = view.heartbeat(args.track, now=args.now, force=args.force)
    except OperatorError as exc:
        _emit({"ok": False, "error": str(exc)}, args.json, human=f"error: {exc}")
        return 2
    _emit(payload, args.json,
          human=(f"heartbeat due={payload['due']} signal={payload['signal']} "
                 f"body={payload['body']}"))
    return 0


def cmd_operator_approval(args: argparse.Namespace) -> int:
    view = _operator_view(args)
    if view is None:
        return 2
    try:
        payload = view.approval(args.track, args.kind)
    except OperatorError as exc:
        _emit({"ok": False, "error": str(exc)}, args.json, human=f"error: {exc}")
        return 2
    if payload.get("needed") is False:
        human = f"{args.kind} approval: not needed ({payload.get('status')})"
    else:
        human = (f"{args.kind} approval needed (ready={payload.get('ready')})\n"
                 f"  $ {payload.get('command')}")
    _emit(payload, args.json, human=human)
    return 0


def cmd_operator_verify_hook(args: argparse.Namespace) -> int:
    view = _operator_view(args)
    if view is None:
        return 2
    try:
        payload = view.verify_hook(args.track)
    except OperatorError as exc:
        _emit({"ok": False, "error": str(exc)}, args.json, human=f"error: {exc}")
        return 2
    lines = [f"verify-hook for {payload['track_id']} (signal={payload['signal']}):"]
    for c in payload["commands"]:
        lines.append(f"  [{'auto' if c['auto_run'] else 'suggest'}] {c['command']}")
        lines.append(f"      expect: {c['expected']}")
    _emit(payload, args.json, human="\n".join(lines))
    return 0


def cmd_operator_artifacts(args: argparse.Namespace) -> int:
    view = _operator_view(args)
    if view is None:
        return 2
    try:
        payload = view.artifacts(args.track)
    except OperatorError as exc:
        _emit({"ok": False, "error": str(exc)}, args.json, human=f"error: {exc}")
        return 2
    _emit(payload, args.json)
    return 0


def cmd_status(args: argparse.Namespace) -> int:
    store = _resolve_store(args)
    status = build_status(store)
    if args.json:
        _emit(status, True)
    else:
        lines = [f"State root: {status['state_root']}",
                 "Totals: " + ", ".join(f"{k}={v}" for k, v in status["totals"].items())]
        for t in status["tracks"]:
            lines.append(f"- {t['track_id']} [{t['state']}] msgs={t['message_count']} "
                         f"locks={len(t['locks'])} workers={len(t['workers'])}  {t['goal']}")
        _emit(status, False, human="\n".join(lines))
    return 0


def cmd_message_send(args: argparse.Namespace) -> int:
    store = _resolve_store(args)
    try:
        msg_type = MessageType(args.type)
    except ValueError:
        valid = ", ".join(sorted(m.value for m in MessageType))
        print(f"error: invalid --type {args.type!r}; valid types: {valid}", file=sys.stderr)
        return 2

    body = args.body or ""
    if args.body_file:
        body = Path(args.body_file).read_text(encoding="utf-8")

    bus = MessageBus(store, args.track)
    msg = bus.send_simple(
        type=msg_type,
        body=body,
        sender_type=SenderType(args.sender_type),
        sender_id=args.worker or args.sender_id or "",
        recipient_type=RecipientType(args.recipient_type),
        recipient_id=args.recipient_id or "",
        task_id=args.task,
        summary=args.summary or "",
        body_ref=args.body_ref,
        requires_ack=args.requires_ack,
    )
    _emit(
        {"message_id": msg.message_id, "type": msg.type.value, "track_id": msg.track_id,
         "task_id": msg.task_id, "created_at": msg.created_at},
        args.json,
        human=f"Sent {msg.type.value} message {msg.message_id} on track {msg.track_id}",
    )
    return 0


def cmd_message_list(args: argparse.Namespace) -> int:
    store = _resolve_store(args)
    bus = MessageBus(store, args.track)
    type_filter = MessageType(args.type) if args.type else None
    messages = bus.list_messages(type=type_filter, task_id=args.task, limit=args.limit)
    data = [m.to_dict() for m in messages]
    if args.json:
        _emit({"track_id": args.track, "count": len(data), "messages": data}, True)
    else:
        human = "\n".join(
            f"{m['created_at']}  {m['type']:<14} {m['sender_id'] or '-':<16} {m['summary']}"
            for m in data
        ) or "(no messages)"
        _emit({"messages": data}, False, human=human)
    return 0


def cmd_lock_acquire(args: argparse.Namespace) -> int:
    store = _resolve_store(args)
    locks = LockManager(store, args.track)
    try:
        lock = locks.acquire(args.file, args.worker, task_id=args.task)
    except LockConflict as exc:
        payload = {"acquired": False, "path": exc.path, "holder": exc.holder}
        if args.json:
            _emit(payload, True)
        else:
            print(f"LOCK CONFLICT: {exc}", file=sys.stderr)
        return 1
    except LockError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    _emit(
        {"acquired": True, "path": lock.path, "worker_id": lock.worker_id,
         "acquired_at": lock.acquired_at},
        args.json,
        human=f"Locked {lock.path} for worker {lock.worker_id}",
    )
    return 0


def cmd_lock_release(args: argparse.Namespace) -> int:
    store = _resolve_store(args)
    locks = LockManager(store, args.track)
    try:
        removed = locks.release(args.file, args.worker)
    except LockConflict as exc:
        if args.json:
            _emit({"released": False, "path": exc.path, "holder": exc.holder}, True)
        else:
            print(f"LOCK CONFLICT: {exc}", file=sys.stderr)
        return 1
    _emit(
        {"released": removed, "path": args.file, "worker_id": args.worker},
        args.json,
        human=(f"Released {args.file}" if removed else f"No lock held on {args.file}"),
    )
    return 0


def cmd_lock_list(args: argparse.Namespace) -> int:
    store = _resolve_store(args)
    locks = LockManager(store, args.track)
    data = [fl.to_dict() for fl in locks.list_locks()]
    human = "\n".join(f"{fl['path']}  ->  {fl['worker_id']}" for fl in data) or "(no locks)"
    _emit({"track_id": args.track, "locks": data}, args.json, human=human)
    return 0


def cmd_doctor(args: argparse.Namespace) -> int:
    root = Path(args.root) if args.root else None
    try:
        store = ConductorStore.resolve(root=root, create=False)
    except FileNotFoundError as exc:
        report = {"ok": False, "error": str(exc)}
        _emit(report, args.json, human=f"DOCTOR: FAIL — {exc}")
        return 1
    report = run_doctor(store)
    if args.json:
        _emit(report, True)
    else:
        lines = [f"DOCTOR: {'OK' if report['ok'] else 'FAIL'}  ({report['state_root']})"]
        for c in report["checks"]:
            lines.append(f"  [{'ok' if c['ok'] else 'XX'}] {c['name']}: {c['detail']}")
        _emit(report, False, human="\n".join(lines))
    return 0 if report["ok"] else 1


# --------------------------------------------------------------------------- #
# Parser
# --------------------------------------------------------------------------- #
def build_parser() -> argparse.ArgumentParser:
    # A shared parent carrying the global flags. Subparsers inherit it with
    # SUPPRESS defaults so repeating ``--json``/``--root`` *after* a subcommand
    # works (e.g. ``conductor status --json``) without a child default clobbering
    # the value already parsed at the top level. argparse evaluates the flag at
    # whatever position it appears; SUPPRESS means "don't touch the attribute if
    # absent here", preserving the global parse.
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--root", default=argparse.SUPPRESS,
                        help="Conductor state root or its parent (overrides $CONDUCTOR_HOME).")
    common.add_argument("--json", action="store_true", default=argparse.SUPPRESS,
                        help="Emit machine-readable JSON.")

    parser = argparse.ArgumentParser(
        prog="conductor",
        parents=[common],
        description="Local-first control plane for coding-agent CLIs (Phase 1 kernel).",
    )
    # NB: do NOT seed json/root defaults here. With SUPPRESS, the flags only land
    # in the namespace when actually passed (at any position). A baseline default
    # would be re-applied by the subparser and clobber a global-position flag.
    # main() backfills the missing attributes after parsing.
    sub = parser.add_subparsers(dest="command", required=True)

    def add(name: str, parent, **kwargs):
        return parent.add_parser(name, parents=[common], **kwargs)

    # init
    p_init = add("init", sub, help="Create the .conductor/ state layout.")
    p_init.add_argument("--dry-run", action="store_true", help="Show what would be created without writing.")
    p_init.set_defaults(func=cmd_init)

    # track
    p_track = add("track", sub, help="Track operations.")
    track_sub = p_track.add_subparsers(dest="track_command", required=True)
    p_track_new = add("new", track_sub, help="Create a new track from a goal.")
    p_track_new.add_argument("goal", help="High-level goal for the track.")
    p_track_new.set_defaults(func=cmd_track_new)
    p_track_list = add("list", track_sub, help="List tracks.")
    p_track_list.set_defaults(func=cmd_track_list)

    # go (Phase 2 goal intake)
    p_go = add("go", sub, help="Intake a goal into a track and generate a plan.")
    p_go.add_argument("goal", help="High-level goal to plan.")
    p_go.add_argument("--plan-only", action="store_true",
                      help="Generate spec/plan/tasks without dispatching (the only Phase 2 mode).")
    p_go.add_argument("--task-workflow-mode", choices=["stage", "full"], default="stage",
                      help="Per-task workflow contract: stage keeps current stage-slice behavior; full requires each task result to include plan/actions/evidence/self-evaluation/risks/handoff sections.")
    p_go.set_defaults(func=cmd_go)

    # plan (review gate)
    p_plan = add("plan", sub, help="Plan operations.")
    plan_sub = p_plan.add_subparsers(dest="plan_command", required=True)
    p_plan_review = add("review", plan_sub, help="Show a machine-readable plan summary.")
    p_plan_review.add_argument("--track", required=True)
    p_plan_review.set_defaults(func=cmd_plan_review)

    # approve (separate approval gate)
    p_approve = add("approve", sub, help="Approval gates.")
    approve_sub = p_approve.add_subparsers(dest="approve_command", required=True)
    p_approve_plan = add("plan", approve_sub, help="Approve a track's plan.")
    p_approve_plan.add_argument("--track", required=True)
    p_approve_plan.add_argument("--rationale", help="Optional rationale recorded with the approval.")
    p_approve_plan.set_defaults(func=cmd_approve_plan)

    p_approve_merge = add("merge", approve_sub, help="Approve a track's merge (requires verified tasks).")
    p_approve_merge.add_argument("--track", required=True)
    p_approve_merge.add_argument("--rationale", help="Optional rationale recorded with the approval.")
    p_approve_merge.add_argument("--force", action="store_true",
                                 help="Override the verification gate (use with caution).")
    p_approve_merge.set_defaults(func=cmd_approve_merge)

    # lane (Phase 3 tmux lane adapter)
    p_lane = add("lane", sub, help="tmux lane operations.")
    lane_sub = p_lane.add_subparsers(dest="lane_command", required=True)

    p_lane_ensure = add("ensure", lane_sub, help="Ensure a tmux lane exists.")
    p_lane_ensure.add_argument("--target", required=True, help="Lane target 'session:window'.")
    p_lane_ensure.set_defaults(func=cmd_lane_ensure)

    p_lane_status = add("status", lane_sub, help="Classify and report lane readiness.")
    p_lane_status.add_argument("--target", required=True)
    p_lane_status.set_defaults(func=cmd_lane_status)

    p_lane_capture = add("capture", lane_sub, help="Capture recent lane transcript.")
    p_lane_capture.add_argument("--target", required=True)
    p_lane_capture.add_argument("--lines", type=int, default=200, help="Transcript lines to capture.")
    p_lane_capture.set_defaults(func=cmd_lane_capture)

    p_lane_submit = add("submit", lane_sub, help="Submit a short artifact-reference instruction.")
    p_lane_submit.add_argument("--target", required=True)
    p_lane_submit.add_argument("--task-file", required=True, help="Path to the task artifact.")
    p_lane_submit.add_argument("--force", action="store_true",
                               help="Override the safe readiness gate (use with caution).")
    p_lane_submit.set_defaults(func=cmd_lane_submit)

    p_lane_blocked = add("blocked", lane_sub, help="List active tasks whose lanes are blocked on provider prompts.")
    p_lane_blocked.add_argument("--track", required=True)
    p_lane_blocked.set_defaults(func=cmd_lane_blocked)

    # dispatch (Phase 4)
    p_dispatch = add("dispatch", sub, help="Dispatch ready tasks of an approved track.")
    p_dispatch.add_argument("--track", required=True)
    p_dispatch.add_argument("--lane-session", help="Override the tmux session/project segment.")
    p_dispatch.add_argument("--force", action="store_true",
                            help="Override lane readiness gate on submit (use with caution).")
    p_dispatch.add_argument("--create-worktree", action="store_true",
                            help="Actually create a git worktree (default: plan only).")
    p_dispatch.set_defaults(func=cmd_dispatch)

    # advance / loop (long-horizon engineering loop)
    p_advance = add("advance", sub, help="Advance verified tasks and release dependency successors.")
    p_advance.add_argument("--track", required=True)
    p_advance.set_defaults(func=cmd_advance)

    p_loop = add("loop", sub, help="One long-horizon loop tick: verify available results, advance, dispatch.")
    p_loop.add_argument("--track", required=True)
    p_loop.add_argument("--lane-session", help="Override the tmux session/project segment.")
    p_loop.add_argument("--max-cycles", type=int, default=1,
                        help="Maximum loop cycles to run in this invocation.")
    p_loop.add_argument("--watch", action="store_true",
                        help="Keep polling idle/running tasks instead of exiting on the first no-progress cycle.")
    p_loop.add_argument("--poll-interval", type=float, default=30.0,
                        help="Seconds to sleep between --watch loop cycles.")
    p_loop.add_argument("--prompt-poll-interval", type=float, default=3.0,
                        help="Seconds between blocked-prompt scans during --watch sleeps when --stop-on-blocked-prompt is set.")
    p_loop.add_argument("--stop-on-blocked-prompt", action="store_true",
                        help="Stop --watch quickly when an active worker lane is waiting on a provider approval prompt.")
    p_loop.add_argument("--force", action="store_true",
                        help="Override lane readiness gate on submit (use with caution).")
    p_loop.add_argument("--create-worktree", action="store_true",
                        help="Actually create a git worktree (default: plan only).")
    p_loop.set_defaults(func=cmd_loop)

    # task (status)
    p_task = add("task", sub, help="Task operations.")
    task_sub = p_task.add_subparsers(dest="task_command", required=True)
    p_task_status = add("status", task_sub, help="Show a task's dispatch/runtime status.")
    p_task_status.add_argument("--track", required=True)
    p_task_status.add_argument("--task", required=True)
    p_task_status.set_defaults(func=cmd_task_status)

    # followup
    p_followup = add("followup", sub, help="Write a follow-up artifact/message for a task.")
    p_followup.add_argument("--track", required=True)
    p_followup.add_argument("--task", required=True)
    p_followup.add_argument("--body-file", required=True, help="File whose contents become the follow-up artifact.")
    p_followup.add_argument("--force", action="store_true",
                            help="Override lane readiness when delivering the reference.")
    p_followup.set_defaults(func=cmd_followup)

    # nudge
    p_nudge = add("nudge", sub, help="Send/record a short nudge for a task.")
    p_nudge.add_argument("--track", required=True)
    p_nudge.add_argument("--task", required=True)
    p_nudge.add_argument("--force", action="store_true",
                         help="Override lane readiness when sending the nudge.")
    p_nudge.set_defaults(func=cmd_nudge)

    # verify / fix / close / reconcile (Phase 5)
    p_verify = add("verify", sub, help="Run verification gates on dispatched tasks.")
    p_verify.add_argument("--track", required=True)
    p_verify.set_defaults(func=cmd_verify)

    p_fix = add("fix", sub, help="Open a bounded fix-loop attempt for a task.")
    p_fix.add_argument("--track", required=True)
    p_fix.add_argument("--task", required=True)
    p_fix.add_argument("--body-file", help="Optional file whose contents become the fix artifact.")
    p_fix.add_argument("--force", action="store_true", help="Override the max-attempts limit.")
    p_fix.set_defaults(func=cmd_fix)

    p_close = add("close", sub, help="Close a track (requires merge approval).")
    p_close.add_argument("--track", required=True)
    p_close.add_argument("--force", action="store_true", help="Override the merge-approval gate.")
    p_close.set_defaults(func=cmd_close)

    p_reconcile = add("reconcile", sub, help="Reconstruct + report track state (resume reconciliation).")
    p_reconcile.add_argument("--track", required=True)
    p_reconcile.set_defaults(func=cmd_reconcile)

    # operator (Phase 6 — Hermes/Telegram surface)
    p_op = add("operator", sub, help="Operator/chat surface (summaries, notifications, hooks).")
    op_sub = p_op.add_subparsers(dest="operator_command", required=True)

    p_op_summary = add("summary", op_sub, help="Chat-safe operator summary.")
    p_op_summary.add_argument("--track", help="Limit to one track (default: all tracks).")
    p_op_summary.add_argument("--format", choices=["json", "text", "telegram"], default="text",
                              help="Output format (default text/telegram-safe).")
    p_op_summary.set_defaults(func=cmd_operator_summary)

    p_op_notify = add("notify", op_sub, help="Terminal-state notification payload.")
    p_op_notify.add_argument("--track", required=True)
    p_op_notify.set_defaults(func=cmd_operator_notify)

    p_op_hb = add("heartbeat", op_sub, help="Heartbeat due/not-due payload (5-min cadence).")
    p_op_hb.add_argument("--track", required=True)
    p_op_hb.add_argument("--now", help="ISO-8601 'now' for deterministic evaluation.")
    p_op_hb.add_argument("--force", action="store_true", help="Force a heartbeat even if not due/terminal.")
    p_op_hb.set_defaults(func=cmd_operator_heartbeat)

    p_op_appr = add("approval", op_sub, help="Approval request payload (plan/merge).")
    p_op_appr.add_argument("--track", required=True)
    p_op_appr.add_argument("--kind", required=True, choices=["plan", "merge"])
    p_op_appr.set_defaults(func=cmd_operator_approval)

    p_op_hook = add("verify-hook", op_sub, help="Commands Hermes should run next.")
    p_op_hook.add_argument("--track", required=True)
    p_op_hook.set_defaults(func=cmd_operator_verify_hook)

    p_op_arts = add("artifacts", op_sub, help="Bounded artifact links for a track.")
    p_op_arts.add_argument("--track", required=True)
    p_op_arts.set_defaults(func=cmd_operator_artifacts)

    # status
    p_status = add("status", sub, help="Operator status across all tracks.")
    p_status.set_defaults(func=cmd_status)

    # message
    p_msg = add("message", sub, help="Message bus operations.")
    msg_sub = p_msg.add_subparsers(dest="message_command", required=True)

    p_msg_send = add("send", msg_sub, help="Append a message to a track's queue.")
    p_msg_send.add_argument("--track", required=True)
    p_msg_send.add_argument("--type", required=True, help="Message type, e.g. PROGRESS.")
    p_msg_send.add_argument("--body", help="Inline message body.")
    p_msg_send.add_argument("--body-file", help="Read body from a file.")
    p_msg_send.add_argument("--body-ref", help="Reference to an external artifact path.")
    p_msg_send.add_argument("--summary", help="Short operator-visible summary.")
    p_msg_send.add_argument("--task", help="Associated task id.")
    p_msg_send.add_argument("--worker", help="Sender worker id (shortcut for --sender-id).")
    p_msg_send.add_argument("--sender-id", default="", help="Sender id.")
    p_msg_send.add_argument("--sender-type", default=SenderType.WORKER.value,
                            choices=[s.value for s in SenderType])
    p_msg_send.add_argument("--recipient-type", default=RecipientType.BROADCAST.value,
                            choices=[r.value for r in RecipientType])
    p_msg_send.add_argument("--recipient-id", default="")
    p_msg_send.add_argument("--requires-ack", action="store_true")
    p_msg_send.set_defaults(func=cmd_message_send)

    p_msg_list = add("list", msg_sub, help="List messages from a track's queue.")
    p_msg_list.add_argument("--track", required=True)
    p_msg_list.add_argument("--type", help="Filter by message type.")
    p_msg_list.add_argument("--task", help="Filter by task id.")
    p_msg_list.add_argument("--limit", type=int, help="Return only the last N messages.")
    p_msg_list.set_defaults(func=cmd_message_list)

    # lock
    p_lock = add("lock", sub, help="File lock operations.")
    lock_sub = p_lock.add_subparsers(dest="lock_command", required=True)

    p_lock_acq = add("acquire", lock_sub, help="Acquire a file lock.")
    p_lock_acq.add_argument("--track", required=True)
    p_lock_acq.add_argument("--file", required=True)
    p_lock_acq.add_argument("--worker", required=True)
    p_lock_acq.add_argument("--task", help="Associated task id.")
    p_lock_acq.set_defaults(func=cmd_lock_acquire)

    p_lock_rel = add("release", lock_sub, help="Release a file lock.")
    p_lock_rel.add_argument("--track", required=True)
    p_lock_rel.add_argument("--file", required=True)
    p_lock_rel.add_argument("--worker", required=True)
    p_lock_rel.set_defaults(func=cmd_lock_release)

    p_lock_list = add("list", lock_sub, help="List active file locks.")
    p_lock_list.add_argument("--track", required=True)
    p_lock_list.set_defaults(func=cmd_lock_list)

    # doctor
    p_doctor = add("doctor", sub, help="Diagnose state-root health.")
    p_doctor.set_defaults(func=cmd_doctor)

    return parser


def main(argv: Optional[list] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    # Backfill SUPPRESS-ed globals so command handlers can read them unconditionally.
    if not hasattr(args, "json"):
        args.json = False
    if not hasattr(args, "root"):
        args.root = None
    try:
        return args.func(args)
    except FileNotFoundError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    except KeyError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
