"""Domain models for the Conductor Phase 1 kernel.

Every model is a stdlib :mod:`dataclasses` dataclass with three contracts:

* ``to_dict()``  -> a JSON-serializable dict (enums collapse to their string value).
* ``from_dict()`` -> validated reconstruction from such a dict.
* ``validate()`` -> raise :class:`SchemaError` on malformed state.

The models are deliberately persistence-agnostic. They know how to turn
themselves into plain data; :mod:`conductor.store` and friends decide where that
data lives on disk. This keeps the schema layer free of filesystem coupling so
it can be unit-tested in isolation.

A single ``SCHEMA_VERSION`` is stamped onto durable records so future phases can
migrate state written by this one.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field, fields
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional

SCHEMA_VERSION = 1


# --------------------------------------------------------------------------- #
# Shared helpers
# --------------------------------------------------------------------------- #
class SchemaError(ValueError):
    """Raised when a record fails structural validation."""


def utc_now_iso() -> str:
    """Current UTC time as an ISO-8601 string with a trailing ``Z``-style offset."""
    return datetime.now(timezone.utc).isoformat()


def new_id(prefix: str) -> str:
    """Generate a short, prefixed, collision-resistant identifier.

    Example: ``new_id("track")`` -> ``"track_3f1e3a51"``. The prefix makes raw
    JSONL logs human-readable; the uuid suffix keeps them unique.
    """
    return f"{prefix}_{uuid.uuid4().hex[:8]}"


def _enum_value(value: Any) -> Any:
    return value.value if isinstance(value, Enum) else value


def _coerce_enum(enum_cls: type, value: Any, field_name: str) -> Any:
    """Accept either an enum member or its string value; validate membership."""
    if isinstance(value, enum_cls):
        return value
    try:
        return enum_cls(value)
    except ValueError as exc:  # pragma: no cover - message tested via from_dict
        valid = ", ".join(sorted(m.value for m in enum_cls))
        raise SchemaError(
            f"{field_name!r} must be one of [{valid}], got {value!r}"
        ) from exc


# --------------------------------------------------------------------------- #
# Enums
# --------------------------------------------------------------------------- #
class TrackState(str, Enum):
    CREATED = "created"
    PLANNING = "planning"
    PLAN_REVIEW = "plan_review"
    APPROVED = "approved"
    DISPATCHED = "dispatched"
    VERIFYING = "verifying"
    COMPLETE = "complete"
    BLOCKED = "blocked"
    CANCELLED = "cancelled"


class PlanStatus(str, Enum):
    NONE = "none"            # track created, no plan generated yet
    DRAFT = "draft"          # plan being generated/revised
    PENDING_REVIEW = "pending_review"  # plan generated, awaiting operator approval
    APPROVED = "approved"    # plan approved; dispatch may proceed (later phase)
    REJECTED = "rejected"    # plan rejected; needs revision


class TaskState(str, Enum):
    PENDING = "pending"
    READY = "ready"
    DISPATCHED = "dispatched"
    WORKING = "working"
    READY_FOR_REVIEW = "ready_for_review"
    VERIFYING = "verifying"
    NEEDS_FIX = "needs_fix"            # failed verification; awaiting a fix (Phase 5)
    READY_FOR_MERGE = "ready_for_merge"  # passed verification (Phase 5)
    COMPLETE = "complete"
    BLOCKED = "blocked"
    FAILED = "failed"
    CANCELLED = "cancelled"


class AttemptState(str, Enum):
    STARTED = "started"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    ABANDONED = "abandoned"


class LaneState(str, Enum):
    ABSENT = "absent"
    SHELL = "shell"
    PROVIDER_READY = "provider_ready"
    BUSY = "busy"
    BLOCKED_PROMPT = "blocked_prompt"
    UNKNOWN = "unknown"


class DispatchState(str, Enum):
    """Outcome of a dispatch attempt for a single task (Phase 4)."""
    SUBMITTED = "submitted"        # instruction delivered to a provider_ready lane
    PENDING_LANE = "pending_lane"  # artifacts ready, lane absent/shell/busy/unknown
    BLOCKED_LANE = "blocked_lane"  # lane shows an operator-action prompt
    FAILED = "failed"              # unexpected failure during dispatch


class StaleRisk(str, Enum):
    NONE = "none"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class WorktreeMode(str, Enum):
    NOT_GIT_REPO = "not_git_repo"      # project root is not a git repo; use current workspace
    GIT_PLANNED = "git_planned"        # repo present; worktree/branch computed but not created
    GIT_WORKTREE = "git_worktree"      # isolated worktree actually created


class MessageType(str, Enum):
    # Operational message bus types (SupaConductor-aligned).
    PROGRESS = "PROGRESS"
    TASK_COMPLETE = "TASK_COMPLETE"
    TASK_FAILED = "TASK_FAILED"
    FILE_LOCK = "FILE_LOCK"
    FILE_UNLOCK = "FILE_UNLOCK"
    BLOCKED = "BLOCKED"
    HEARTBEAT = "HEARTBEAT"
    ASSIGNMENT = "ASSIGNMENT"
    STATUS = "STATUS"
    QUESTION = "QUESTION"
    RESULT = "RESULT"
    EVENT = "EVENT"
    VERIFICATION = "VERIFICATION"
    FOLLOWUP = "FOLLOWUP"
    # Board / decision protocol types.
    BOARD_ASSESS = "BOARD_ASSESS"
    BOARD_DISCUSS = "BOARD_DISCUSS"
    BOARD_VOTE = "BOARD_VOTE"
    BOARD_RESOLVE = "BOARD_RESOLVE"


class SenderType(str, Enum):
    OPERATOR = "operator"
    CONDUCTOR = "conductor"
    WORKER = "worker"
    SYSTEM = "system"
    VERIFIER = "verifier"


class RecipientType(str, Enum):
    LANE = "lane"
    TASK = "task"
    TRACK = "track"
    WORKFLOW = "workflow"
    OPERATOR = "operator"
    BROADCAST = "broadcast"


class HeartbeatStatus(str, Enum):
    ALIVE = "alive"
    STALE = "stale"
    DEAD = "dead"
    UNKNOWN = "unknown"


class ApprovalKind(str, Enum):
    PLAN = "plan"
    MERGE = "merge"
    DESTRUCTIVE = "destructive"


class ApprovalState(str, Enum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    WAIVED = "waived"


class VerificationStatus(str, Enum):
    PENDING = "pending"
    PASSED = "passed"
    FAILED = "failed"
    WAIVED = "waived"


class EvidenceLevel(str, Enum):
    UNVERIFIED = "unverified"
    WORKER_REPORTED = "worker_reported"
    TOOL_VERIFIED = "tool_verified"
    OPERATOR_VERIFIED = "operator_verified"


class NotificationSeverity(str, Enum):
    INFO = "info"
    SUCCESS = "success"
    WARNING = "warning"
    ERROR = "error"


# --------------------------------------------------------------------------- #
# Base
# --------------------------------------------------------------------------- #
@dataclass
class _Model:
    """Mixin giving every model uniform (de)serialization + validation hooks.

    ``to_dict`` walks declared fields, unwrapping enums and recursing into nested
    models/lists so the result is always plain JSON data. ``from_dict`` is the
    inverse and is the *only* sanctioned construction path for data read off
    disk, because it runs :meth:`validate`.
    """

    def to_dict(self) -> Dict[str, Any]:
        out: Dict[str, Any] = {}
        for f in fields(self):
            value = getattr(self, f.name)
            out[f.name] = _serialize(value)
        return out

    @classmethod
    def from_dict(cls, data: Dict[str, Any]):
        if not isinstance(data, dict):
            raise SchemaError(f"{cls.__name__}.from_dict expects a dict, got {type(data).__name__}")
        known = {f.name for f in fields(cls)}
        kwargs = {k: v for k, v in data.items() if k in known}
        obj = cls(**kwargs)  # type: ignore[arg-type]
        obj._post_load()
        obj.validate()
        return obj

    # Subclasses override to coerce enum fields after a raw-dict load.
    def _post_load(self) -> None:  # pragma: no cover - default no-op
        pass

    def validate(self) -> None:  # pragma: no cover - default no-op
        pass


def _serialize(value: Any) -> Any:
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, _Model):
        return value.to_dict()
    if isinstance(value, list):
        return [_serialize(v) for v in value]
    if isinstance(value, dict):
        return {k: _serialize(v) for k, v in value.items()}
    return value


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise SchemaError(message)


# --------------------------------------------------------------------------- #
# AccessList — Fugu-style scoped context visibility
# --------------------------------------------------------------------------- #
@dataclass
class AccessList(_Model):
    """Declares exactly which prior artifacts/tasks a worker may see.

    Mirrors Fugu's access-list communication topology: context is a deliberate
    grant, never a global paste.
    """

    task_ids: List[str] = field(default_factory=list)
    artifact_refs: List[str] = field(default_factory=list)
    allow_broadcast: bool = False

    def validate(self) -> None:
        _require(isinstance(self.task_ids, list), "AccessList.task_ids must be a list")
        _require(isinstance(self.artifact_refs, list), "AccessList.artifact_refs must be a list")
        _require(isinstance(self.allow_broadcast, bool), "AccessList.allow_broadcast must be a bool")


# --------------------------------------------------------------------------- #
# Track
# --------------------------------------------------------------------------- #
@dataclass
class Track(_Model):
    """A durable unit of work: a goal plus its spec/plan/metadata and lifecycle."""

    track_id: str = field(default_factory=lambda: new_id("track"))
    goal: str = ""
    state: TrackState = TrackState.CREATED
    spec_ref: Optional[str] = "spec.md"
    plan_ref: Optional[str] = "plan.md"
    metadata_ref: Optional[str] = "metadata.json"
    created_at: str = field(default_factory=utc_now_iso)
    updated_at: str = field(default_factory=utc_now_iso)
    schema_version: int = SCHEMA_VERSION
    tags: List[str] = field(default_factory=list)

    def _post_load(self) -> None:
        self.state = _coerce_enum(TrackState, self.state, "Track.state")

    def validate(self) -> None:
        _require(bool(self.track_id), "Track.track_id is required")
        _require(isinstance(self.goal, str) and self.goal.strip() != "", "Track.goal must be non-empty")
        _require(isinstance(self.state, TrackState), "Track.state must be a TrackState")


# --------------------------------------------------------------------------- #
# Task / TaskAttempt
# --------------------------------------------------------------------------- #
@dataclass
class Task(_Model):
    task_id: str = field(default_factory=lambda: new_id("task"))
    track_id: str = ""
    title: str = ""
    description: str = ""
    state: TaskState = TaskState.PENDING
    dependencies: List[str] = field(default_factory=list)
    owner_lane: Optional[str] = None
    access_list: AccessList = field(default_factory=AccessList)
    input_refs: List[str] = field(default_factory=list)
    output_refs: List[str] = field(default_factory=list)
    verification_refs: List[str] = field(default_factory=list)
    method_id: str = "build"
    acceptance_criteria: List[str] = field(default_factory=list)
    definition_of_done_refs: List[str] = field(default_factory=list)
    # Prose expectations (worker guidance) vs. real executable commands.
    # verification_commands holds strictly executable strings the verifier runs.
    verification_requirements: List[str] = field(default_factory=list)
    verification_commands: List[str] = field(default_factory=list)
    autonomy_policy: str = "auto_ok"
    risk_class: str = "normal"
    created_at: str = field(default_factory=utc_now_iso)
    updated_at: str = field(default_factory=utc_now_iso)
    schema_version: int = SCHEMA_VERSION

    def _post_load(self) -> None:
        self.state = _coerce_enum(TaskState, self.state, "Task.state")
        if isinstance(self.access_list, dict):
            self.access_list = AccessList.from_dict(self.access_list)

    def validate(self) -> None:
        _require(bool(self.task_id), "Task.task_id is required")
        _require(bool(self.track_id), "Task.track_id is required")
        _require(isinstance(self.state, TaskState), "Task.state must be a TaskState")
        _require(isinstance(self.dependencies, list), "Task.dependencies must be a list")
        _require(isinstance(self.access_list, AccessList), "Task.access_list must be an AccessList")
        _require(isinstance(self.method_id, str) and bool(self.method_id), "Task.method_id must be non-empty")
        _require(isinstance(self.acceptance_criteria, list), "Task.acceptance_criteria must be a list")
        _require(isinstance(self.definition_of_done_refs, list), "Task.definition_of_done_refs must be a list")
        _require(isinstance(self.verification_commands, list), "Task.verification_commands must be a list")
        _require(isinstance(self.autonomy_policy, str), "Task.autonomy_policy must be a string")
        _require(isinstance(self.risk_class, str), "Task.risk_class must be a string")
        self.access_list.validate()


@dataclass
class TaskAttempt(_Model):
    attempt_id: str = field(default_factory=lambda: new_id("attempt"))
    task_id: str = ""
    track_id: str = ""
    attempt_number: int = 1
    state: AttemptState = AttemptState.STARTED
    lane_target: Optional[str] = None
    worktree_ref: Optional[str] = None
    started_at: str = field(default_factory=utc_now_iso)
    ended_at: Optional[str] = None
    result_ref: Optional[str] = None
    schema_version: int = SCHEMA_VERSION

    def _post_load(self) -> None:
        self.state = _coerce_enum(AttemptState, self.state, "TaskAttempt.state")

    def validate(self) -> None:
        _require(bool(self.attempt_id), "TaskAttempt.attempt_id is required")
        _require(bool(self.task_id), "TaskAttempt.task_id is required")
        _require(isinstance(self.attempt_number, int) and self.attempt_number >= 1,
                 "TaskAttempt.attempt_number must be a positive int")
        _require(isinstance(self.state, AttemptState), "TaskAttempt.state must be an AttemptState")


# --------------------------------------------------------------------------- #
# WorkerLane
# --------------------------------------------------------------------------- #
@dataclass
class WorkerLane(_Model):
    lane_id: str = field(default_factory=lambda: new_id("lane"))
    target: str = ""  # e.g. "Conductor:claude" (project:provider)
    provider: Optional[str] = None
    state: LaneState = LaneState.UNKNOWN
    current_task_id: Optional[str] = None
    last_seen_at: Optional[str] = None
    schema_version: int = SCHEMA_VERSION

    def _post_load(self) -> None:
        self.state = _coerce_enum(LaneState, self.state, "WorkerLane.state")

    def validate(self) -> None:
        _require(bool(self.lane_id), "WorkerLane.lane_id is required")
        _require(bool(self.target), "WorkerLane.target is required")
        _require(isinstance(self.state, LaneState), "WorkerLane.state must be a LaneState")


# --------------------------------------------------------------------------- #
# MessageEnvelope
# --------------------------------------------------------------------------- #
@dataclass
class Endpoint(_Model):
    type: Any = SenderType.SYSTEM
    id: str = ""

    def validate(self) -> None:
        _require(isinstance(self.id, str), "Endpoint.id must be a string")


@dataclass
class MessageEnvelope(_Model):
    """The single coordination unit appended to ``queue.jsonl``.

    Large payloads must be written as artifacts and referenced via ``body_ref``;
    only a short ``summary`` and ``body`` live inline so the log stays scannable
    and tmux-safe.
    """

    message_id: str = field(default_factory=lambda: new_id("msg"))
    track_id: str = ""
    task_id: Optional[str] = None
    run_id: Optional[str] = None
    type: MessageType = MessageType.PROGRESS
    sender_type: SenderType = SenderType.SYSTEM
    sender_id: str = ""
    recipient_type: RecipientType = RecipientType.BROADCAST
    recipient_id: str = ""
    body: str = ""
    body_ref: Optional[str] = None
    summary: str = ""
    requires_ack: bool = False
    causation_id: Optional[str] = None
    correlation_id: Optional[str] = None
    created_at: str = field(default_factory=utc_now_iso)
    schema_version: int = SCHEMA_VERSION

    def _post_load(self) -> None:
        self.type = _coerce_enum(MessageType, self.type, "MessageEnvelope.type")
        self.sender_type = _coerce_enum(SenderType, self.sender_type, "MessageEnvelope.sender_type")
        self.recipient_type = _coerce_enum(RecipientType, self.recipient_type, "MessageEnvelope.recipient_type")

    def validate(self) -> None:
        _require(bool(self.message_id), "MessageEnvelope.message_id is required")
        _require(bool(self.track_id), "MessageEnvelope.track_id is required")
        _require(isinstance(self.type, MessageType), "MessageEnvelope.type must be a MessageType")
        _require(isinstance(self.sender_type, SenderType), "MessageEnvelope.sender_type invalid")
        _require(isinstance(self.recipient_type, RecipientType), "MessageEnvelope.recipient_type invalid")


# --------------------------------------------------------------------------- #
# FileLock
# --------------------------------------------------------------------------- #
@dataclass
class FileLock(_Model):
    """One-writer-per-file claim. Projection lives in ``locks.json``."""

    path: str = ""
    worker_id: str = ""
    track_id: str = ""
    task_id: Optional[str] = None
    acquired_at: str = field(default_factory=utc_now_iso)
    schema_version: int = SCHEMA_VERSION

    def validate(self) -> None:
        _require(bool(self.path), "FileLock.path is required")
        _require(bool(self.worker_id), "FileLock.worker_id is required")


# --------------------------------------------------------------------------- #
# HeartbeatState
# --------------------------------------------------------------------------- #
@dataclass
class HeartbeatState(_Model):
    worker_id: str = ""
    track_id: str = ""
    task_id: Optional[str] = None
    status: HeartbeatStatus = HeartbeatStatus.UNKNOWN
    last_beat_at: str = field(default_factory=utc_now_iso)
    interval_seconds: int = 300
    note: Optional[str] = None
    schema_version: int = SCHEMA_VERSION

    def _post_load(self) -> None:
        self.status = _coerce_enum(HeartbeatStatus, self.status, "HeartbeatState.status")

    def validate(self) -> None:
        _require(bool(self.worker_id), "HeartbeatState.worker_id is required")
        _require(isinstance(self.status, HeartbeatStatus), "HeartbeatState.status invalid")
        _require(isinstance(self.interval_seconds, int) and self.interval_seconds > 0,
                 "HeartbeatState.interval_seconds must be positive")


# --------------------------------------------------------------------------- #
# ApprovalRequest
# --------------------------------------------------------------------------- #
@dataclass
class ApprovalRequest(_Model):
    approval_id: str = field(default_factory=lambda: new_id("appr"))
    track_id: str = ""
    task_id: Optional[str] = None
    kind: ApprovalKind = ApprovalKind.PLAN
    state: ApprovalState = ApprovalState.PENDING
    requested_by: str = ""
    decided_by: Optional[str] = None
    rationale: Optional[str] = None
    created_at: str = field(default_factory=utc_now_iso)
    decided_at: Optional[str] = None
    schema_version: int = SCHEMA_VERSION

    def _post_load(self) -> None:
        self.kind = _coerce_enum(ApprovalKind, self.kind, "ApprovalRequest.kind")
        self.state = _coerce_enum(ApprovalState, self.state, "ApprovalRequest.state")

    def validate(self) -> None:
        _require(bool(self.approval_id), "ApprovalRequest.approval_id is required")
        _require(bool(self.track_id), "ApprovalRequest.track_id is required")
        _require(isinstance(self.kind, ApprovalKind), "ApprovalRequest.kind invalid")
        _require(isinstance(self.state, ApprovalState), "ApprovalRequest.state invalid")


# --------------------------------------------------------------------------- #
# VerificationGate
# --------------------------------------------------------------------------- #
@dataclass
class VerificationGate(_Model):
    gate_id: str = field(default_factory=lambda: new_id("gate"))
    track_id: str = ""
    task_id: Optional[str] = None
    name: str = ""
    commands: List[str] = field(default_factory=list)
    status: VerificationStatus = VerificationStatus.PENDING
    evidence_level: EvidenceLevel = EvidenceLevel.UNVERIFIED
    evidence_refs: List[str] = field(default_factory=list)
    checks: List[Dict[str, Any]] = field(default_factory=list)
    verifier: Optional[str] = None
    reason: str = ""
    created_at: str = field(default_factory=utc_now_iso)
    updated_at: str = field(default_factory=utc_now_iso)
    schema_version: int = SCHEMA_VERSION

    def _post_load(self) -> None:
        self.status = _coerce_enum(VerificationStatus, self.status, "VerificationGate.status")
        self.evidence_level = _coerce_enum(EvidenceLevel, self.evidence_level, "VerificationGate.evidence_level")

    def validate(self) -> None:
        _require(bool(self.gate_id), "VerificationGate.gate_id is required")
        _require(bool(self.track_id), "VerificationGate.track_id is required")
        _require(isinstance(self.commands, list), "VerificationGate.commands must be a list")
        _require(isinstance(self.status, VerificationStatus), "VerificationGate.status invalid")
        _require(isinstance(self.evidence_level, EvidenceLevel), "VerificationGate.evidence_level invalid")


# --------------------------------------------------------------------------- #
# RouteDecision
# --------------------------------------------------------------------------- #
@dataclass
class RouteDecision(_Model):
    decision_id: str = field(default_factory=lambda: new_id("route"))
    track_id: str = ""
    task_id: str = ""
    chosen_lane: str = ""
    candidates: List[str] = field(default_factory=list)
    reason: str = ""
    task_type: Optional[str] = None
    risk: Optional[str] = None
    created_at: str = field(default_factory=utc_now_iso)
    schema_version: int = SCHEMA_VERSION

    def validate(self) -> None:
        _require(bool(self.decision_id), "RouteDecision.decision_id is required")
        _require(bool(self.track_id), "RouteDecision.track_id is required")
        _require(bool(self.chosen_lane), "RouteDecision.chosen_lane is required")


# --------------------------------------------------------------------------- #
# OperatorNotification
# --------------------------------------------------------------------------- #
@dataclass
class OperatorNotification(_Model):
    notification_id: str = field(default_factory=lambda: new_id("note"))
    track_id: str = ""
    task_id: Optional[str] = None
    severity: NotificationSeverity = NotificationSeverity.INFO
    title: str = ""
    body: str = ""
    artifact_refs: List[str] = field(default_factory=list)
    evidence_level: EvidenceLevel = EvidenceLevel.UNVERIFIED
    created_at: str = field(default_factory=utc_now_iso)
    schema_version: int = SCHEMA_VERSION

    def _post_load(self) -> None:
        self.severity = _coerce_enum(NotificationSeverity, self.severity, "OperatorNotification.severity")
        self.evidence_level = _coerce_enum(EvidenceLevel, self.evidence_level, "OperatorNotification.evidence_level")

    def validate(self) -> None:
        _require(bool(self.notification_id), "OperatorNotification.notification_id is required")
        _require(bool(self.title), "OperatorNotification.title is required")
        _require(isinstance(self.severity, NotificationSeverity), "OperatorNotification.severity invalid")


# --------------------------------------------------------------------------- #
# LaneRecord — the Phase 3 tmux lane projection (lanes/<escaped>.json)
# --------------------------------------------------------------------------- #
@dataclass
class LaneRecord(_Model):
    """Durable projection of a tmux lane's identity and last-known runtime state.

    Identity (``target``/``session``/``window``/``provider``) is stable; the
    ``last_*`` timestamps and ``state`` are refreshed on every interaction
    (status/capture/submit) so an operator can see lane health without attaching
    to tmux.
    """

    lane_id: str = field(default_factory=lambda: new_id("lane"))
    target: str = ""              # raw target, e.g. "Conductor:claude"
    session: str = ""             # session / project segment
    window: str = ""              # window / provider segment
    provider: Optional[str] = None
    model: Optional[str] = None   # model the provider CLI was launched with (if known)
    state: LaneState = LaneState.UNKNOWN
    current_task_id: Optional[str] = None
    tmux_available: bool = True
    last_line_count: int = 0
    last_transcript_ref: Optional[str] = None
    last_event: Optional[Dict[str, Any]] = None
    last_classified_at: Optional[str] = None
    last_capture_at: Optional[str] = None
    last_submit_at: Optional[str] = None
    last_heartbeat_at: Optional[str] = None
    created_at: str = field(default_factory=utc_now_iso)
    updated_at: str = field(default_factory=utc_now_iso)
    schema_version: int = SCHEMA_VERSION

    def _post_load(self) -> None:
        self.state = _coerce_enum(LaneState, self.state, "LaneRecord.state")

    def validate(self) -> None:
        _require(bool(self.lane_id), "LaneRecord.lane_id is required")
        _require(bool(self.target), "LaneRecord.target is required")
        _require(bool(self.session), "LaneRecord.session is required")
        _require(bool(self.window), "LaneRecord.window is required")
        _require(isinstance(self.state, LaneState), "LaneRecord.state must be a LaneState")


# --------------------------------------------------------------------------- #
# DispatchRecord — the Phase 4 per-task runtime projection (tasks/<id>/status.json)
# --------------------------------------------------------------------------- #
@dataclass
class DispatchRecord(_Model):
    """Per-task dispatch + runtime state projection.

    Bridges the Phase 2 plan task and the Phase 3 lane: it records where the task
    was routed, the worktree/workspace it owns, the artifact paths a worker needs,
    heartbeat timestamps, and a derived stale-risk. Persisted to
    ``tracks/<track>/tasks/<task_id>/status.json``.
    """

    task_id: str = ""
    track_id: str = ""
    title: str = ""
    kind: str = "general"
    task_state: TaskState = TaskState.PENDING
    dispatch_state: Optional[DispatchState] = None
    provider: Optional[str] = None
    lane_target: Optional[str] = None
    lane_state: Optional[LaneState] = None
    worktree_mode: WorktreeMode = WorktreeMode.NOT_GIT_REPO
    branch: Optional[str] = None
    workspace: Optional[str] = None
    worktree_path: Optional[str] = None
    task_artifact_ref: Optional[str] = None
    result_artifact_ref: Optional[str] = None
    route_ref: Optional[str] = None
    status_ref: Optional[str] = None
    access_task_ids: List[str] = field(default_factory=list)
    dependencies: List[str] = field(default_factory=list)
    method_id: str = "build"
    acceptance_criteria: List[str] = field(default_factory=list)
    definition_of_done_refs: List[str] = field(default_factory=list)
    # Prose expectations (worker guidance) vs. real executable commands.
    # verification_commands holds strictly executable strings the verifier runs.
    verification_requirements: List[str] = field(default_factory=list)
    verification_commands: List[str] = field(default_factory=list)
    autonomy_policy: str = "auto_ok"
    risk_class: str = "normal"
    stale_risk: StaleRisk = StaleRisk.NONE
    blocker: Optional[str] = None
    # Phase 5 verification / fix-loop fields.
    verification_status: Optional[VerificationStatus] = None
    verification_ref: Optional[str] = None
    verifier: Optional[str] = None
    verified_at: Optional[str] = None
    ready_for_merge: bool = False
    fix_attempts: int = 0
    max_fix_attempts: int = 3
    dispatched_at: Optional[str] = None
    heartbeat_at: Optional[str] = None
    last_followup_at: Optional[str] = None
    last_nudge_at: Optional[str] = None
    last_fix_at: Optional[str] = None
    created_at: str = field(default_factory=utc_now_iso)
    updated_at: str = field(default_factory=utc_now_iso)
    schema_version: int = SCHEMA_VERSION

    def _post_load(self) -> None:
        self.task_state = _coerce_enum(TaskState, self.task_state, "DispatchRecord.task_state")
        if self.dispatch_state is not None:
            self.dispatch_state = _coerce_enum(DispatchState, self.dispatch_state, "DispatchRecord.dispatch_state")
        if self.lane_state is not None:
            self.lane_state = _coerce_enum(LaneState, self.lane_state, "DispatchRecord.lane_state")
        if self.verification_status is not None:
            self.verification_status = _coerce_enum(VerificationStatus, self.verification_status, "DispatchRecord.verification_status")
        self.worktree_mode = _coerce_enum(WorktreeMode, self.worktree_mode, "DispatchRecord.worktree_mode")
        self.stale_risk = _coerce_enum(StaleRisk, self.stale_risk, "DispatchRecord.stale_risk")

    def validate(self) -> None:
        _require(bool(self.task_id), "DispatchRecord.task_id is required")
        _require(bool(self.track_id), "DispatchRecord.track_id is required")
        _require(isinstance(self.task_state, TaskState), "DispatchRecord.task_state invalid")
        _require(isinstance(self.worktree_mode, WorktreeMode), "DispatchRecord.worktree_mode invalid")
        _require(isinstance(self.method_id, str) and bool(self.method_id), "DispatchRecord.method_id must be non-empty")
        _require(isinstance(self.acceptance_criteria, list), "DispatchRecord.acceptance_criteria must be a list")
        _require(isinstance(self.definition_of_done_refs, list), "DispatchRecord.definition_of_done_refs must be a list")
        _require(isinstance(self.verification_commands, list), "DispatchRecord.verification_commands must be a list")
        _require(isinstance(self.autonomy_policy, str), "DispatchRecord.autonomy_policy must be a string")
        _require(isinstance(self.risk_class, str), "DispatchRecord.risk_class must be a string")
        _require(isinstance(self.stale_risk, StaleRisk), "DispatchRecord.stale_risk invalid")


# --------------------------------------------------------------------------- #
# TrackRecord — the Phase 2 aggregate persisted to metadata.json
# --------------------------------------------------------------------------- #
@dataclass
class TrackRecord(_Model):
    """Aggregate document for ``tracks/<id>/metadata.json``.

    Serializes the :class:`Track` fields *flat* at the top level (so the Phase 1
    ``read_track`` -> ``Track.from_dict`` path keeps working unchanged) and adds
    the Phase 2 plan view: ``plan_status``, the planned ``tasks`` DAG, recorded
    ``approvals``, and a bounded revision counter.
    """

    track: Track = field(default_factory=lambda: Track(goal="placeholder"))
    plan_status: PlanStatus = PlanStatus.NONE
    plan_revision: int = 0
    max_plan_revisions: int = 5
    tasks: List[Task] = field(default_factory=list)
    approvals: List[ApprovalRequest] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        data = self.track.to_dict()  # flat Track fields at top level
        data["plan_status"] = _enum_value(self.plan_status)
        data["plan_revision"] = self.plan_revision
        data["max_plan_revisions"] = self.max_plan_revisions
        data["tasks"] = [t.to_dict() for t in self.tasks]
        data["approvals"] = [a.to_dict() for a in self.approvals]
        return data

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> TrackRecord:
        if not isinstance(data, dict):
            raise SchemaError("TrackRecord.from_dict expects a dict")
        track = Track.from_dict(data)  # ignores the extra plan keys
        tasks = [Task.from_dict(t) for t in data.get("tasks", []) or []]
        approvals = [ApprovalRequest.from_dict(a) for a in data.get("approvals", []) or []]
        rec = cls(
            track=track,
            plan_status=_coerce_enum(PlanStatus, data.get("plan_status", "none"), "TrackRecord.plan_status"),
            plan_revision=int(data.get("plan_revision", 0)),
            max_plan_revisions=int(data.get("max_plan_revisions", 5)),
            tasks=tasks,
            approvals=approvals,
        )
        rec.validate()
        return rec

    def plan_approval(self) -> Optional[ApprovalRequest]:
        """Return the most recent PLAN-kind approval request, if any."""
        plan_approvals = [a for a in self.approvals if a.kind is ApprovalKind.PLAN]
        return plan_approvals[-1] if plan_approvals else None

    def is_plan_approved(self) -> bool:
        return self.plan_status is PlanStatus.APPROVED

    def merge_approval(self) -> Optional[ApprovalRequest]:
        """Return the most recent MERGE-kind approval request, if any."""
        merge_approvals = [a for a in self.approvals if a.kind is ApprovalKind.MERGE]
        return merge_approvals[-1] if merge_approvals else None

    def is_merge_approved(self) -> bool:
        appr = self.merge_approval()
        return appr is not None and appr.state is ApprovalState.APPROVED

    def validate(self) -> None:
        _require(isinstance(self.track, Track), "TrackRecord.track must be a Track")
        self.track.validate()
        _require(isinstance(self.plan_status, PlanStatus), "TrackRecord.plan_status invalid")
        _require(self.plan_revision >= 0, "TrackRecord.plan_revision must be >= 0")
        _require(self.max_plan_revisions >= 1, "TrackRecord.max_plan_revisions must be >= 1")
        for t in self.tasks:
            t.validate()
        for a in self.approvals:
            a.validate()


__all__ = [
    "SCHEMA_VERSION",
    "SchemaError",
    "utc_now_iso",
    "new_id",
    # enums
    "TrackState", "PlanStatus", "TaskState", "AttemptState", "LaneState",
    "DispatchState", "StaleRisk", "WorktreeMode",
    "MessageType", "SenderType", "RecipientType", "HeartbeatStatus",
    "ApprovalKind", "ApprovalState", "VerificationStatus", "EvidenceLevel",
    "NotificationSeverity",
    # models
    "AccessList", "Track", "Task", "TaskAttempt", "WorkerLane", "Endpoint",
    "MessageEnvelope", "FileLock", "HeartbeatState", "ApprovalRequest",
    "VerificationGate", "RouteDecision", "OperatorNotification", "TrackRecord",
    "LaneRecord", "DispatchRecord",
]
