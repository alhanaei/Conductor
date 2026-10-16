"""Isolated behavioral tests for moving an adoption between policy sources.

Run with ``python3 -m unittest discover -s tests -v``. Source A is this package's own
manifest-bound file set; source B is a derived copy with a changed policy file and a
changed Claude Code verification skill, re-manifested. All targets are disposable.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

from test_conductor_init import initializer, tree_state  # noqa: E402

REPO = Path(__file__).resolve().parents[1]
SHA_B = "1234567890abcdef1234567890abcdef12345678"
POLICY_ADDITION = b"\nReviewed policy addition for the migration fixture.\n"
VERIFICATION_ADDITION = b"\nReviewed verification step added by the migration fixture.\n"


def sha256(data):
    return hashlib.sha256(data).hexdigest()


def state_without_backups(root):
    """Contents only: a rollback rewrites files, so their mtimes legitimately change."""
    return {key: value[0] for key, value in tree_state(root).items()
            if not key.startswith(".conductor/backups/")}


class MigrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp_sources = tempfile.TemporaryDirectory(prefix="conductor-test-migration-sources-")
        base = Path(cls.temp_sources.name)
        cls.source_a = base / "a"
        manifest = json.loads((REPO / "MANIFEST.json").read_bytes())
        for relative in sorted(set(manifest["files"]) | {"MANIFEST.json"}):
            destination = cls.source_a / relative
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.write_bytes((REPO / relative).read_bytes())
        cls.sha_a = subprocess.run(["git", "rev-parse", "HEAD"], cwd=REPO, check=True,
                                   stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True).stdout.strip()
        cls.manifest_a = sha256((cls.source_a / "MANIFEST.json").read_bytes())
        cls.source_b = base / "b"
        shutil.copytree(cls.source_a, cls.source_b)
        manifest = json.loads((cls.source_b / "MANIFEST.json").read_bytes())
        for relative, addition in (("shared/WORKFLOW.md", POLICY_ADDITION),
                                   ("assistants/claude-code/project/skills/project-verification/SKILL.md", VERIFICATION_ADDITION)):
            path = cls.source_b / relative
            path.write_bytes(path.read_bytes() + addition)
            manifest["files"][relative] = sha256(path.read_bytes())
        kit = cls.source_b / "assistants/claude-code"
        lines = []
        for line in (kit / "SHA256SUMS").read_text().splitlines():
            _, name = line.split("  ", 1)
            lines.append(f"{sha256((kit / name).read_bytes())}  {name}")
        sums = ("\n".join(lines) + "\n").encode()
        (kit / "SHA256SUMS").write_bytes(sums)
        manifest["files"]["assistants/claude-code/SHA256SUMS"] = sha256(sums)
        (cls.source_b / "MANIFEST.json").write_bytes((json.dumps(manifest, indent=2) + "\n").encode())
        cls.manifest_b = sha256((cls.source_b / "MANIFEST.json").read_bytes())

    @classmethod
    def tearDownClass(cls):
        cls.temp_sources.cleanup()

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="conductor-test-migration-project-")
        self.addCleanup(self.temp.cleanup)
        self.target = Path(self.temp.name) / "project"
        self.target.mkdir()
        self.claude = {"assistant": "claude-code", "surface": "desktop", "execution": "local",
                       "native_skills": ".claude/skills", "native_instructions": "CLAUDE.md",
                       "verified": True, "evidence_ref": "https://code.claude.com/docs/en/skills"}
        self.codex = {"assistant": "codex", "surface": "cli", "execution": "local",
                      "native_skills": ".agents/skills", "native_instructions": "AGENTS.md",
                      "verified": True, "evidence_ref": "https://learn.chatgpt.com/docs/build-skills"}
        self.facts = {"name": "Example service", "kind": "software", "purpose": "Serve a documented fixture API",
                      "repository": "https://github.com/example/service", "lifecycle": "Active",
                      "task_records": ["TASKS.md"], "checkpoint": ".conductor/HANDOFF.md", "architecture": "unknown",
                      "verification": [{"name": "Fixture check", "command": "python3 checks.py", "cwd": ".",
                                        "prerequisites": "Python standard library", "expected": "Exit 0",
                                        "source": "checks.py"}]}
        (self.target / "TASKS.md").write_text("# Authoritative task records\n")
        (self.target / "checks.py").write_text("from pathlib import Path\nPath('CHECK_WAS_RUN').write_text('bad')\n")

    def root(self, profile):
        return self.target / profile["native_skills"] / "conductor-project-init"

    def adopt(self, profile):
        self.assertEqual(initializer.generate(self.target, self.source_a, self.sha_a, profile,
                                              apply=True, manifest_sha=self.manifest_a)["status"], "installed")
        self.assertEqual(initializer.onboard(self.target, self.facts, self.root(profile), apply=True)["status"], "installed")

    def migrate(self, profile, *, apply=True):
        return initializer.migrate(self.target, self.source_b, SHA_B, apply=apply,
                                   manifest_sha=self.manifest_b, skill_root=self.root(profile))

    def onboard(self, profile):
        return initializer.onboard(self.target, self.facts, self.root(profile), apply=True)

    def adoption(self):
        return json.loads((self.target / ".conductor/adoption.json").read_text())

    def test_migration_moves_pin_snapshot_skill_and_record(self):
        self.adopt(self.claude)
        planned = self.migrate(self.claude, apply=False)
        self.assertEqual(planned["status"], "planned")
        actions = {change["path"]: change["action"] for change in planned["changes"]}
        self.assertEqual(actions["AGENTS.md"], "update")
        self.assertEqual(actions[".claude/skills/conductor-project-init/generation.json"], "update")
        self.assertEqual(actions[f".conductor/policy/{SHA_B}/shared/WORKFLOW.md"], "create")
        self.assertEqual(actions[f".conductor/policy/{self.sha_a}/shared/WORKFLOW.md"], "remove")
        self.assertEqual(actions[".claude/skills/project-verification/SKILL.md"], "update")
        installed = self.migrate(self.claude)
        self.assertEqual(installed["status"], "installed")
        self.assertNotIn("notes", installed)
        agents = (self.target / "AGENTS.md").read_text()
        new_policy = (self.source_b / "shared/WORKFLOW.md").read_bytes()
        self.assertIn(SHA_B, agents)
        self.assertIn(sha256(new_policy), agents)
        self.assertNotIn(self.sha_a, agents)
        self.assertEqual((self.target / f".conductor/policy/{SHA_B}/shared/WORKFLOW.md").read_bytes(), new_policy)
        self.assertFalse((self.target / f".conductor/policy/{self.sha_a}").exists())
        self.assertTrue((self.target / ".claude/skills/project-verification/SKILL.md").read_bytes().endswith(VERIFICATION_ADDITION))
        metadata = json.loads((self.root(self.claude) / "generation.json").read_text())
        self.assertEqual(metadata["policy_commit"], SHA_B)
        self.assertEqual((self.root(self.claude) / "assets/source/shared/WORKFLOW.md").read_bytes(), new_policy)
        record = self.adoption()
        self.assertEqual(record["policy_commit"], SHA_B)
        self.assertEqual(record["assistant_pins"], {"claude-code": SHA_B})
        self.assertEqual(record["migrations"], [{"from": self.sha_a, "to": SHA_B, "assistant": "claude-code"}])
        self.assertFalse(any(key.startswith(f".conductor/policy/{self.sha_a}/") for key in record["files"]))
        self.assertEqual(record["facts"], self.facts)
        self.assertEqual((self.target / "PROJECT.md").read_text().count(initializer.BEGIN), 1)
        self.assertFalse((self.target / "CHECK_WAS_RUN").exists())

    def test_migration_and_onboarding_reruns_are_exact_noops(self):
        self.adopt(self.claude)
        self.migrate(self.claude)
        before = tree_state(self.target)
        self.assertEqual(self.migrate(self.claude)["status"], "unchanged")
        self.assertEqual(self.onboard(self.claude)["status"], "unchanged")
        self.assertEqual(tree_state(self.target), before)

    def test_second_assistant_follows_the_shared_pin(self):
        self.adopt(self.codex)
        self.adopt(self.claude)
        first = self.migrate(self.claude)
        self.assertEqual(first["status"], "installed")
        self.assertEqual(first["notes"], ["Assistants still on the previous pin must run migrate for their own skill: codex"])
        self.assertEqual(self.adoption()["assistant_pins"], {"claude-code": SHA_B, "codex": self.sha_a})
        blocked = self.onboard(self.codex)
        self.assertEqual(blocked["status"], "blocked")
        self.assertIn("migrate", blocked["blockers"][0])
        agents_before = (self.target / "AGENTS.md").read_bytes()
        second = self.migrate(self.codex)
        self.assertEqual(second["status"], "installed")
        self.assertNotIn("notes", second)
        self.assertEqual((self.target / "AGENTS.md").read_bytes(), agents_before)
        self.assertEqual(json.loads((self.root(self.codex) / "generation.json").read_text())["policy_commit"], SHA_B)
        record = self.adoption()
        self.assertEqual(record["assistant_pins"], {"claude-code": SHA_B, "codex": SHA_B})
        self.assertEqual(len(record["migrations"]), 1)
        self.assertEqual(record["assistants"], ["claude-code", "codex"])
        before = tree_state(self.target)
        self.assertEqual(self.onboard(self.codex)["status"], "unchanged")
        self.assertEqual(self.onboard(self.claude)["status"], "unchanged")
        self.assertEqual(self.migrate(self.codex)["status"], "unchanged")
        self.assertEqual(tree_state(self.target), before)

    def test_edited_managed_section_blocks_migration_without_writes(self):
        self.adopt(self.claude)
        agents = self.target / "AGENTS.md"
        agents.write_text(agents.read_text().replace(self.sha_a, "f" * 40, 1))
        before = tree_state(self.target)
        with self.assertRaises(initializer.InitError):
            self.migrate(self.claude)
        self.assertEqual(tree_state(self.target), before)

    def test_migration_requires_an_adoption_record(self):
        self.assertEqual(initializer.generate(self.target, self.source_a, self.sha_a, self.claude,
                                              apply=True, manifest_sha=self.manifest_a)["status"], "installed")
        before = tree_state(self.target)
        result = self.migrate(self.claude)
        self.assertEqual(result["status"], "blocked")
        self.assertEqual(tree_state(self.target), before)

    def test_custom_verification_skill_survives_migration(self):
        self.adopt(self.claude)
        custom = self.target / ".claude/skills/project-verification/SKILL.md"
        custom.write_text("Custom verification instructions.\n")
        result = self.migrate(self.claude)
        self.assertEqual(result["status"], "installed")
        self.assertIn("Existing custom verification skill preserved as a whole; review its mapping to PROJECT.md", result["notes"])
        self.assertEqual(custom.read_text(), "Custom verification instructions.\n")

    def test_rollback_restores_the_previous_adoption_exactly(self):
        self.adopt(self.claude)
        before = state_without_backups(self.target)
        result = self.migrate(self.claude)
        transaction = self.target / result["transaction"]
        actions = {change["path"]: change["action"] for change in result["changes"]}
        self.assertIn("remove", actions.values())
        rolled = initializer.rollback(self.target, transaction, apply=True)
        self.assertEqual(rolled["status"], "rolled_back")
        self.assertEqual(state_without_backups(self.target), before)
        self.assertEqual(self.onboard(self.claude)["status"], "unchanged")

    def test_rollback_refuses_when_a_removed_file_was_recreated(self):
        self.adopt(self.claude)
        result = self.migrate(self.claude)
        transaction = self.target / result["transaction"]
        recreated = self.target / f".conductor/policy/{self.sha_a}/shared/WORKFLOW.md"
        recreated.parent.mkdir(parents=True)
        recreated.write_text("recreated after migration\n")
        before = tree_state(self.target)
        with self.assertRaises(initializer.InitError):
            initializer.rollback(self.target, transaction, apply=True)
        self.assertEqual(tree_state(self.target), before)

    def test_generate_at_a_new_pin_points_to_migrate(self):
        self.adopt(self.claude)
        result = initializer.generate(self.target, self.source_b, SHA_B, self.claude,
                                      apply=True, manifest_sha=self.manifest_b)
        self.assertEqual(result["status"], "blocked")
        self.assertIn("migrate", result["blockers"][0])


if __name__ == "__main__":
    unittest.main()
