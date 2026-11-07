"""Regression tests for the `linked-task` checker embedded in `.github/workflows/pr-policy.yml`.

The checker is the Python script in the workflow's single `run: |` step. These tests read that
exact text out of the workflow file and execute it with `subprocess.run` replaced by an
in-memory GitHub double, so the policy under test is the one CI runs, not a copy. Nothing here
touches the network, a credential or a real label.

Run from the repository root:  python3 -m unittest discover -s tests -p 'test_*.py'
"""

import contextlib
import io
import json
import os
import pathlib
import re
import subprocess
import textwrap
import unittest
from unittest import mock

ROOT = pathlib.Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github" / "workflows" / "pr-policy.yml"

HEAD = "a" * 40
STALE = "b" * 40

DEFAULT_ENV = {
    "GITHUB_REPOSITORY": "owner/repo",
    "PR_NUMBER": "7",
    "PRIORITY_LABELS": "P0,P1,P2,P3",
    "BLOCKED_LABEL": "blocked:owner",
    "CATEGORY_PREFIX": "kind:",
    "TRACKING_LABEL": "kind:tracking",
    "READY_LABEL": "status:ready",
    "RECORD_PATHS": "docs/adr/,.conductor/HANDOFF.md",
    "APPROVAL_MODE": "manual",
    "INTEGRATION_BRANCH": "main",
    "DEFAULT_BRANCH": "main",
    "BASE_REF": "main",
    "HEAD_REF": "claude/feature",
    "REVIEW_REQUIRED_LABEL": "review:required",
    "HEAD_SHA": HEAD,
}


def embedded_script():
    """Return the dedented Python source of the workflow's `run: |` step."""
    lines = WORKFLOW.read_text(encoding="utf-8").splitlines()
    for index, line in enumerate(lines):
        if line.strip() == "shell: python" and lines[index + 1].strip() == "run: |":
            indent = len(lines[index + 1]) - len(lines[index + 1].lstrip())
            body = []
            for next_line in lines[index + 2:]:
                if next_line.strip() and (len(next_line) - len(next_line.lstrip())) <= indent:
                    break
                body.append(next_line)
            return textwrap.dedent("\n".join(body)) + "\n"
    raise AssertionError("no `shell: python` step with a `run: |` block in pr-policy.yml")


class ApiError(Exception):
    """A `gh api` failure: exit code plus what gh writes to stderr and stdout."""

    def __init__(self, returncode, stderr, stdout=""):
        super().__init__(stderr)
        self.returncode, self.stderr, self.stdout = returncode, stderr, stdout


NO_PARENT = ApiError(1, "gh: Not Found (HTTP 404)\n", '{"message":"Not Found","status":"404"}\n')


class FakeGitHub:
    """Stands in for `subprocess.run` and answers the `gh` calls the checker makes."""

    def __init__(self, body="Closes #42", files=("src/app.py",), issues=None, parents=None):
        self.body = body
        self.files = list(files)
        # issue number -> (labels, state)
        self.issues = dict(issues or {42: (["P2", "kind:chore", "status:ready"], "OPEN")})
        # issue number -> parent number, or an ApiError for the parent lookup; absent means 404
        self.parents = dict(parents or {})
        self.calls = []

    def __call__(self, args, check=False, capture_output=False, text=False, **kwargs):
        self.calls.append(list(args))
        assert args[0] == "gh", f"only gh is faked, got {args!r}"
        assert capture_output and text, "the checker must capture gh output as text"
        try:
            stdout = self._dispatch(args[1:])
        except ApiError as error:
            if check:
                raise subprocess.CalledProcessError(error.returncode, args, error.stdout, error.stderr)
            return subprocess.CompletedProcess(args, error.returncode, error.stdout, error.stderr)
        return subprocess.CompletedProcess(args, 0, stdout, "")

    def _dispatch(self, args):
        if args[:2] == ["pr", "view"]:
            assert args[2] == DEFAULT_ENV["PR_NUMBER"] and args[3:5] == ["--repo", "owner/repo"]
            fields = args[args.index("--json") + 1]
            if fields == "body":
                return json.dumps({"body": self.body})
            if fields == "files":
                return json.dumps({"files": [{"path": path} for path in self.files]})
        if args[:2] == ["issue", "view"]:
            number = int(args[2])
            assert args[3:5] == ["--repo", "owner/repo"] and args[args.index("--json") + 1] == "labels,state"
            if number not in self.issues:
                raise ApiError(1, "GraphQL: Could not resolve to an issue or pull request (HTTP 404)\n")
            labels, state = self.issues[number]
            return json.dumps({"labels": [{"name": name} for name in labels], "state": state})
        match = re.fullmatch(r"repos/owner/repo/issues/(\d+)/parent", args[1]) if args[0] == "api" else None
        if match:
            parent = self.parents.get(int(match.group(1)), NO_PARENT)
            if isinstance(parent, ApiError):
                raise parent
            return json.dumps({"number": parent, "state": "open"})
        raise AssertionError(f"unexpected gh call: {args!r}")


