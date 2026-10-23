"""Isolated tests for the ``claude-code-projects`` adapter profile of the initializer.

Run with ``python3 -m unittest discover -s tests -v``. The profile reads an adopted
project's ``.conductor/adoption.json``, ``PROJECT.md`` and pinned policy file and emits the
project-instructions text, its digest, the always-on ``CLAUDE.md`` lines and an owner
checklist. The golden fixture under ``tests/golden/claude-code-projects/`` is the output
for this repository's own adoption record; regenerate it with
``python3 tests/test_conductor_init_projects.py --write-golden`` as a reviewed change.
"""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from test_conductor_init import initializer, tree_state  # noqa: E402

REPO = Path(__file__).resolve().parents[1]
GOLDEN = REPO / "tests/golden/claude-code-projects"
PROFILE = "claude-code-projects"
HELPER = REPO / "shared/skills/conductor-init/scripts/conductor_init.py"
# Files of this repository that the profile reads; the fixture is a copy of them.
INPUTS = ("AGENTS.md", "CLAUDE.md", "PROJECT.md", ".conductor/adoption.json",
          "tests/package_conductor_init.py", "tests/test_conductor_init.py",
          "docs/initializer-validation.md", "docs/contributing.md")


def sha(data):
    return hashlib.sha256(data).hexdigest()


def fixture_from_repo(target):
    """A disposable project holding this repository's adoption inputs and pinned policy."""
    adoption = json.loads((REPO / ".conductor/adoption.json").read_text())
    policy = initializer.policy_path(adoption["policy_commit"])
    for relative in INPUTS + (policy,):
        destination = target / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes((REPO / relative).read_bytes())
    # The fixture starts before this adapter was generated: strip its record and lines, and
    # start in approval mode manual whatever this repository runs (ADR 0005), so the golden
    # output and the mode tests do not move when the repository switches mode.
    adoption.pop("adapters", None)
    adoption.pop("protection", None)
    adoption["facts"] = {key: value for key, value in adoption["facts"].items() if key != "approval_mode"}
    project = (REPO / "PROJECT.md").read_bytes()
    project, project_section = initializer.append_block(project, initializer.project_record(adoption["facts"]))
    (target / "PROJECT.md").write_bytes(project)
    adoption["managed_blocks"]["PROJECT.md"] = sha(project_section)
    adoption["files"] = {key: value for key, value in adoption["files"].items()
                         if not key.startswith(initializer.ADAPTER_DIR + "/")}
    claude = (REPO / "CLAUDE.md").read_bytes()
    section = initializer.block(claude)
    spec = dict(initializer.PROFILES["claude-code"], name="claude-code")
    plain = initializer.native_adapter(spec, claude.replace(section, b""))
    new_section = (initializer.BEGIN + "\n" + plain + "\n" + initializer.END).encode()
    (target / "CLAUDE.md").write_bytes(claude.replace(section, new_section))
    adoption["managed_blocks"]["CLAUDE.md"] = sha(new_section)
    (target / ".conductor/adoption.json").write_bytes(initializer.encoded(adoption))
    return adoption


def golden_outputs(target):
    adoption = json.loads((target / ".conductor/adoption.json").read_text())
    entry = adoption["adapters"][PROFILE]
    return {
        "project-instructions.md": (target / entry["project_instructions"]).read_bytes(),
        "OWNER-CHECKLIST.md": (target / entry["owner_checklist"]).read_bytes(),
        "CLAUDE-section.md": initializer.block((target / "CLAUDE.md").read_bytes()),
        "adoption-entry.json": initializer.encoded(entry),
    }


class ProjectsProfileTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="conductor-test-projects-")
        self.addCleanup(self.temp.cleanup)
        self.target = Path(self.temp.name) / "project"
        self.target.mkdir()
        self.adoption = fixture_from_repo(self.target)

    def generate(self, *, apply=True, mode=None, **options):
        return initializer.generate_adapter(self.target, PROFILE, options, apply=apply, mode=mode)

    def check(self, **options):
        return initializer.check_adapter(self.target, PROFILE, options)

    def adoption_now(self):
        return json.loads((self.target / ".conductor/adoption.json").read_text())

    def test_four_outputs_match_the_golden_files(self):
        result = self.generate()
        self.assertEqual(result["status"], "installed", result)
        self.assertEqual(sorted(change["path"] for change in result["changes"]), [
            ".conductor/adapters/claude-code-projects/OWNER-CHECKLIST.md",
            ".conductor/adapters/claude-code-projects/project-instructions.md",
            ".conductor/adoption.json", "CLAUDE.md"])
        for name, data in golden_outputs(self.target).items():
            with self.subTest(output=name):
                self.assertEqual(data.decode(), (GOLDEN / name).read_text(),
                                 f"{name} differs from tests/golden; regenerate with --write-golden if intended")

    def test_instructions_carry_policy_rules_commands_and_fallback_within_the_limit(self):
        self.generate()
        entry = self.adoption_now()["adapters"][PROFILE]
        text = (self.target / entry["project_instructions"]).read_text()
        self.assertLess(len(text), 16000)
        self.assertEqual(len(text), entry["project_instructions_chars"])
        self.assertEqual(sha(text.encode()), entry["project_instructions_sha256"])
        policy = initializer.policy_path(self.adoption["policy_commit"])
        self.assertIn(policy, text)
        self.assertIn(sha((self.target / policy).read_bytes()), text)
        for check in self.adoption["facts"]["verification"]:
            self.assertIn(f"`{check['command']}` from `{check['cwd']}`", text)
        for phrase in ("`status:ready`", "Branch from `main`", "Never merge by hand, never mark a draft ready",
                       "approval mode `manual`", "Merge is the owner's gate",
                       "`Closes #N`", "`/task-start #N`", "`/task-finish --stopped`",
                       "`.git/conductor-local/claim.json`", "`.git/conductor-local/verification.json`",
                       "Found and left", self.adoption["facts"]["checkpoint"], "at most 2"):
            self.assertIn(phrase, " ".join(text.split()))
        self.assertNotIn("{{", text)
        self.assertTrue(all(len(line) <= 96 or " " not in line.strip() for line in text.splitlines()), "ragged line")

    def test_claude_md_carries_the_three_always_on_lines_and_onboard_keeps_them(self):
        self.generate()
        section = initializer.block((self.target / "CLAUDE.md").read_bytes()).decode()
        lines = self.adoption_now()["adapters"][PROFILE]["always_on_lines"]
        self.assertEqual(len(lines), 3)
        for line in lines:
            self.assertIn(line, section)
        self.assertEqual((self.target / "CLAUDE.md").read_bytes().count(b"@AGENTS.md"), 1)
        # A later claude-code onboarding regenerates the same section: exact no-op.
        self.assertEqual(initializer.recorded_always_on(
            self.adoption_now(), dict(initializer.PROFILES["claude-code"], name="claude-code")), tuple(lines))
        before = tree_state(self.target)
        self.assertEqual(self.generate()["status"], "unchanged")
        self.assertEqual(tree_state(self.target), before)

    def test_check_passes_after_generation_and_names_each_mismatch(self):
        self.generate()
        verified = self.check()
        self.assertEqual(verified["status"], "verified", verified)
        adoption = self.adoption_now()
        entry = adoption["adapters"][PROFILE]
        # 1. Recorded digest changed in the record.
        tampered = json.loads(json.dumps(adoption))
        tampered["adapters"][PROFILE]["project_instructions_sha256"] = "0" * 64
        (self.target / ".conductor/adoption.json").write_bytes(initializer.encoded(tampered))
        result = self.check()
        self.assertEqual(result["status"], "blocked")
        self.assertTrue(any("recorded project_instructions_sha256" in item for item in result["blockers"]), result)
        (self.target / ".conductor/adoption.json").write_bytes(initializer.encoded(adoption))
        # 2. Pasted text edited on disk without regenerating.
        path = self.target / entry["project_instructions"]
        original = path.read_bytes()
        path.write_bytes(original + b"\nExtra rule.\n")
        result = self.check()
        self.assertEqual(result["status"], "blocked")
        self.assertTrue(any(item.startswith("project_instructions file") for item in result["blockers"]), result)
        self.assertFalse(any("recorded project_instructions_sha256" in item for item in result["blockers"]))
        path.write_bytes(original)
        # 3. The always-on lines edited in CLAUDE.md.
        claude = self.target / "CLAUDE.md"
        claude.write_bytes(claude.read_bytes().replace(b"Never merge", b"Always merge"))
        result = self.check()
        self.assertEqual(result["status"], "blocked")
        self.assertTrue(any("CLAUDE.md managed section differs" in item for item in result["blockers"]), result)
        # 4. Inputs differ from the recorded ones.
        claude.write_bytes(claude.read_bytes().replace(b"Always merge", b"Never merge"))
        result = self.check(max_parallel_threads=3)
        self.assertEqual(result["status"], "blocked")
        self.assertTrue(any("recorded inputs" in item for item in result["blockers"]), result)
        self.assertEqual(self.check()["status"], "verified")

    def protection(self, *branches, **overrides):
        """Record branch protection evidence the way the owner checklist asks a thread to."""
        adoption = self.adoption_now()
        adoption["protection"] = {branch: dict({
            "bypass_allowed": False, "approvals_required": False,
            "required_checks": ["verify", "linked-task"], "verified": "2026-10-23",
            "evidence": "https://example.invalid/protection"}, **overrides) for branch in branches}
        (self.target / ".conductor/adoption.json").write_bytes(initializer.encoded(adoption))

    def test_auto_mode_is_refused_until_protection_is_recorded(self):
        """ADR 0005: auto needs bypass off and the two checks required on every landing branch."""
        with self.assertRaises(initializer.InitError) as caught:
            self.generate(apply=False, mode="auto")
        self.assertIn("`main` has no `protection` entry", str(caught.exception))
        self.protection("main", required_checks=["verify"])
        with self.assertRaises(initializer.InitError) as caught:
            self.generate(apply=False, mode="auto")
        self.assertIn("required_checks lack linked-task", str(caught.exception))
        self.protection("main")
        with self.assertRaises(initializer.InitError) as caught:
            self.generate(apply=False, mode="auto", integration_branch="staging")
        self.assertIn("`staging` has no `protection` entry", str(caught.exception))
        self.assertEqual(self.generate(apply=False, mode="auto")["status"], "planned")
        with self.assertRaises(initializer.InitError):
            self.generate(apply=False, mode="later")

    def test_auto_mode_writes_the_fact_and_the_delegated_text(self):
        self.protection("main", "staging")
        result = self.generate(mode="auto", integration_branch="staging")
        self.assertEqual(result["status"], "installed", result)
        self.assertIn("PROJECT.md", [change["path"] for change in result["changes"]])
        adoption = self.adoption_now()
        self.assertEqual(adoption["facts"]["approval_mode"], "auto")
        self.assertIn("- Approval mode: auto", (self.target / "PROJECT.md").read_text())
        self.assertEqual(initializer.block((self.target / "PROJECT.md").read_bytes()) is not None, True)
        self.assertEqual(sha(initializer.block((self.target / "PROJECT.md").read_bytes())), adoption["managed_blocks"]["PROJECT.md"])
        entry = adoption["adapters"][PROFILE]
        self.assertEqual(entry["inputs"]["integration_branch"], "staging")
        text = (self.target / entry["project_instructions"]).read_text()
        for phrase in ("Approval mode `auto`", "the coordinator files and readies sub-issues", "Branch from `staging`",
                       "enable GitHub auto-merge with squash", "Promotion of `staging` into `main` is the owner's merge",
                       "push to `staging` or `main` without a pull request"):
            self.assertIn(phrase, " ".join(text.split()))
        self.assertNotIn("do not file it", text)
        lines = entry["always_on_lines"]
        self.assertIn("Approval mode `auto`", lines[1])
        self.assertIn("push to `staging` or `main` without a pull request", lines[2])
        checklist = (self.target / entry["owner_checklist"]).read_text()
        for phrase in ("`CONDUCTOR_APPROVAL_MODE` to `auto`", "`CONDUCTOR_INTEGRATION_BRANCH` to `staging`",
                       "Allow auto-merge", "On `staging` and `main`"):
            self.assertIn(phrase, checklist)
        # The fact now drives the text: a rerun without the override is a no-op, check passes,
        # and a different integration branch is a named input mismatch.
        self.assertEqual(self.generate(integration_branch="staging")["status"], "unchanged")
        self.assertEqual(self.check()["status"], "verified")
        result = self.check(integration_branch="main")
        self.assertEqual(result["status"], "blocked")
        self.assertTrue(any("recorded inputs" in item for item in result["blockers"]), result)
        # Back to manual: the fact, PROJECT.md and the text follow.
        self.assertEqual(self.generate(mode="manual", integration_branch="staging")["status"], "installed")
        self.assertEqual(self.adoption_now()["facts"]["approval_mode"], "manual")
        self.assertIn("- Approval mode: manual", (self.target / "PROJECT.md").read_text())
        self.assertIn("Merge is the owner's gate", (self.target / self.adoption_now()["adapters"][PROFILE]["project_instructions"]).read_text())

    def test_manual_default_records_no_fact_and_names_the_variable(self):
        self.generate()
        self.assertNotIn("approval_mode", self.adoption_now()["facts"])
        entry = self.adoption_now()["adapters"][PROFILE]
        self.assertEqual(entry["inputs"]["integration_branch"], "main")
        checklist = (self.target / entry["owner_checklist"]).read_text()
        self.assertIn("`CONDUCTOR_APPROVAL_MODE` to `manual`", checklist)
        self.assertNotIn("CONDUCTOR_INTEGRATION_BRANCH", checklist)
        self.assertNotIn("Allow auto-merge", checklist)
        self.assertIn("record it under `protection.<branch>`", checklist)

    def test_check_before_generation_and_without_adoption_is_blocked(self):
        self.assertEqual(self.check()["status"], "blocked")
        empty = Path(self.temp.name) / "empty"
        empty.mkdir()
        self.assertEqual(initializer.generate_adapter(empty, PROFILE, None, apply=False)["status"], "blocked")
        with self.assertRaises(initializer.InitError):
            initializer.generate_adapter(self.target, "codex-cloud", None, apply=False)

    def test_preview_writes_nothing_and_over_limit_text_is_refused(self):
        before = tree_state(self.target)
        result = self.generate(apply=False)
        self.assertEqual(result["status"], "planned")
        self.assertEqual(tree_state(self.target), before)
        adoption = self.adoption_now()
        adoption["facts"]["purpose"] = "x" * 16000
        (self.target / ".conductor/adoption.json").write_bytes(initializer.encoded(adoption))
        with self.assertRaises(initializer.InitError) as caught:
            self.generate(apply=False)
        self.assertIn("16000 field limit", str(caught.exception))
        with self.assertRaises(initializer.InitError):
            self.generate(apply=False, max_parallel_threads=0)

    def test_edited_policy_file_or_custom_output_blocks_generation(self):
        policy = self.target / initializer.policy_path(self.adoption["policy_commit"])
        policy.write_bytes(policy.read_bytes() + b"\nedit\n")
        with self.assertRaises(initializer.InitError):
            self.generate(apply=False)
        policy.write_bytes(policy.read_bytes()[:-len(b"\nedit\n")])
        custom = self.target / initializer.ADAPTER_DIR / PROFILE / "project-instructions.md"
        custom.parent.mkdir(parents=True)
        custom.write_text("hand-written\n")
        with self.assertRaises(initializer.InitError):
            self.generate(apply=False)

    def test_cli_runs_against_this_repository_and_is_current(self):
        """Acceptance 1: the committed outputs of this repository are what the helper generates now."""
        for arguments in (("generate", "--profile", PROFILE), ("check", "--profile", PROFILE)):
            completed = subprocess.run(
                [sys.executable, str(HELPER), *arguments, "--target", str(REPO)],
                cwd=REPO, check=False, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
            self.assertEqual(completed.returncode, 0, completed.stdout + completed.stderr)
            response = json.loads(completed.stdout)
            self.assertIn(response["status"], ("unchanged", "verified"), response)
            self.assertFalse(response["changes"])


def write_golden():
    with tempfile.TemporaryDirectory(prefix="conductor-golden-") as temp:
        target = Path(temp) / "project"
        target.mkdir()
        fixture_from_repo(target)
        result = initializer.generate_adapter(target, PROFILE, None, apply=True)
        assert result["status"] == "installed", result
        GOLDEN.mkdir(parents=True, exist_ok=True)
        for name, data in golden_outputs(target).items():
            (GOLDEN / name).write_bytes(data)
            print("wrote", GOLDEN / name)


if __name__ == "__main__":
    sys.path.insert(0, os.path.dirname(__file__))
    if "--write-golden" in sys.argv:
        write_golden()
    else:
        unittest.main()
