"""Conductor v2 method catalog.

The catalog turns broad lifecycle phases into deterministic task-level method
contracts. It intentionally stays data-only: no LLM calls, no harness-specific
plugin behavior, and no runtime prompt injection magic.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List


@dataclass(frozen=True)
class MethodContract:
    method_id: str
    description: str
    workflow: str
    acceptance_criteria: List[str] = field(default_factory=list)
    anti_rationalizations: List[str] = field(default_factory=list)
    verification_requirements: List[str] = field(default_factory=list)
    autonomy_policy: str = "auto_ok"
    risk_class: str = "normal"


_METHODS: Dict[str, MethodContract] = {
    "spec": MethodContract(
        method_id="spec",
        description="Clarify requirements, assumptions, non-goals, and open questions before execution.",
        workflow="Define scope → surface assumptions → identify blockers → hand off concrete requirements",
        acceptance_criteria=[
            "Requirements, assumptions, non-goals, and open questions are captured.",
            "Any ambiguity that blocks implementation is surfaced explicitly.",
        ],
        anti_rationalizations=[
            "Do not silently fill ambiguous requirements.",
            "Do not proceed to implementation decisions before scope is explicit.",
            "Do not claim clarity if open questions remain material to the next task.",
        ],
        verification_requirements=[
            "Result artifact lists requirements, assumptions, non-goals, and open questions.",
            "Handoff identifies what the plan/design task should consume next.",
        ],
        autonomy_policy="stop_on_ambiguity",
    ),
    "plan": MethodContract(
        method_id="plan",
        description="Design the implementation approach, interfaces, file surfaces, and verification strategy.",
        workflow="Map dependencies → define interfaces → list files/surfaces → define verification",
        acceptance_criteria=[
            "Implementation approach and affected surfaces are named.",
            "Verification strategy is specific enough for a worker to execute.",
        ],
        anti_rationalizations=[
            "Do not design by vibes; tie decisions to concrete files or interfaces.",
            "Do not hide risks that should stop autonomous execution.",
        ],
        verification_requirements=[
            "Result artifact includes design decisions, likely files, risks, and verification commands.",
        ],
        autonomy_policy="stop_on_ambiguity",
    ),
    "build": MethodContract(
        method_id="build",
        description="Implement one approved slice incrementally with evidence.",
        workflow="Implement smallest slice → run targeted checks → record evidence → hand off",
        acceptance_criteria=[
            "The approved implementation slice is complete and scoped.",
            "No unrelated files or behavior are changed.",
        ],
        anti_rationalizations=[
            "Do not implement the whole feature in one pass.",
            "Do not change files outside the task scope.",
            "Do not claim completion without command evidence.",
        ],
        verification_requirements=[
            "Targeted tests or checks for the changed behavior are run.",
            "Relevant regression/build/type checks are run when available.",
        ],
        autonomy_policy="auto_ok",
    ),
    "test": MethodContract(
        method_id="test",
        description="Prove behavior with automated tests and reproducible verification output.",
        workflow="Identify claims → add/adjust tests → run targeted suite → run regression suite",
        acceptance_criteria=[
            "Behavior is covered by tests or explicit verification artifacts.",
            "Regression risk is checked with the relevant suite.",
        ],
        anti_rationalizations=[
            "Do not use manual inspection as the only proof when automated checks are feasible.",
            "Do not skip edge cases because the happy path passes.",
        ],
        verification_requirements=[
            "Result artifact includes exact commands and observed outputs.",
        ],
        autonomy_policy="auto_ok",
    ),
    "review": MethodContract(
        method_id="review",
        description="Review quality, documentation, risks, and readiness for final operator decision.",
        workflow="Review diff/artifacts → classify blockers → update docs → produce final handoff",
        acceptance_criteria=[
            "Blockers, risks, and documentation needs are identified.",
            "Final handoff is ready for Conductor/operator merge decision.",
        ],
        anti_rationalizations=[
            "Do not rubber-stamp worker output as complete.",
            "Do not recommend final merge if planned DAG tasks remain unfinalized.",
        ],
        verification_requirements=[
            "Result artifact includes review verdict, blockers, risks, and final handoff.",
        ],
        autonomy_policy="requires_operator",
        risk_class="review_gate",
    ),
    "ship": MethodContract(
        method_id="ship",
        description="Prepare release/close readiness with rollback and monitoring evidence.",
        workflow="Check gates → summarize risks → define rollback → hand off launch decision",
        acceptance_criteria=[
            "Release readiness, rollback path, and monitoring needs are documented.",
        ],
        anti_rationalizations=[
            "Do not declare GO without rollback criteria.",
            "Do not ignore security, observability, or migration implications.",
        ],
        verification_requirements=[
            "Final summary includes go/no-go, rollback, and evidence references.",
        ],
        autonomy_policy="requires_operator",
        risk_class="release_gate",
    ),
}


DEFAULT_METHOD_ID = "build"


def get_method(method_id: str) -> MethodContract:
    return _METHODS.get(method_id, _METHODS[DEFAULT_METHOD_ID])


def method_ids() -> List[str]:
    return list(_METHODS)
