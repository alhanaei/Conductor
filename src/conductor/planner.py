"""Deterministic goal -> plan scaffolding (Phase 2).

No model calls. A goal is decomposed into a fixed, dependency-ordered task
chain that demonstrates the DAG + access-list machinery later phases need. The
decomposition is intentionally generic and stable so the same goal always yields
the same plan shape — that makes the planner unit-testable and the artifacts
reviewable.

Per Fugu's access-list principle, each task's :class:`AccessList` grants
visibility only to its *dependency* outputs plus the shared ``spec.md`` — never a
global paste of every other task's context.
"""

from __future__ import annotations

from typing import Dict, List, Tuple

from .methods import get_method
from .models import AccessList, Task, TaskState

# (slug, title, description-suffix, dependency-slugs, method_id)
_TASK_TEMPLATE: List[Tuple[str, str, str, List[str], str]] = [
    ("clarify", "Clarify requirements and constraints",
     "Capture concrete requirements, assumptions, and open questions", [], "spec"),
    ("design", "Design approach, interfaces, and file surfaces",
     "Define the solution shape, key interfaces, and files/surfaces to touch", ["clarify"], "plan"),
    ("implement", "Implement the solution",
     "Build the change within the approved design and access scope", ["design"], "build"),
    ("test", "Add tests and verify behavior",
     "Add automated tests and verify acceptance criteria", ["implement"], "test"),
    ("review", "Review, document, and finalize",
     "Review the diff, update docs, and prepare for merge approval", ["test"], "review"),
]

TASK_WORKFLOW_MODES = {"stage", "full"}

_FULL_TASK_WORKFLOW_CONTRACT = (
    "\n\nPer-task workflow contract (full mode): "
    "Plan → Execute → Self-evaluate → Evidence → Handoff. "
    "The worker result.md must include sections named ## Plan, ## Actions Taken, "
    "## Evidence, ## Self-Evaluation, ## Open Risks, and ## Handoff."
)


def _validate_task_workflow_mode(task_workflow_mode: str) -> str:
    if task_workflow_mode not in TASK_WORKFLOW_MODES:
        valid = ", ".join(sorted(TASK_WORKFLOW_MODES))
        raise ValueError(f"task_workflow_mode must be one of: {valid}")
    return task_workflow_mode


def build_tasks(track_id: str, goal: str, task_workflow_mode: str = "stage") -> List[Task]:
    """Generate the deterministic task DAG for ``goal`` under ``track_id``.

    Returns tasks in topological order. The first task (no dependencies) is
    ``READY``; the rest are ``PENDING`` until their dependencies complete.
    """
    task_workflow_mode = _validate_task_workflow_mode(task_workflow_mode)
    slug_to_id: Dict[str, str] = {}
    ordered: List[Tuple[Task, List[str]]] = []

    # First pass: create tasks and record their generated ids per slug.
    for slug, title, desc_suffix, dep_slugs, method_id in _TASK_TEMPLATE:
        method = get_method(method_id)
        description = f"{desc_suffix} for goal: {goal}"
        if task_workflow_mode == "full":
            description += _FULL_TASK_WORKFLOW_CONTRACT
        task = Task(
            track_id=track_id,
            title=title,
            description=description,
            state=TaskState.READY if not dep_slugs else TaskState.PENDING,
            method_id=method.method_id,
            acceptance_criteria=list(method.acceptance_criteria),
            definition_of_done_refs=["definition_of_done.md"],
            # Prose expectations from the method catalog; real executable
            # commands are configured per task/track (see `task set-verify`).
            verification_requirements=list(method.verification_requirements),
            verification_commands=[],
            autonomy_policy=method.autonomy_policy,
            risk_class=method.risk_class,
        )
        slug_to_id[slug] = task.task_id
        ordered.append((task, dep_slugs))

    # Second pass: wire dependencies + access lists now that all ids exist.
    for task, dep_slugs in ordered:
        task.dependencies = [slug_to_id[d] for d in dep_slugs]
        task.access_list = AccessList(
            task_ids=list(task.dependencies),
            artifact_refs=["spec.md"],
            allow_broadcast=False,
        )

    return [task for task, _ in ordered]


def render_spec(track_id: str, goal: str, created_at: str) -> str:
    """Render a real ``spec.md`` with goal, assumptions, non-goals, and placeholders."""
    return f"""# Spec — {goal}

- track_id: {track_id}
- created_at: {created_at}
- phase: 2 (goal intake)
- status: pending plan approval

## Goal

{goal}

## Assumptions

- Deterministic plan scaffold (no model-assisted planning in Phase 2).
- Work executes inside an approved slice once the plan is approved (later phase).
- _Add concrete, goal-specific assumptions during review._

## Non-Goals

- No worker dispatch, tmux lanes, worktrees, or provider launchers in this phase.
- No Telegram/Hermes integration in this phase.
- _Add explicit out-of-scope items for this goal during review._

## Acceptance Criteria

- [ ] _Define measurable acceptance criteria during plan review (Phase 2 placeholder)._

## Open Questions

- _List unresolved questions that must be answered before dispatch (Phase 2 placeholder)._
"""


