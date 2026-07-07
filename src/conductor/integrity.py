"""Deterministic integrity gates for verification (diff scope, test integrity,
review verdicts).

These are pure functions over (changed files, task metadata, config) so they
can be unit-tested without git or a filesystem. Each returns a check dict in
the same shape the verification gate already uses:
``{name, passed, detail, ...evidence}``.

Skip semantics matter: when the diff cannot be computed (non-git workspace,
missing baseline) the gates return ``passed=True`` with an explicit
"skipped" detail — a gate that cannot measure must say so loudly rather than
fail work it has no evidence against.
"""

from __future__ import annotations

import fnmatch
import json
from pathlib import Path
from typing import Any, Dict, List, Optional

# Paths always exempt from scope enforcement: conductor's own artifacts are
# written by workers as part of the protocol (result.md, heartbeats, ...).
_ALWAYS_ALLOWED_PREFIXES = (".conductor/", ".hermes/")

# Default patterns identifying test files. Overridable via conductor.json
# {"test_file_patterns": [...]} (fnmatch globs against repo-relative paths).
DEFAULT_TEST_FILE_PATTERNS = [
    "tests/*", "tests/**", "test/*", "test/**",
    "test_*", "*/test_*", "**/test_*",
    "*_test.*", "**/*_test.*",
    "*.test.*", "**/*.test.*",
    "*.spec.*", "**/*.spec.*",
]

VALID_VERDICTS = ("approve", "reject")


def _matches_any(path: str, patterns: List[str]) -> bool:
    return any(fnmatch.fnmatch(path, p) for p in patterns)


def filter_enforceable(changed: List[str]) -> List[str]:
    """Drop conductor/hermes artifact paths — they are protocol writes."""
    return [f for f in changed
            if not f.startswith(_ALWAYS_ALLOWED_PREFIXES)]


# --------------------------------------------------------------------------- #
# Gate 1: diff scope
# --------------------------------------------------------------------------- #
def check_diff_scope(changed: Optional[List[str]], scope_paths: List[str],
                     prior_scopes: Optional[List[str]] = None) -> Dict[str, Any]:
    """Changed files must match the task's declared scope globs.

    - ``changed is None`` → diff unavailable → skip (pass, explicit note).
    - empty ``scope_paths`` → scope not declared → informational pass that
      still *reports* the changed files as evidence.
    - otherwise → fail listing every out-of-scope file.

    ``prior_scopes`` are the declared scopes of *already completed* tasks in
    the same track. Sequential tasks share the workspace and the same diff
    baseline, so a predecessor's legitimate, verified changes still appear in
    this task's diff (field-observed: a test task failed diff_scope because
    the build task's src/ change was uncommitted). Files matching a prior
    completed scope are attributed to that work, not this task's.
    """
    base = {"name": "diff_scope"}
    if changed is None:
        return {**base, "passed": True,
                "detail": "skipped: workspace is not a git repo or baseline unknown",
                "changed_files": []}
    enforceable = filter_enforceable(changed)
    if not scope_paths:
        return {**base, "passed": True,
                "detail": (f"no scope declared; {len(enforceable)} changed file(s) "
                           "reported as evidence (set 'conductor task set-scope' to enforce)"),
                "changed_files": enforceable}
    prior = prior_scopes or []
    attributed = [f for f in enforceable
                  if not _matches_any(f, scope_paths) and _matches_any(f, prior)]
    out_of_scope = [f for f in enforceable
                    if not _matches_any(f, scope_paths) and not _matches_any(f, prior)]
    if out_of_scope:
        return {**base, "passed": False,
                "detail": (f"{len(out_of_scope)} file(s) changed outside the task scope: "
                           + ", ".join(out_of_scope[:20])),
                "changed_files": enforceable, "out_of_scope": out_of_scope,
                "attributed_to_prior_tasks": attributed,
                "scope_paths": scope_paths}
    detail = f"all {len(enforceable)} changed file(s) within declared scope"
    if attributed:
        detail += (f" ({len(attributed)} attributed to prior completed tasks: "
                   + ", ".join(attributed[:10]) + ")")
    return {**base, "passed": True, "detail": detail,
            "changed_files": enforceable,
            "attributed_to_prior_tasks": attributed,
            "scope_paths": scope_paths}