def run_policy(fake, **env):
    """Execute the embedded checker against `fake`; return (exit code, printed output)."""
    environment = {**DEFAULT_ENV, **env}
    output = io.StringIO()
    with mock.patch.dict(os.environ, environment, clear=False), mock.patch.object(subprocess, "run", fake), \
            contextlib.redirect_stdout(output):
        try:
            exec(compile(embedded_script(), str(WORKFLOW), "exec"), {"__name__": "pr_policy"})
        except SystemExit as stop:
            code = stop.code
        else:
            raise AssertionError("the checker must end with sys.exit")
    return (0 if code is None else int(code)), output.getvalue()


def ready(*extra, priority="P2", category="kind:chore"):
    return [label for label in (priority, category, "status:ready", *extra) if label]


class PolicyTest(unittest.TestCase):
    def assertRejected(self, fake, message, **env):
        code, output = run_policy(fake, **env)
        self.assertEqual(code, 1, output)
        self.assertIn("::error::", output)
        self.assertIn(message, output)
        return output

    def assertAccepted(self, fake, **env):
        code, output = run_policy(fake, **env)
        self.assertEqual(code, 0, output)
        self.assertNotIn("::error::", output)
        return output


class ClosingTaskTests(PolicyTest):
    def test_valid_open_ready_task_is_accepted(self):
        output = self.assertAccepted(FakeGitHub())
        self.assertIn("Task #42 is ready", output)

    def test_repeated_references_to_the_same_task_count_once(self):
        self.assertAccepted(FakeGitHub(body="Closes #42\n\nFixes #42, resolves #42."))

    def test_missing_task_link_is_rejected(self):
        self.assertRejected(FakeGitHub(body="No task here."), "must name the task it closes")

    def test_two_distinct_closing_tasks_are_rejected(self):
        fake = FakeGitHub(body="Closes #42 and closes #43", issues={42: (ready(), "OPEN"), 43: (ready(), "OPEN")})
        self.assertRejected(fake, "exactly one task")

    def test_missing_ready_label_is_rejected(self):
        self.assertRejected(FakeGitHub(issues={42: (["P2", "kind:chore"], "OPEN")}), "missing the 'status:ready' label")

    def test_closed_task_is_rejected(self):
        self.assertRejected(FakeGitHub(issues={42: (ready(), "CLOSED")}), "closed")

    def test_owner_blocked_task_cannot_be_closed_by_a_pull_request(self):
        self.assertRejected(FakeGitHub(issues={42: (["blocked:owner", "kind:chore", "status:ready"], "OPEN")}), "blocked:owner")

    def test_tracking_record_cannot_be_closed_by_a_pull_request(self):
        self.assertRejected(FakeGitHub(issues={42: (["kind:tracking", "status:ready"], "OPEN")}), "kind:tracking")

    def test_missing_priority_is_rejected(self):
        self.assertRejected(FakeGitHub(issues={42: (["kind:chore", "status:ready"], "OPEN")}), "no priority label")

    def test_two_priorities_are_rejected(self):
        self.assertRejected(FakeGitHub(issues={42: (ready("P1"), "OPEN")}), "more than one priority label")

    def test_missing_category_is_rejected(self):
        self.assertRejected(FakeGitHub(issues={42: (["P2", "status:ready"], "OPEN")}), "expected exactly one 'kind:' label, found 0")

    def test_two_categories_are_rejected(self):
        self.assertRejected(FakeGitHub(issues={42: (ready("kind:docs"), "OPEN")}), "expected exactly one 'kind:' label, found 2")

    def test_custom_label_names_are_honoured(self):
        custom = dict(PRIORITY_LABELS="prio/high,prio/low", BLOCKED_LABEL="waiting", CATEGORY_PREFIX="type/",
                      TRACKING_LABEL="type/epic", READY_LABEL="go")
        self.assertAccepted(FakeGitHub(issues={42: (["prio/low", "type/docs", "go"], "OPEN")}), **custom)
        output = self.assertRejected(FakeGitHub(), "missing the 'go' label", **custom)
        self.assertIn("expected exactly one 'type/' label, found 0", output)
        self.assertRejected(FakeGitHub(issues={42: (["prio/low", "type/epic", "go"], "OPEN")}), "type/epic", **custom)

    def test_invalid_approval_mode_is_rejected(self):
        self.assertRejected(FakeGitHub(), "CONDUCTOR_APPROVAL_MODE must be 'manual' or 'auto'", APPROVAL_MODE="later")


