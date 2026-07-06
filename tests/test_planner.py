"""Deterministic planner: DAG shape, dependencies, and access-list scoping."""

from conductor import planner
from conductor.models import TaskState


def test_build_tasks_is_deterministic_shape():
    a = planner.build_tasks("track_1", "Build a dashboard")
    b = planner.build_tasks("track_1", "Build a dashboard")
    assert [t.title for t in a] == [t.title for t in b]
    assert len(a) == 5


def test_first_task_ready_rest_pending():
    tasks = planner.build_tasks("track_1", "goal")
    assert tasks[0].state is TaskState.READY
    assert all(t.state is TaskState.PENDING for t in tasks[1:])


def test_dependencies_form_a_chain():
    tasks = planner.build_tasks("track_1", "goal")
    assert tasks[0].dependencies == []
    for prev, cur in zip(tasks, tasks[1:]):
        assert cur.dependencies == [prev.task_id]


def test_build_tasks_assigns_v2_method_metadata():
    tasks = planner.build_tasks("track_1", "goal")

    assert [t.method_id for t in tasks] == ["spec", "plan", "build", "test", "review"]
    assert all(t.definition_of_done_refs == ["definition_of_done.md"] for t in tasks)
    assert all(t.acceptance_criteria for t in tasks)
    # Prose expectations live in verification_requirements; verification_commands
    # is strictly for executable commands and starts empty (set via task set-verify).
    assert all(t.verification_requirements for t in tasks)
    assert all(t.verification_commands == [] for t in tasks)
    assert [t.autonomy_policy for t in tasks] == [
        "stop_on_ambiguity",
        "stop_on_ambiguity",
        "auto_ok",
        "auto_ok",
        "requires_operator",
    ]


def test_access_list_scopes_to_dependencies_only():
    tasks = planner.build_tasks("track_1", "goal")
    # First task sees no prior task; later tasks see exactly their dependency.
    assert tasks[0].access_list.task_ids == []
    assert tasks[1].access_list.task_ids == [tasks[0].task_id]
    # No task is granted broadcast visibility by default (Fugu principle).
    assert all(t.access_list.allow_broadcast is False for t in tasks)
    assert all("spec.md" in t.access_list.artifact_refs for t in tasks)


def test_render_spec_contains_sections():
    spec = planner.render_spec("track_1", "Build X", "2026-01-01T00:00:00+00:00")
    for heading in ["## Goal", "## Assumptions", "## Non-Goals",
                    "## Acceptance Criteria", "## Open Questions"]:
        assert heading in spec
    assert "Build X" in spec


def test_render_plan_lists_tasks_and_status():
    tasks = planner.build_tasks("track_1", "Build X")
    plan = planner.render_plan("track_1", "Build X", "2026-01-01T00:00:00+00:00",
                               tasks, "pending_review", 1)
    assert "## Task DAG" in plan
    assert "## Verification Criteria" in plan
    assert "plan_status: pending_review" in plan
    for t in tasks:
        assert t.task_id in plan
        assert f"- method: {t.method_id}" in plan


def test_render_definition_of_done_contains_conductor_v2_gates():
    dod = planner.render_definition_of_done("track_1", "Build X")

    assert "# Definition of Done" in dod
    assert "Result artifact is present and non-empty" in dod
    assert "Verification artifact exists and passed" in dod
    assert "No active `blocked_prompt` lanes" in dod


def test_build_tasks_full_task_workflow_mode_adds_per_task_contract():
    tasks = planner.build_tasks("track_1", "Build X", task_workflow_mode="full")

    assert len(tasks) == 5
    assert all("Per-task workflow contract" in t.description for t in tasks)
    assert all("Plan → Execute → Self-evaluate → Evidence → Handoff" in t.description for t in tasks)


def test_render_plan_declares_task_workflow_mode():
    tasks = planner.build_tasks("track_1", "Build X", task_workflow_mode="full")
    plan = planner.render_plan(
        "track_1",
        "Build X",
        "2026-01-01T00:00:00+00:00",
        tasks,
        "pending_review",
        1,
        task_workflow_mode="full",
    )

    assert "- task_workflow_mode: full" in plan
    assert "## Per-Task Workflow Contract" in plan
    assert "## Plan" in plan
    assert "## Self-Evaluation" in plan


def test_invalid_task_workflow_mode_rejected():
    import pytest

    with pytest.raises(ValueError, match="task_workflow_mode"):
        planner.build_tasks("track_1", "Build X", task_workflow_mode="unknown")
