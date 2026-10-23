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
                self.SHARED, {"kits/a/": {"conductor-init", "conductor-handoff"}}, allowlist={})
        message = str(caught.exception)
        self.assertIn("kits/a/global/skills/coding-task/SKILL.md", message)
        self.assertIn("shared/skills/coding-task", message)

    def test_alias_satisfies_a_renamed_wrapper(self):
        checked = packaging.check_wrapper_copies(
            self.SHARED, {"kits/a/": {"conductor-init", "conductor-handoff", "coding-task"}},
            allowlist={})
        self.assertEqual(checked, ["kits/a/"])

    def test_allowlisted_omission_passes(self):
        checked = packaging.check_wrapper_copies(
            self.SHARED, {"kits/a/": {"conductor-init", "conductor-handoff"}},
            allowlist={"kits/a/": {"coding-task": "requested on #15"}})
        self.assertEqual(checked, ["kits/a/"])

    def test_stale_allowlist_entry_fails_once_the_copy_exists(self):
        with self.assertRaises(ValueError) as caught:
            packaging.check_wrapper_copies(
                self.SHARED, {"kits/a/": {"conductor-init", "conductor-handoff", "coding-task"}},
                allowlist={"kits/a/": {"coding-task": "requested on #15"}})
        self.assertIn("Stale wrapper allowlist entry", str(caught.exception))
        self.assertIn("'coding-task'", str(caught.exception))

    def test_allowlist_is_per_kit(self):
        kits = {"kits/a/": {"conductor-init", "conductor-handoff"},
                "kits/b/": {"conductor-init", "conductor-handoff", "coding-task"}}
        checked = packaging.check_wrapper_copies(
            self.SHARED, kits, allowlist={"kits/a/": {"coding-task": "requested on #15"}})
        self.assertEqual(checked, ["kits/a/", "kits/b/"])
        with self.assertRaises(ValueError):
            packaging.check_wrapper_copies(
                self.SHARED, kits, allowlist={"kits/b/": {"coding-task": "x"}})

    def test_repository_kit_carries_every_shared_wrapper_without_an_allowlist(self):
        shared = packaging.skill_names("shared/skills")
        self.assertIn("conductor-init", shared)
        kits = {prefix: packaging.skill_names(prefix + packaging.WRAPPER_SKILLS)
                for prefix in packaging.NATIVE}
        self.assertEqual(packaging.check_wrapper_copies(shared, kits), sorted(packaging.NATIVE))
        self.assertEqual(packaging.WRAPPER_ALLOWLIST, {}, "the drift allowlist is empty since the single re-pin")


if __name__ == "__main__":
    unittest.main()