class ApprovalModeTests(PolicyTest):
    def test_manual_mode_accepts_any_base(self):
        self.assertAccepted(FakeGitHub(), APPROVAL_MODE="manual", INTEGRATION_BRANCH="dev", BASE_REF="main")

    def test_auto_mode_rejects_a_wrong_integration_target(self):
        self.assertRejected(FakeGitHub(), "target the integration branch 'dev'", APPROVAL_MODE="auto",
                            INTEGRATION_BRANCH="dev", BASE_REF="main")

    def test_auto_mode_accepts_the_integration_branch(self):
        output = self.assertAccepted(FakeGitHub(), APPROVAL_MODE="auto", INTEGRATION_BRANCH="dev", BASE_REF="dev")
        self.assertIn("base 'dev' accepted", output)

    def test_auto_mode_accepts_the_promotion_into_the_default_branch(self):
        output = self.assertAccepted(FakeGitHub(), APPROVAL_MODE="auto", INTEGRATION_BRANCH="dev",
                                     BASE_REF="main", HEAD_REF="dev", DEFAULT_BRANCH="main")
        self.assertIn("(promotion)", output)


class ParentTests(PolicyTest):
    def _with_parent(self, parent_labels, parent_state="OPEN"):
        return FakeGitHub(issues={42: (ready(), "OPEN"), 7: (parent_labels, parent_state)}, parents={42: 7})

    def test_confirmed_no_parent_response_is_accepted(self):
        fake = FakeGitHub(parents={42: NO_PARENT})
        output = self.assertAccepted(fake)
        self.assertNotIn("Parent", output)
        self.assertIn(["gh", "api", "repos/owner/repo/issues/42/parent"], fake.calls)

    def test_open_readied_parent_is_accepted_in_auto(self):
        output = self.assertAccepted(self._with_parent(["P1", "kind:feature", "status:ready"]), APPROVAL_MODE="auto")
        self.assertIn("Parent #7 of task #42 is open", output)

    def test_tracking_parent_without_priority_is_accepted(self):
        self.assertAccepted(self._with_parent(["kind:tracking", "status:ready"]), APPROVAL_MODE="auto")

    def test_closed_parent_is_rejected(self):
        self.assertRejected(self._with_parent(["P1", "kind:feature", "status:ready"], "CLOSED"), "parent is closed")

    def test_unready_parent_is_rejected_in_auto_but_not_in_manual(self):
        self.assertRejected(self._with_parent(["P1", "kind:feature"]), "inherits readiness only from a readied parent",
                            APPROVAL_MODE="auto")
        self.assertAccepted(self._with_parent(["P1", "kind:feature"]), APPROVAL_MODE="manual")

    def test_parent_with_two_categories_is_rejected(self):
        self.assertRejected(self._with_parent(["P1", "kind:feature", "kind:docs", "status:ready"]),
                            "Parent #7 of task #42 is not a workable record")

    def test_parent_permission_failure_fails_the_check(self):
        fake = FakeGitHub(parents={42: ApiError(1, "gh: Resource not accessible by integration (HTTP 403)\n")})
        output = self.assertRejected(fake, "Could not read the parent of task #42")
        self.assertIn("HTTP 403", output)

    def test_parent_server_failure_fails_the_check(self):
        fake = FakeGitHub(parents={42: ApiError(1, "gh: Server Error (HTTP 502)\n")})
        self.assertRejected(fake, "Could not read the parent of task #42")

    def test_parent_transport_failure_fails_the_check(self):
        fake = FakeGitHub(parents={42: ApiError(4, "error connecting to api.github.com\n")})
        self.assertRejected(fake, "Could not read the parent of task #42")