# --------------------------------------------------------------------------- #
# Gate 2: test integrity
# --------------------------------------------------------------------------- #
def check_test_integrity(changed: Optional[List[str]], scope_paths: List[str],
                         method_id: str,
                         config: Optional[Dict[str, Any]] = None,
                         prior_scopes: Optional[List[str]] = None) -> Dict[str, Any]:
    """Non-test tasks must not modify test files (unless scope grants it).

    Closes the "worker weakened the tests so pytest passes" hole: a ``build``
    task that edits ``tests/...`` fails verification unless its declared scope
    explicitly includes those paths. ``test``-method tasks are exempt — editing
    tests is their job.
    """
    base = {"name": "test_integrity"}
    if changed is None:
        return {**base, "passed": True,
                "detail": "skipped: workspace is not a git repo or baseline unknown"}
    if method_id == "test":
        return {**base, "passed": True,
                "detail": "test-method task; test files are in scope by definition"}

    patterns = (config or {}).get("test_file_patterns") or DEFAULT_TEST_FILE_PATTERNS
    enforceable = filter_enforceable(changed)
    touched_tests = [f for f in enforceable if _matches_any(f, patterns)]
    # Scope can explicitly grant test files to a non-test task; files within a
    # prior completed task's scope are that task's work (shared workspace).
    prior = prior_scopes or []
    unauthorized = [f for f in touched_tests
                    if not (scope_paths and _matches_any(f, scope_paths))
                    and not _matches_any(f, prior)]
    if unauthorized:
        return {**base, "passed": False,
                "detail": (f"non-test task (method={method_id}) modified test file(s) "
                           "outside its declared scope: " + ", ".join(unauthorized[:20])),
                "test_files_modified": unauthorized}
    return {**base, "passed": True,
            "detail": ("no test files modified" if not touched_tests
                       else f"{len(touched_tests)} test file(s) modified within declared scope")}


# --------------------------------------------------------------------------- #
# Gate 3: review verdict
# --------------------------------------------------------------------------- #
def read_verdict(path: Path) -> Dict[str, Any]:
    """Parse a review task's ``verdict.json``.

    Returns ``{present, valid, verdict, blockers, notes, error}``. A verdict is
    valid only when ``verdict`` is exactly ``approve`` or ``reject``.
    """
    path = Path(path)
    if not path.exists():
        return {"present": False, "valid": False, "verdict": None,
                "blockers": [], "notes": None, "error": "verdict.json missing"}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as exc:
        return {"present": True, "valid": False, "verdict": None,
                "blockers": [], "notes": None, "error": f"unparseable verdict.json: {exc}"}
    verdict = data.get("verdict")
    if verdict not in VALID_VERDICTS:
        return {"present": True, "valid": False, "verdict": verdict,
                "blockers": [], "notes": None,
                "error": f"verdict must be one of {VALID_VERDICTS}, got {verdict!r}"}
    blockers = data.get("blockers") or []
    if not isinstance(blockers, list):
        blockers = [str(blockers)]
    return {"present": True, "valid": True, "verdict": verdict,
            "blockers": [str(b) for b in blockers],
            "notes": data.get("notes"), "error": None}


def check_review_verdict(verdict_path: Path) -> Dict[str, Any]:
    """Verification check for review-method tasks: a *valid* verdict must exist.

    Note the split of responsibilities: verification passes on either verdict
    value (the reviewer did its job whether it approved or rejected); the
    *merge gate* is where ``reject`` blocks.
    """
    v = read_verdict(verdict_path)
    if not v["valid"]:
        return {"name": "review_verdict", "passed": False,
                "detail": f"review task must write a valid verdict.json: {v['error']}",
                "verdict": v["verdict"]}
    return {"name": "review_verdict", "passed": True,
            "detail": f"verdict recorded: {v['verdict']}"
                      + (f" ({len(v['blockers'])} blocker(s))" if v["blockers"] else ""),
            "verdict": v["verdict"], "blockers": v["blockers"]}