def render_plan(track_id: str, goal: str, created_at: str, tasks: List[Task],
                plan_status: str, plan_revision: int,
                task_workflow_mode: str = "stage") -> str:
    """Render a real ``plan.md`` describing the task DAG and approval status."""
    task_workflow_mode = _validate_task_workflow_mode(task_workflow_mode)
    lines: List[str] = [
        f"# Plan — {goal}",
        "",
        f"- track_id: {track_id}",
        f"- created_at: {created_at}",
        f"- plan_status: {plan_status}",
        f"- plan_revision: {plan_revision}",
        f"- task_workflow_mode: {task_workflow_mode}",
        "",
        "## Task DAG",
        "",
    ]

    if task_workflow_mode == "full":
        lines += [
            "## Per-Task Workflow Contract",
            "",
            "Every task keeps its normal DAG role, but each worker result must include:",
            "",
            "- `## Plan` — local task plan before execution",
            "- `## Actions Taken` — concrete work performed",
            "- `## Evidence` — commands, files, metrics, or artifact paths",
            "- `## Self-Evaluation` — worker-side evaluation against the task objective",
            "- `## Open Risks` — residual issues or blockers",
            "- `## Handoff` — what Conductor/downstream tasks should consume next",
            "",
        ]

    id_to_title = {t.task_id: t.title for t in tasks}
    for idx, task in enumerate(tasks, start=1):
        if task.dependencies:
            deps = ", ".join(f"{id_to_title.get(d, d)} (`{d}`)" for d in task.dependencies)
        else:
            deps = "_none_"
        access = ", ".join(task.access_list.task_ids) or "_none (spec.md only)_"
        lines += [
            f"### {idx}. {task.title}",
            "",
            f"- task_id: `{task.task_id}`",
            f"- state: {task.state.value}",
            f"- method: {task.method_id}",
            f"- autonomy_policy: {task.autonomy_policy}",
            f"- risk_class: {task.risk_class}",
            f"- depends_on: {deps}",
            f"- access_list.task_ids: {access}",
            f"- access_list.artifact_refs: {', '.join(task.access_list.artifact_refs)}",
            f"- definition_of_done_refs: {', '.join(task.definition_of_done_refs)}",
            f"- description: {task.description}",
            "",
            "Acceptance criteria:",
            *[f"- [ ] {item}" for item in task.acceptance_criteria],
            "",
            "Verification requirements:",
            *[f"- [ ] {item}" for item in task.verification_commands],
            "",
        ]

    lines += [
        "## Likely Files / Surfaces",
        "",
        "- _Identify the files, modules, and services this work will touch (placeholder)._",
        "",
        "## Verification Criteria",
        "",
        "- _Define the commands/checks that prove each task is complete (placeholder)._",
        "",
        "## Approval",
        "",
        f"- plan_status: **{plan_status}**",
        "- Plan approval is a separate, explicit gate (`conductor approve plan`).",
        "- No worker dispatch occurs before approval.",
        "",
    ]
    return "\n".join(lines)


def render_definition_of_done(track_id: str, goal: str) -> str:
    """Render the Conductor v2 standing Definition of Done artifact."""
    return f"""# Definition of Done — {goal}

- track_id: {track_id}
- scope: standing quality bar for every Conductor task in this track
- source: Conductor v2 method contract

## Correctness

- [ ] Task acceptance criteria are met.
- [ ] Result artifact is present and non-empty.
- [ ] Evidence listed in `result.md` is concrete and reproducible.
- [ ] Edge cases, errors, and blockers are recorded instead of hidden.

## Quality

- [ ] Work is scoped to the task and access list.
- [ ] No unrelated refactors or drive-by cleanup.
- [ ] Worker-written machine fields stay inside Conductor schema enums.

## Verification

- [ ] Verification artifact exists and passed.
- [ ] Verification evidence references the task result artifact.
- [ ] Missing results remain skipped in watch loops, not marked failed prematurely.

## Operator / Loop Safety

- [ ] No active `blocked_prompt` lanes.
- [ ] Operator summary does not recommend final merge/close while DAG tasks are unfinalized.
- [ ] Final merge/close gates are backed by Conductor verification, not worker claims.
"""


def render_quality_gates(track_id: str, goal: str) -> dict:
    """Machine-readable companion to ``definition_of_done.md``."""
    return {
        "track_id": track_id,
        "goal": goal,
        "schema": "conductor.v2.quality_gates",
        "required_checks": [
            "result_artifact_present",
            "definition_of_done_present",
            "verification_artifact_written",
            "no_active_blocked_prompt_lanes",
        ],
    }
