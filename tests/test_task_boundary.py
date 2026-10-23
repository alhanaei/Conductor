"""Tests for the task boundary helper (shared/skills/task-start/scripts/task_boundary.py).

Run with ``python3 -m unittest discover -s tests -v``. Every test runs in a disposable Git
repository and reads the task record from a JSON file, so no network or GitHub access is
touched. Covered: the status:ready refusal, the claim file and its allowed paths, the
evidence SHA check and the stopped finish.
"""

from __future__ import annotations

import contextlib
import importlib.util
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


REPO = Path(__file__).resolve().parents[1]
HELPER = REPO / "shared/skills/task-start/scripts/task_boundary.py"
SPEC = importlib.util.spec_from_file_location("task_boundary_under_test", HELPER)
assert SPEC is not None and SPEC.loader is not None
boundary = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = boundary
SPEC.loader.exec_module(boundary)

RECORD_BODY = """### Problem

Something.

### Allowed paths, services and actions

- `shared/skills/`, `tests/` and `MANIFEST.json`.
- Test comments on one readied test task. One branch, one PR, `Closes` this record.

### Stop conditions

Pause for the owner.
"""


def git(cwd: Path, *args: str) -> str:
    return subprocess.run(["git", *args], cwd=cwd, check=True, capture_output=True, text=True).stdout.strip()


class TaskBoundaryTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="conductor-boundary-")
        self.root = Path(self.temp.name)
        git(self.root, "init", "-q", "-b", "main")
        git(self.root, "config", "user.email", "test@example.invalid")
        git(self.root, "config", "user.name", "Test")
        (self.root / "README.md").write_text("hello\n")
        git(self.root, "add", "README.md")
        git(self.root, "commit", "-qm", "init")
        self.previous_cwd = os.getcwd()
        os.chdir(self.root)
        self.env = {key: value for key, value in os.environ.items()
                    if key not in ("GITHUB_TOKEN", "GH_TOKEN")}
        os.environ.pop("GITHUB_TOKEN", None)
        os.environ.pop("GH_TOKEN", None)

    def tearDown(self):
        os.chdir(self.previous_cwd)
        self.temp.cleanup()

    def record(self, number=46, labels=("kind:feature", "P1", "status:ready"), state="open"):
        path = self.root.parent / f"record-{number}-{os.getpid()}.json"
        path.write_text(json.dumps({"number": number, "title": "Boundary skills: start and finish",
                                    "body": RECORD_BODY, "state": state,
                                    "labels": [{"name": name} for name in labels],
                                    "html_url": f"https://example.invalid/issues/{number}"}))
        self.addCleanup(path.unlink)
        return str(path)

    def run_helper(self, *argv: str):
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            code = boundary.main(list(argv))
        return code, out.getvalue(), err.getvalue()

    def start(self, **kwargs):
        record = self.record(**kwargs)
        return self.run_helper("start", "46", "--role", "Implementer", "--runtime", "unit test",
                               "--reference", "test-ref", "--record", record, "--no-fetch")

    def local(self, name: str) -> Path:
        return self.root / ".git" / "conductor-local" / name

    def test_start_refuses_a_task_without_status_ready(self):
        code, _, err = self.start(labels=("kind:feature", "P1"))
        self.assertEqual(code, 2)
        self.assertIn("status:ready", err)
        self.assertFalse(self.local("claim.json").exists())
        self.assertEqual(git(self.root, "rev-parse", "--abbrev-ref", "HEAD"), "main")

    def test_start_refuses_a_closed_task(self):
        code, _, err = self.start(state="closed")
        self.assertEqual(code, 2)
        self.assertIn("closed", err)

    def test_start_writes_the_claim_with_allowed_paths_and_branches(self):
        code, out, _ = self.start()
        self.assertEqual(code, 0)
        claim = json.loads(self.local("claim.json").read_text())
        self.assertEqual(claim["task"], 46)
        self.assertEqual(claim["role"], "Implementer")
        self.assertEqual(claim["allowed_paths"], ["shared/skills/", "tests/", "MANIFEST.json"])
        self.assertEqual(claim["base"], "main")
        self.assertEqual(claim["base_sha"], git(self.root, "rev-parse", "main"))
        self.assertRegex(claim["branch"], r"^claude/boundary-skills-start-and-finish-\d{8}$")
        self.assertEqual(git(self.root, "rev-parse", "--abbrev-ref", "HEAD"), claim["branch"])
        self.assertEqual(len(claim["lines"]), 3)
        self.assertIn("Allowed paths: shared/skills/, tests/, MANIFEST.json", out)
        self.assertIn("never merge", out)
        comment = self.local("claim-comment.md").read_text()
        self.assertIn("**Claim.** Task #46", comment)
        self.assertIn("unit test", comment)

    def test_start_keeps_an_assigned_branch_and_refuses_a_second_task(self):
        git(self.root, "checkout", "-qb", "claude/assigned")
        record = self.record()
        code, _, _ = self.run_helper("start", "46", "--role", "Implementer", "--runtime", "t",
                                     "--reference", "r", "--record", record, "--no-fetch",
                                     "--branch", "claude/assigned")
        self.assertEqual(code, 0)
        self.assertEqual(git(self.root, "rev-parse", "--abbrev-ref", "HEAD"), "claude/assigned")
        other = self.record(number=47)
        code, _, err = self.run_helper("start", "47", "--role", "Implementer", "--runtime", "t",
                                       "--reference", "r", "--record", other, "--no-fetch")
        self.assertEqual(code, 3)
        self.assertIn("claim conflict", err)

    def test_start_refuses_when_no_record_access_exists(self):
        code, _, err = self.run_helper("start", "46", "--role", "Implementer", "--runtime", "t",
                                       "--reference", "r", "--no-fetch")
        self.assertEqual(code, 2)
        self.assertIn("--record", err)

    def test_finish_writes_evidence_for_the_exact_head_and_the_pr_body(self):
        self.start()
        code, out, _ = self.run_helper("finish", "--check", "echo=echo ok", "--summary", "did it",
                                       "--proposal", "retire the old wrapper")
        self.assertEqual(code, 0, out)
        evidence = json.loads(self.local("verification.json").read_text())
        self.assertEqual(evidence["sha"], git(self.root, "rev-parse", "HEAD"))
        self.assertTrue(evidence["ok"])
        self.assertEqual(evidence["checks"][0]["name"], "echo")
        body = self.local("pr-body.md").read_text()
        self.assertIn("Closes #46", body)
        self.assertIn("| echo | `echo ok`, `.` | passed | `" + evidence["sha"][:12] + "` |", body)
        self.assertIn("- retire the old wrapper", body)
        self.assertIn("- Merge: the owner's gate.", body)
        self.assertFalse(json.loads(self.local("claim.json").read_text())["auto_merge"])
        self.assertIn("Head: `" + evidence["sha"] + "`", self.local("checkpoint.md").read_text())
        self.assertIn("**Finished.** Task #46", self.local("milestone-comment.md").read_text())
        self.assertEqual(self.run_helper("verify-evidence")[0], 0)

    def test_finish_records_auto_merge_without_merging(self):
        """Approval mode auto: the body and milestone say GitHub merges; nothing merges here."""
        self.start()
        code, out, _ = self.run_helper("finish", "--check", "echo=echo ok", "--summary", "did it", "--auto-merge")
        self.assertEqual(code, 0, out)
        body = self.local("pr-body.md").read_text()
        self.assertIn("GitHub auto-merge (squash) enabled by task-finish", body)
        self.assertIn("integration branch `main`", body)
        self.assertTrue(json.loads(self.local("claim.json").read_text())["auto_merge"])
        self.assertEqual(git(self.root, "log", "--oneline", "main..HEAD"), "")  # nothing merged, nothing committed

    def test_finish_stops_on_a_failed_check_or_a_dirty_tree(self):
        self.start()
        code, _, _ = self.run_helper("finish", "--check", "bad=exit 7")
        self.assertEqual(code, 4)
        evidence = json.loads(self.local("verification.json").read_text())
        self.assertFalse(evidence["ok"])
        self.assertFalse(self.local("pr-body.md").exists())
        self.assertIn("Blocker: verification failed", self.local("checkpoint.md").read_text())
        self.assertEqual(self.run_helper("verify-evidence")[0], 5)
        (self.root / "README.md").write_text("changed\n")
        code, _, _ = self.run_helper("finish", "--check", "echo=echo ok")
        self.assertEqual(code, 4)
        self.assertIn("uncommitted changes", self.local("checkpoint.md").read_text())

    def test_evidence_check_fails_once_head_moves(self):
        self.start()
        self.assertEqual(self.run_helper("finish", "--check", "echo=echo ok")[0], 0)
        (self.root / "README.md").write_text("more\n")
        git(self.root, "commit", "-qam", "more")
        code, _, err = self.run_helper("verify-evidence")
        self.assertEqual(code, 5)
        self.assertIn("HEAD is", err)

    def test_stopped_finish_records_blocker_and_next_action(self):
        self.start()
        code, _, _ = self.run_helper("finish", "--stopped", "--blocker", "quota", "--next", "resume")
        self.assertEqual(code, 4)
        checkpoint = self.local("checkpoint.md").read_text()
        self.assertIn("State: stopped", checkpoint)
        self.assertIn("Blocker: quota", checkpoint)
        self.assertIn("Next action: resume", checkpoint)
        self.assertIn("**Stopped.**", self.local("milestone-comment.md").read_text())
        self.assertFalse(self.local("pr-body.md").exists())

    def test_finish_without_a_claim_fails(self):
        code, _, err = self.run_helper("finish", "--check", "echo=echo ok")
        self.assertEqual(code, 3)
        self.assertIn("task-start", err)

    def test_allowed_paths_parser_reads_only_its_section(self):
        self.assertEqual(boundary.allowed_paths(RECORD_BODY), ["shared/skills/", "tests/", "MANIFEST.json"])
        self.assertEqual(boundary.allowed_paths("### Problem\n`x`\n"), [])


if __name__ == "__main__":
    unittest.main()
