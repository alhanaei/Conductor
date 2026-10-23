"""Isolated behavioral tests for the Claude Code native mapping of the initializer.

Run with ``python3 -m unittest discover -s tests -v``. The fixture is this package's
own reviewed file set as listed by MANIFEST.json, so ``tests/package_conductor_init.py``
must be up to date. All targets are disposable directories; no project command runs.
"""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest

from test_conductor_init import initializer, manifest_source, tree_state  # noqa: E402

REPO = Path(__file__).resolve().parents[1]


class ClaudeCodeInitializerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.artifact_temp = tempfile.TemporaryDirectory(prefix="conductor-test-claude-source-")
        cls.artifact = Path(cls.artifact_temp.name)
        cls.source_sha, cls.manifest_sha = manifest_source(cls.artifact)

    @classmethod
    def tearDownClass(cls):
        cls.artifact_temp.cleanup()

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="conductor-test-claude-project-")
        self.addCleanup(self.temp.cleanup)
        self.target = Path(self.temp.name) / "project"
        self.target.mkdir()
        self.claude = {
            "assistant": "claude-code", "surface": "desktop", "execution": "local",
            "native_skills": ".claude/skills", "native_instructions": "CLAUDE.md",
            "verified": True, "evidence_ref": "https://code.claude.com/docs/en/skills",
        }
        self.facts = {
            "name": "Example service", "kind": "software",
            "purpose": "Serve a documented fixture API",
            "repository": "https://github.com/example/service",
            "lifecycle": "Active", "task_records": ["TASKS.md"],
            "checkpoint": ".conductor/HANDOFF.md", "architecture": "unknown",
            "verification": [{
                "name": "Fixture check", "command": "python3 checks.py",
                "cwd": ".", "prerequisites": "Python standard library",
                "expected": "Exit 0", "source": "checks.py",
            }],
        }
        (self.target / "TASKS.md").write_text("# Authoritative task records\n")
        (self.target / "checks.py").write_text(
            "from pathlib import Path\nPath('CHECK_WAS_RUN').write_text('bad')\n")

    def skill_root(self, profile):
        return self.target / profile["native_skills"] / "conductor-project-init"

    def generate(self, profile=None, *, apply=True, **kwargs):
        options = {
            "target": self.target, "source": self.artifact, "source_sha": self.source_sha,
            "capabilities": profile or self.claude, "manifest_sha": self.manifest_sha, "apply": apply,
        }
        options.update(kwargs)
        return initializer.generate(**options)

    def onboard(self, profile=None, *, apply=True, **kwargs):
        profile = profile or self.claude
        options = {"target": self.target, "facts": self.facts,
                   "skill_root": self.skill_root(profile), "apply": apply}
        options.update(kwargs)
        return initializer.onboard(**options)

    def assert_rejected_without_writes(self, operation):
        before = tree_state(self.target)
        try:
            result = operation()
        except initializer.InitError:
            pass
        else:
            self.assertIn(result["status"], {"blocked", "draft"}, result)
            self.assertTrue(result.get("blockers"), result)
        self.assertEqual(tree_state(self.target), before)

    def test_generated_claude_skill_has_native_layout_without_legacy_metadata(self):
        self.assertEqual(self.generate()["status"], "installed")
        root = self.skill_root(self.claude)
        for relative in ("SKILL.md", "scripts/conductor_init.py", "generation.json",
                         "assets/source/shared/WORKFLOW.md",
                         "assets/source/assistants/claude-code/project/skills/project-verification/SKILL.md"):
            self.assertTrue((root / relative).is_file(), relative)
        self.assertFalse((root / "agents/openai.yaml").exists())
        self.assertFalse((self.target / ".agents").exists())
        skill = (root / "SKILL.md").read_text()
        self.assertIn("Claude Code", skill)
        self.assertIn(".claude/skills/conductor-project-init/scripts/conductor_init.py", skill)
        self.assertIn(f"`{self.source_sha}`", skill)
        self.assertNotIn("@", skill.replace("@SOURCE_SHA@", ""))
        metadata = json.loads((root / "generation.json").read_text())
        self.assertEqual(metadata["assistant"], "claude-code")
        self.assertEqual(metadata["native_checksums_sha256"], hashlib.sha256(
            (self.artifact / "assistants/claude-code/SHA256SUMS").read_bytes()).hexdigest())
        self.assertNotIn("source_codex_checksums_sha256", metadata)
        self.assertEqual(self.generate()["status"], "unchanged")

    def test_claude_onboarding_writes_shared_facts_and_imports_agents(self):
        self.generate()
        result = self.onboard()
        self.assertEqual(result["status"], "installed")
        agents = (self.target / "AGENTS.md").read_text()
        claude = (self.target / "CLAUDE.md").read_text()
        self.assertIn(self.source_sha, agents)
        self.assertIn(initializer.BEGIN, agents)
        self.assertEqual(claude.count("@AGENTS.md"), 1)
        self.assertEqual(claude.count(initializer.BEGIN), 1)
        self.assertNotIn(self.source_sha, claude)
        self.assertTrue((self.target / "PROJECT.md").is_file())
        installed = self.target / ".claude/skills/project-verification/SKILL.md"
        self.assertEqual(installed.read_bytes(), (
            self.artifact / "assistants/claude-code/project/skills/project-verification/SKILL.md").read_bytes())
        self.assertFalse((self.target / ".agents").exists())
        self.assertFalse((self.target / "CHECK_WAS_RUN").exists())
        adoption = json.loads((self.target / ".conductor/adoption.json").read_text())
        self.assertEqual(adoption["assistants"], ["claude-code"])
        self.assertIn("CLAUDE.md", adoption["managed_blocks"])
        self.assertIn("claude-code", adoption["native_discovery"])

    def test_existing_claude_rules_and_import_are_preserved_once(self):
        existing = "@AGENTS.md\n\n# Personal project rules\nKeep this untouched.\n"
        (self.target / "CLAUDE.md").write_text(existing)
        self.generate()
        self.assertEqual(self.onboard()["status"], "installed")
        claude = (self.target / "CLAUDE.md").read_text()
        self.assertTrue(claude.startswith(existing))
        self.assertEqual(claude.count("@AGENTS.md"), 1)

    def test_repeat_claude_onboarding_is_exact_noop(self):
        self.generate()
        self.onboard()
        before = tree_state(self.target)
        result = self.onboard()
        self.assertEqual(result["status"], "unchanged")
        self.assertFalse(result["changes"])
        self.assertEqual(tree_state(self.target), before)

    def test_mismatched_native_mapping_is_draft(self):
        for field, value in (("native_skills", ".agents/skills"), ("native_instructions", "AGENTS.md"),
                             ("verified", False)):
            with self.subTest(field=field):
                self.assert_rejected_without_writes(
                    lambda: self.generate(dict(self.claude, **{field: value})))

    def test_legacy_adoption_record_is_read_as_data(self):
        """A record written by an earlier generator for another assistant still migrates."""
        self.generate()
        self.assertEqual(self.onboard()["status"], "installed")
        record = self.target / ".conductor/adoption.json"
        adoption = json.loads(record.read_text())
        adoption["assistants"] = ["codex"]
        adoption["generator_sha256"] = "0" * 64
        adoption["native_discovery"] = "unverified"
        del adoption["assistant_pins"]
        adoption["managed_blocks"] = {key: value for key, value in adoption["managed_blocks"].items()
                                      if key != "CLAUDE.md"}
        record.write_text(json.dumps(adoption, indent=2, sort_keys=True) + "\n")
        result = self.onboard()
        self.assertEqual(result["status"], "installed")
        adoption = json.loads(record.read_text())
        self.assertEqual(adoption["assistants"], ["claude-code", "codex"])
        self.assertEqual(adoption["generator_sha256"]["codex"], "0" * 64)
        self.assertIn("claude-code", adoption["generator_sha256"])
        self.assertEqual(adoption["native_discovery"]["codex"], "unverified")
        self.assertEqual(adoption["assistant_pins"], {"claude-code": self.source_sha})

    def test_onboarding_locates_single_generated_skill_without_explicit_root(self):
        self.generate()
        result = initializer.onboard(self.target, self.facts, apply=False)
        self.assertEqual(result["status"], "planned")

    def test_rollback_restores_original_claude_rules(self):
        original = b"# Original Claude rules\nDo not discard me.\n"
        (self.target / "CLAUDE.md").write_bytes(original)
        self.generate()
        result = self.onboard()
        transaction = self.target / result["transaction"]
        rolled = initializer.rollback(self.target, transaction, apply=True)
        self.assertEqual(rolled["status"], "rolled_back")
        self.assertEqual((self.target / "CLAUDE.md").read_bytes(), original)
        self.assertFalse((self.target / "AGENTS.md").exists())
        self.assertFalse((self.target / ".claude/skills/project-verification/SKILL.md").exists())

    def test_generated_claude_skill_is_portable(self):
        self.generate()
        for path in self.skill_root(self.claude).rglob("*"):
            if path.is_file() and path.suffix in {".md", ".json"}:
                text = path.read_text()
                self.assertNotIn(str(self.target), text, str(path))
                self.assertNotIn(str(self.artifact), text, str(path))


if __name__ == "__main__":
    sys.path.insert(0, os.path.dirname(__file__))
    unittest.main()
