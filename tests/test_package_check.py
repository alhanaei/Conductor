"""Tests for the packaging check's wrapper-copy rule (tests/package_conductor_init.py).

Run with ``python3 -m unittest discover -s tests -v``. The rule is exercised on plain
inputs, then once on the repository itself so a kit that drifts from shared/skills, or an
allowlist entry that outlived its copy, fails here before CI.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path
import sys
import unittest


REPO = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("package_conductor_init_under_test",
                                              REPO / "tests/package_conductor_init.py")
assert SPEC is not None and SPEC.loader is not None
packaging = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = packaging
SPEC.loader.exec_module(packaging)


class WrapperCopyRuleTests(unittest.TestCase):
    SHARED = {"conductor-init", "checkpoint-handoff", "coding-task"}

    def test_missing_copy_names_the_kit_and_the_skill(self):
        with self.assertRaises(ValueError) as caught:
            packaging.check_wrapper_copies(
                self.SHARED, {"codex/": {"conductor-init", "conductor-handoff"}}, allowlist={})
        message = str(caught.exception)
        self.assertIn("codex/global/skills/coding-task/SKILL.md", message)
        self.assertIn("shared/skills/coding-task", message)

    def test_alias_satisfies_a_renamed_wrapper(self):
        checked = packaging.check_wrapper_copies(
            self.SHARED, {"codex/": {"conductor-init", "conductor-handoff", "coding-task"}},
            allowlist={})
        self.assertEqual(checked, ["codex/"])

    def test_allowlisted_omission_passes(self):
        checked = packaging.check_wrapper_copies(
            self.SHARED, {"codex/": {"conductor-init", "conductor-handoff"}},
            allowlist={"codex/": {"coding-task": "requested on #15"}})
        self.assertEqual(checked, ["codex/"])

    def test_stale_allowlist_entry_fails_once_the_copy_exists(self):
        with self.assertRaises(ValueError) as caught:
            packaging.check_wrapper_copies(
                self.SHARED, {"codex/": {"conductor-init", "conductor-handoff", "coding-task"}},
                allowlist={"codex/": {"coding-task": "requested on #15"}})
        self.assertIn("Stale wrapper allowlist entry", str(caught.exception))
        self.assertIn("'coding-task'", str(caught.exception))

    def test_allowlist_is_per_kit(self):
        kits = {"codex/": {"conductor-init", "conductor-handoff"},
                "assistants/claude-code/": {"conductor-init", "conductor-handoff", "coding-task"}}
        checked = packaging.check_wrapper_copies(
            self.SHARED, kits, allowlist={"codex/": {"coding-task": "requested on #15"}})
        self.assertEqual(checked, ["assistants/claude-code/", "codex/"])
        with self.assertRaises(ValueError):
            packaging.check_wrapper_copies(
                self.SHARED, kits, allowlist={"assistants/claude-code/": {"coding-task": "x"}})

    def test_repository_kits_pass_with_the_recorded_allowlist(self):
        shared = packaging.skill_names("shared/skills")
        self.assertIn("conductor-init", shared)
        kits = {prefix: packaging.skill_names(prefix + packaging.WRAPPER_SKILLS)
                for prefix in packaging.NATIVE}
        self.assertEqual(packaging.check_wrapper_copies(shared, kits), sorted(packaging.NATIVE))
        for prefix, entries in packaging.WRAPPER_ALLOWLIST.items():
            self.assertIn(prefix, packaging.NATIVE)
            for reason in entries.values():
                self.assertRegex(reason, r"#\d+", "every allowlist entry names its task record")


if __name__ == "__main__":
    unittest.main()