class ReviewRequiredTests(PolicyTest):
    def _labelled(self, body):
        return FakeGitHub(body=body, issues={42: (ready("review:required"), "OPEN")})

    def test_missing_review_line_is_rejected(self):
        self.assertRejected(self._labelled("Closes #42\n\n## Review\n\n- Reviewer: <runtime or login>, reviewed SHA: <40-hex>\n"),
                            "records no review of its head")

    def test_review_line_naming_the_head_is_accepted(self):
        output = self.assertAccepted(self._labelled(f"Closes #42\n\n## Review\n\n- Reviewer: Codex, reviewed SHA: {HEAD}\n"))
        self.assertIn(f"Review of head {HEAD} recorded by Codex", output)

    def test_review_line_naming_a_stale_sha_is_rejected(self):
        self.assertRejected(self._labelled(f"Closes #42\n\n## Review\n\n- Reviewer: Codex, reviewed SHA: {STALE}\n"),
                            f"names SHA {STALE}, not the head {HEAD}")

    def test_unlabelled_task_needs_no_review_line(self):
        self.assertAccepted(FakeGitHub(body="Closes #42\n\n## Review\n\n- Reviewer: <runtime or login>, reviewed SHA: <40-hex>\n"))


class RecordOnlyReferenceTests(PolicyTest):
    def test_record_only_files_may_reference_the_task(self):
        fake = FakeGitHub(body="Refs #42", files=["docs/adr/0008-example.md", ".conductor/HANDOFF.md"])
        output = self.assertAccepted(fake)
        self.assertIn("Record-only pull request", output)

    def test_reference_with_a_non_record_file_is_rejected(self):
        self.assertRejected(FakeGitHub(body="Refs #42", files=["docs/adr/0008-example.md", "AGENTS.md"]),
                            "must name the task it closes")

    def test_reference_without_a_task_number_is_rejected(self):
        self.assertRejected(FakeGitHub(body="Record only.", files=["docs/adr/0008-example.md"]), "must name the task it closes")

    def test_reference_to_two_distinct_records_is_rejected(self):
        fake = FakeGitHub(body="Refs #42, refs #43", files=["docs/adr/0008-example.md"],
                          issues={42: (ready(), "OPEN"), 43: (ready(), "OPEN")})
        self.assertRejected(fake, "exactly one task")

    def test_referenced_tracking_record_stays_accepted(self):
        fake = FakeGitHub(body="Refs #42", files=["docs/adr/0008-example.md"], issues={42: (["kind:tracking"], "OPEN")})
        self.assertAccepted(fake)

    def test_referenced_record_still_needs_ready_and_labels(self):
        fake = FakeGitHub(body="Refs #42", files=["docs/adr/0008-example.md"], issues={42: (["P2", "kind:chore"], "OPEN")})
        self.assertRejected(fake, "missing the 'status:ready' label")

    def test_closing_keyword_wins_over_a_reference(self):
        fake = FakeGitHub(body="Closes #42, refs #43", files=["docs/adr/0008-example.md"])
        output = self.assertAccepted(fake)
        self.assertNotIn("Record-only", output)


if __name__ == "__main__":
    unittest.main()
