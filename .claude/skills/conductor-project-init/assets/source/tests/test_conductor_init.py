"""Isolated behavioral tests for the two-stage portable Conductor initializer.

Run with ``python3 -m unittest discover -s tests -v``.  Development may point
CONDUCTOR_INIT_IMPL at another checkout; the default is repository-relative.
The pinned source fixture is this package's own reviewed file set as listed by
MANIFEST.json, so ``tests/package_conductor_init.py`` must be up to date. All targets
are disposable directories; no project command runs.
"""

from __future__ import annotations

import copy
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


REPO = Path(__file__).resolve().parents[1]
IMPL = Path(os.environ.get("CONDUCTOR_INIT_IMPL", str(
    REPO / "shared/skills/conductor-init/scripts/conductor_init.py")))
SPEC = importlib.util.spec_from_file_location("conductor_init_under_test", IMPL)
assert SPEC is not None and SPEC.loader is not None
initializer = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = initializer
SPEC.loader.exec_module(initializer)

PROFILE = {
    "assistant": "claude-code", "surface": "desktop", "execution": "local",
    "native_skills": ".claude/skills", "native_instructions": "CLAUDE.md",
    "verified": True, "evidence_ref": "https://code.claude.com/docs/en/skills",
}
NATIVE_SKILLS = PROFILE["native_skills"]
NATIVE_INSTRUCTIONS = PROFILE["native_instructions"]
VERIFICATION_SKILL = "assistants/claude-code/project/skills/project-verification/SKILL.md"


def tree_state(root: Path) -> dict[str, tuple[bytes, int]]:
    """Capture actual user-visible bytes and mtimes, including transactions."""
    return {
        str(path.relative_to(root)): (path.read_bytes(), path.stat().st_mtime_ns)
        for path in sorted(root.rglob("*")) if path.is_file()
    }


def manifest_source(destination: Path) -> tuple[str, str]:
    """Copy the manifest-bound working tree into destination; return (HEAD sha, manifest sha)."""
    manifest = json.loads((REPO / "MANIFEST.json").read_bytes())
    for relative in sorted(set(manifest["files"]) | {"MANIFEST.json"}):
        target = destination / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes((REPO / relative).read_bytes())
    sha = subprocess.run(["git", "rev-parse", "HEAD"], cwd=REPO, check=True,
                         stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True).stdout.strip()
    return sha, hashlib.sha256((destination / "MANIFEST.json").read_bytes()).hexdigest()


class InitializerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.artifact_temp = tempfile.TemporaryDirectory(prefix="conductor-test-source-")
        cls.artifact = Path(cls.artifact_temp.name)
        cls.source_sha, cls.manifest_sha = manifest_source(cls.artifact)

    @classmethod
    def tearDownClass(cls):
        cls.artifact_temp.cleanup()

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="conductor-test-project-")
        self.addCleanup(self.temp.cleanup)
        self.target = Path(self.temp.name) / "project"
        self.target.mkdir()
        self.capabilities = dict(PROFILE)
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

    @property
    def skill_root(self):
        return self.target / NATIVE_SKILLS / "conductor-project-init"

    def generate(self, *, apply=True, **kwargs):
        options = {
            "target": self.target, "source": self.artifact,
            "source_sha": self.source_sha, "capabilities": self.capabilities,
            "manifest_sha": self.manifest_sha, "apply": apply,
        }
        options.update(kwargs)
        return initializer.generate(**options)

    def onboard(self, *, apply=True, **kwargs):
        options = {"target": self.target, "facts": self.facts,
                   "skill_root": self.skill_root, "apply": apply}
        options.update(kwargs)
        return initializer.onboard(**options)

    def install(self):
        self.assertEqual(self.generate()["status"], "installed")
        return self.onboard()

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

    def test_generation_dry_run_has_no_filesystem_effect(self):
        before = tree_state(self.target)
        result = self.generate(apply=False)
        self.assertEqual(result["status"], "planned")
        self.assertTrue(result["changes"])
        self.assertEqual(tree_state(self.target), before)

    def test_generated_skill_is_self_contained_and_portable(self):
        self.assertEqual(self.generate()["status"], "installed")
        for relative in ("SKILL.md", "scripts/conductor_init.py", "generation.json",
                         "assets/source/shared/WORKFLOW.md"):
            self.assertTrue((self.skill_root / relative).is_file(), relative)
        metadata = json.loads((self.skill_root / "generation.json").read_text())
        self.assertIn(self.source_sha, json.dumps(metadata))
        for path in self.skill_root.rglob("*"):
            if path.is_file() and path.suffix in {".md", ".json", ".yaml"}:
                text = path.read_text()
                self.assertNotIn(str(self.target), text, str(path))
                self.assertNotIn(str(self.artifact), text, str(path))
        self.assertFalse((self.target / "AGENTS.md").exists())
        self.assertFalse((self.target / NATIVE_INSTRUCTIONS).exists())

    def test_repeat_generation_preserves_bytes_and_mtimes(self):
        self.generate()
        before = tree_state(self.target)
        result = self.generate()
        self.assertEqual(result["status"], "unchanged")
        self.assertFalse(result["changes"])
        self.assertEqual(tree_state(self.target), before)

    def test_unsupported_assistant_is_draft_without_installation(self):
        profile = dict(self.capabilities, assistant="unknown-assistant")
        self.assert_rejected_without_writes(lambda: self.generate(capabilities=profile))

    def test_unverified_capabilities_do_not_activate_native_instructions(self):
        profile = dict(self.capabilities, verified=False)
        self.assert_rejected_without_writes(lambda: self.generate(capabilities=profile))

    def test_cloud_capability_profile_stays_project_scoped(self):
        profile = dict(self.capabilities, execution="cloud")
        result = self.generate(capabilities=profile)
        self.assertEqual(result["status"], "installed")
        self.assertTrue((self.skill_root / "SKILL.md").exists())
        self.assertFalse((self.target / NATIVE_INSTRUCTIONS).exists())

    def test_software_onboarding_pins_policy_and_never_executes_commands(self):
        result = self.install()
        self.assertEqual(result["status"], "installed")
        snapshot = self.target / ".conductor/policy" / self.source_sha
        self.assertEqual((snapshot / "shared/WORKFLOW.md").read_bytes(),
                         (self.artifact / "shared/WORKFLOW.md").read_bytes())
        agents = (self.target / "AGENTS.md").read_text()
        project = (self.target / "PROJECT.md").read_text()
        self.assertIn(self.source_sha, agents)
        self.assertIn("Active", project)
        self.assertIn("TASKS.md", project)
        self.assertTrue((self.target / ".conductor/adoption.json").is_file())
        self.assertTrue((self.target / NATIVE_SKILLS / "project-verification/SKILL.md").is_file())
        self.assertFalse((self.target / "CHECK_WAS_RUN").exists())

    def test_snapshot_holds_only_the_shared_policy_tree(self):
        self.install()
        snapshot = self.target / ".conductor/policy" / self.source_sha
        files = {str(p.relative_to(snapshot)) for p in snapshot.rglob("*") if p.is_file()}
        self.assertIn("shared/WORKFLOW.md", files)
        self.assertIn("shared/workflows/backlog.md", files)
        self.assertTrue(all(name.startswith("shared/") for name in files), sorted(files)[:5])
        self.assertNotIn("MANIFEST.json", files)
        self.assertFalse(any(name.startswith(("tests/", "docs/", "assistants/")) for name in files))

    def test_adoption_records_the_policy_file_digest_as_the_pin(self):
        self.install()
        adoption = json.loads((self.target / ".conductor/adoption.json").read_text())
        policy = hashlib.sha256((self.artifact / "shared/WORKFLOW.md").read_bytes()).hexdigest()
        self.assertEqual(adoption["policy_commit"], self.source_sha)
        self.assertEqual(adoption["policy_sha256"], policy)
        self.assertIn(policy, (self.target / "AGENTS.md").read_text())

    def test_analytics_only_project_has_no_inferred_software_checks(self):
        self.generate()
        facts = dict(self.facts, name="Dataset review", kind="analytics",
                     purpose="Reconcile approved fixture totals",
                     data_sources=["data/approved.csv"], storage="data/",
                     verification=[{
                         "name": "Reconcile totals", "command": "python3 reconcile.py",
                         "cwd": ".", "prerequisites": "Approved local CSV",
                         "expected": "Totals match within 0.01", "source": "reconcile.py",
                     }])
        (self.target / "reconcile.py").write_text("raise RuntimeError('must not execute')\n")
        (self.target / "data").mkdir()
        (self.target / "data/approved.csv").write_text("value\n1\n")
        result = self.onboard(facts=facts)
        self.assertEqual(result["status"], "installed")
        content = (self.target / "PROJECT.md").read_text()
        self.assertIn("analytics", content.lower())
        self.assertIn("data/approved.csv", content)
        self.assertNotIn("npm test", content)
        self.assertNotIn("pytest", content)

    def test_preserves_existing_instructions_and_custom_files(self):
        shared = "# Personal rules\nAlways use the fixture review process.\n"
        native = "# Native project rules\nKeep this untouched.\n"
        custom = b"custom project facts outside managed ownership\n"
        (self.target / "AGENTS.md").write_text(shared)
        (self.target / NATIVE_INSTRUCTIONS).write_text(native)
        (self.target / "user-notes.txt").write_bytes(custom)
        before = tree_state(self.target)
        self.assertEqual(self.install()["status"], "installed")
        self.assertIn(shared, (self.target / "AGENTS.md").read_text())
        self.assertIn(native, (self.target / NATIVE_INSTRUCTIONS).read_text())
        self.assertEqual(tree_state(self.target)["user-notes.txt"], before["user-notes.txt"])

    def test_repeat_onboarding_is_exact_noop(self):
        self.install()
        before = tree_state(self.target)
        result = self.onboard()
        self.assertEqual(result["status"], "unchanged")
        self.assertFalse(result["changes"])
        self.assertEqual(tree_state(self.target), before)

    def test_custom_text_outside_managed_rules_survives_repeat_onboarding(self):
        self.install()
        agents = self.target / "AGENTS.md"
        agents.write_text("# Later personal rule\nPreserve this custom preface.\n\n" +
                          agents.read_text())
        before = tree_state(self.target)
        result = self.onboard()
        self.assertEqual(result["status"], "unchanged")
        self.assertEqual(tree_state(self.target), before)

    def test_parked_lifecycle_is_preserved_separately_from_task_progress(self):
        self.generate()
        facts = dict(self.facts, lifecycle="Parked")
        result = self.onboard(facts=facts)
        self.assertEqual(result["status"], "installed")
        project = (self.target / "PROJECT.md").read_text()
        self.assertIn("Parked", project)
        self.assertEqual((self.target / "TASKS.md").read_text(),
                         "# Authoritative task records\n")

    def test_onboarding_dry_run_does_not_create_effective_rules(self):
        self.generate()
        before = tree_state(self.target)
        result = self.onboard(apply=False)
        self.assertEqual(result["status"], "planned")
        self.assertEqual(tree_state(self.target), before)
        self.assertFalse((self.target / "AGENTS.md").exists())

    def test_missing_essential_fact_is_draft(self):
        self.generate()
        facts = copy.deepcopy(self.facts)
        del facts["purpose"]
        self.assert_rejected_without_writes(lambda: self.onboard(facts=facts))

    def test_unknown_verification_does_not_invent_a_command(self):
        self.generate()
        facts = dict(self.facts, verification=[])
        result = self.onboard(facts=facts)
        self.assertIn(result["status"], {"installed", "draft"})
        if (self.target / "AGENTS.md").exists():
            content = (self.target / "AGENTS.md").read_text()
            self.assertNotIn("python3 checks.py", content)
            self.assertNotIn("npm test", content)
            self.assertNotIn("pytest", content)
        self.assertFalse((self.target / "CHECK_WAS_RUN").exists())

    def test_active_override_blocks_without_touching_files(self):
        self.generate()
        (self.target / "AGENTS.override.md").write_text("# Effective override\n")
        self.assert_rejected_without_writes(self.onboard)

    def test_closed_project_is_not_reopened_implicitly(self):
        self.generate()
        (self.target / "PROJECT.md").write_text("# Existing project\n\n- Lifecycle: Closed\n")
        self.assert_rejected_without_writes(self.onboard)

    def test_existing_confirmed_owner_is_not_reassigned(self):
        self.generate()
        facts = dict(self.facts, owner={"name": "Alice", "ref": "TASKS.md", "confirmed": True})
        self.assertEqual(self.onboard(facts=facts)["status"], "installed")
        reassignment = dict(facts, owner={"name": "Bob", "ref": "TASKS.md", "confirmed": True})
        self.assert_rejected_without_writes(lambda: self.onboard(facts=reassignment))

    def test_user_edit_inside_managed_rules_blocks_reinstallation(self):
        self.install()
        agents = self.target / "AGENTS.md"
        content = agents.read_text()
        self.assertIn(self.source_sha, content)
        agents.write_text(content.replace(self.source_sha, "f" * 40, 1))
        self.assert_rejected_without_writes(self.onboard)

    def test_user_edit_to_generated_skill_is_not_overwritten(self):
        self.generate()
        skill = self.skill_root / "SKILL.md"
        skill.write_text(skill.read_text() + "\nUser customization.\n")
        self.assert_rejected_without_writes(self.generate)

    def test_rollback_restores_original_shared_file_and_keeps_unrelated_changes(self):
        original = b"# Original project rules\nDo not discard me.\n"
        (self.target / "AGENTS.md").write_bytes(original)
        self.generate()
        result = self.onboard()
        transaction = Path(result["transaction"])
        if not transaction.is_absolute():
            transaction = self.target / transaction
        if transaction.is_dir():
            transaction /= "transaction.json"
        self.assertTrue(transaction.is_file())
        (self.target / "later-user-note.txt").write_text("created after setup\n")
        dry_before = tree_state(self.target)
        dry = initializer.rollback(self.target, transaction, apply=False)
        self.assertEqual(dry["status"], "planned")
        self.assertEqual(tree_state(self.target), dry_before)
        rolled = initializer.rollback(self.target, transaction, apply=True)
        self.assertIn(rolled["status"], {"installed", "rolled_back"})
        self.assertEqual((self.target / "AGENTS.md").read_bytes(), original)
        self.assertEqual((self.target / "later-user-note.txt").read_text(), "created after setup\n")
        self.assertFalse((self.target / "PROJECT.md").exists())

    def test_rollback_refuses_to_erase_later_managed_file_edits(self):
        result = self.install()
        transaction = Path(result["transaction"])
        if not transaction.is_absolute():
            transaction = self.target / transaction
        if transaction.is_dir():
            transaction /= "transaction.json"
        project = self.target / "PROJECT.md"
        project.write_text(project.read_text() + "\nUser added a later decision.\n")
        self.assert_rejected_without_writes(
            lambda: initializer.rollback(self.target, transaction, apply=True))

    def test_traversal_in_native_destination_is_rejected(self):
        profile = dict(self.capabilities, native_skills="../escaped-skills")
        self.assert_rejected_without_writes(lambda: self.generate(capabilities=profile))
        self.assertFalse((self.target.parent / "escaped-skills").exists())

    def test_traversal_in_checkpoint_is_rejected(self):
        self.generate()
        facts = dict(self.facts, checkpoint="../escaped-checkpoint.md")
        self.assert_rejected_without_writes(lambda: self.onboard(facts=facts))
        self.assertFalse((self.target.parent / "escaped-checkpoint.md").exists())

    def test_symlinked_destination_does_not_write_outside_project(self):
        outside = self.target.parent / "outside"
        outside.mkdir()
        (self.target / NATIVE_SKILLS.split("/")[0]).symlink_to(outside, target_is_directory=True)
        before = tree_state(outside)
        self.assert_rejected_without_writes(self.generate)
        self.assertEqual(tree_state(outside), before)

    def test_symlinked_shared_rules_are_not_followed(self):
        self.generate()
        outside = self.target.parent / "outside-rules.md"
        outside.write_text("# Other project rules\n")
        (self.target / "AGENTS.md").symlink_to(outside)
        original = outside.read_bytes()
        self.assert_rejected_without_writes(self.onboard)
        self.assertEqual(outside.read_bytes(), original)

    def test_corrupted_source_cannot_become_a_trusted_snapshot(self):
        import shutil
        source = self.target.parent / "corrupted-source"
        shutil.copytree(self.artifact, source)
        policy = source / "shared/WORKFLOW.md"
        policy.write_text(policy.read_text() + "\nUnreviewed policy addition.\n")
        self.assert_rejected_without_writes(lambda: self.generate(source=source))

    def test_wrong_manifest_identity_is_rejected(self):
        self.assert_rejected_without_writes(lambda: self.generate(manifest_sha="0" * 64))

    def test_moving_or_abbreviated_source_revision_is_rejected(self):
        for revision in ("main", self.source_sha[:7]):
            with self.subTest(revision=revision):
                self.assert_rejected_without_writes(lambda: self.generate(source_sha=revision))

    def test_corrupted_native_verification_skill_is_rejected(self):
        import shutil
        source = self.target.parent / "corrupted-native-source"
        shutil.copytree(self.artifact, source)
        native = source / VERIFICATION_SKILL
        native.write_text(native.read_text() + "\nUnreviewed native addition.\n")
        self.assert_rejected_without_writes(lambda: self.generate(source=source))

    def test_checkpoint_reserved_paths_cannot_replace_managed_outputs(self):
        self.generate()
        for checkpoint in ("AGENTS.md", "./PROJECT.md", NATIVE_INSTRUCTIONS, ".conductor",
                           ".conductor/policy",
                           ".conductor/policy/" + self.source_sha + "/shared/WORKFLOW.md",
                           NATIVE_SKILLS + "/conductor-project-init/SKILL.md", ".git/config"):
            with self.subTest(checkpoint=checkpoint):
                self.assert_rejected_without_writes(lambda: self.onboard(
                    facts=dict(self.facts, checkpoint=checkpoint)))

    def test_closed_markdown_and_table_declarations_are_respected(self):
        self.generate()
        for declaration in ('- **Lifecycle:** Closed', '- Lifecycle: "Closed"',
                            '| Lifecycle | Closed |'):
            with self.subTest(declaration=declaration):
                (self.target / 'PROJECT.md').write_text(declaration + '\n')
                self.assert_rejected_without_writes(self.onboard)

    def test_existing_parked_project_does_not_become_active(self):
        self.generate()
        (self.target / 'PROJECT.md').write_text('- **Lifecycle:** Parked\n')
        self.assert_rejected_without_writes(self.onboard)

    def test_existing_markdown_owner_requires_reconciliation(self):
        self.generate()
        for declaration in ('- **Owner:** Bob', '| Assigned to | Bob |'):
            with self.subTest(declaration=declaration):
                (self.target / 'PROJECT.md').write_text(declaration + '\n')
                self.assert_rejected_without_writes(self.onboard)

    def test_custom_verification_skill_is_preserved_as_whole_directory(self):
        self.generate()
        skill = self.target / NATIVE_SKILLS / 'project-verification'
        skill.mkdir(parents=True)
        custom = skill / 'SKILL.md'
        custom.write_text('Custom verification instructions.\n')
        before = tree_state(skill)
        result = self.onboard()
        self.assertEqual(result['status'], 'installed')
        self.assertTrue(result['notes'])
        self.assertEqual(tree_state(skill), before)

    def test_modified_generation_pin_cannot_mislabel_policy(self):
        self.generate()
        path = self.skill_root / 'generation.json'
        metadata = json.loads(path.read_text())
        metadata['policy_commit'] = 'f' * 40
        path.write_text(json.dumps(metadata))
        self.assert_rejected_without_writes(self.onboard)

    def test_generation_metadata_requires_complete_asset_coverage(self):
        self.generate()
        path = self.skill_root / 'generation.json'
        metadata = json.loads(path.read_text())
        del metadata['files']['assets/source/shared/WORKFLOW.md']
        path.write_text(json.dumps(metadata))
        self.assert_rejected_without_writes(self.onboard)

    def test_project_generation_rejects_global_scope(self):
        profile = dict(self.capabilities, scope='global')
        self.assert_rejected_without_writes(lambda: self.generate(capabilities=profile))

    def test_artifact_without_bound_checksums_needs_independent_native_identity(self):
        import shutil
        source = self.target.parent / 'unbound-source'
        shutil.copytree(self.artifact, source)
        checksums = 'assistants/claude-code/SHA256SUMS'
        manifest = json.loads((source / 'MANIFEST.json').read_text())
        del manifest['files'][checksums]
        (source / 'MANIFEST.json').write_text(json.dumps(manifest, indent=2) + '\n')
        manifest_sha = hashlib.sha256((source / 'MANIFEST.json').read_bytes()).hexdigest()
        self.assert_rejected_without_writes(
            lambda: self.generate(source=source, manifest_sha=manifest_sha))
        profile = dict(self.capabilities, source_native_checksums_sha256=hashlib.sha256(
            (source / checksums).read_bytes()).hexdigest())
        result = self.generate(source=source, manifest_sha=manifest_sha, capabilities=profile)
        self.assertEqual(result['status'], 'installed')

    def test_non_directory_managed_ancestor_is_rejected_before_writes(self):
        (self.target / NATIVE_SKILLS.split("/")[0]).write_text('User file, not a directory\n')
        self.assert_rejected_without_writes(self.generate)

    def test_atomic_replacement_failure_preserves_original_and_restores_prior_writes(self):
        from unittest.mock import patch
        self.generate()
        original = b'Original project rules\n'
        (self.target / 'AGENTS.md').write_bytes(original)
        replace = initializer.os.replace
        def fail_native(source, destination):
            if Path(destination).name == 'AGENTS.md':
                raise OSError('simulated replacement failure')
            return replace(source, destination)
        with patch.object(initializer.os, 'replace', side_effect=fail_native):
            with self.assertRaises(OSError):
                self.onboard()
        self.assertEqual((self.target / 'AGENTS.md').read_bytes(), original)
        self.assertFalse((self.target / 'PROJECT.md').exists())
        self.assertFalse((self.target / '.conductor/policy' / self.source_sha / 'shared/WORKFLOW.md').exists())
        self.assertFalse(list(self.target.rglob('.conductor-write-*')))

    def test_new_custom_owner_conflict_is_respected_on_repeat_adoption(self):
        self.generate()
        facts = dict(self.facts, owner={'name': 'Alice', 'ref': 'TASKS.md', 'confirmed': True})
        self.assertEqual(self.onboard(facts=facts)['status'], 'installed')
        project = self.target / 'PROJECT.md'
        project.write_text(project.read_text() + '\n- **Owner:** Bob\n')
        self.assert_rejected_without_writes(lambda: self.onboard(facts=facts))

    def git_source_fixture(self):
        import shutil
        source = self.target.parent / 'git-source'
        shutil.copytree(self.artifact, source)
        (source / '.gitattributes').write_text('*.md filter=fixture-unsafe\n')
        def git(*args):
            return subprocess.check_output(['git', '-c', 'core.hooksPath=/dev/null',
                '-c', 'commit.gpgsign=false', '-c', 'user.name=Fixture',
                '-c', 'user.email=fixture@example.invalid', '-C', str(source), *args],
                stderr=subprocess.PIPE).decode().strip()
        git('init', '--quiet')
        git('add', '.')
        git('commit', '--quiet', '-m', 'Disposable reviewed policy fixture')
        return source, git('rev-parse', 'HEAD'), git

    def test_clean_git_source_verifies_raw_blobs_without_artifact_digests(self):
        source, sha, _ = self.git_source_fixture()
        result = self.generate(source=source, source_sha=sha, manifest_sha=None)
        self.assertEqual(result['status'], 'installed')
        metadata = json.loads((self.skill_root / 'generation.json').read_text())
        self.assertEqual(metadata['policy_commit'], sha)
        self.assertEqual((self.skill_root / 'assets/source/shared/WORKFLOW.md').read_bytes(),
                         (source / 'shared/WORKFLOW.md').read_bytes())

    def test_dirty_git_source_rejected_without_executing_configured_filter(self):
        import shlex
        source, sha, git = self.git_source_fixture()
        marker = self.target.parent / 'FILTER_WAS_RUN'
        code = "from pathlib import Path; Path(" + repr(str(marker)) + ").write_text('bad')"
        git('config', 'filter.fixture-unsafe.clean', 'python3 -c ' + shlex.quote(code))
        git('config', 'core.fsmonitor', 'python3 -c ' + shlex.quote(code))
        policy = source / 'shared/WORKFLOW.md'
        policy.write_text(policy.read_text() + '\nUnreviewed source edit.\n')
        self.assert_rejected_without_writes(lambda: self.generate(
            source=source, source_sha=sha, manifest_sha=None))
        self.assertFalse(marker.exists())

    def test_staged_git_source_change_rejected_even_when_file_bytes_restored(self):
        source, sha, git = self.git_source_fixture()
        file = source / 'shared/WORKFLOW.md'
        original = file.read_bytes()
        file.write_bytes(original + b'\nStaged change.\n')
        git('add', 'shared/WORKFLOW.md')
        file.write_bytes(original)
        self.assert_rejected_without_writes(lambda: self.generate(
            source=source, source_sha=sha, manifest_sha=None))

    def test_matching_custom_owner_preserves_exact_repeat_noop(self):
        self.generate()
        facts = dict(self.facts, owner={'name': 'Alice', 'ref': 'TASKS.md', 'confirmed': True})
        self.onboard(facts=facts)
        project = self.target / 'PROJECT.md'
        project.write_text(project.read_text() + '\n- Owner: Alice\n')
        before = tree_state(self.target)
        self.assertEqual(self.onboard(facts=facts)['status'], 'unchanged')
        self.assertEqual(tree_state(self.target), before)

    def test_reviewed_generator_update_keeps_policy_pin_and_custom_files(self):
        import shutil
        from unittest.mock import patch
        self.generate()
        scratch = self.target.parent / 'new-generator'
        package = IMPL.parent.parent
        shutil.copytree(package, scratch)
        template = scratch / 'assets/project-skill.md'
        template.write_text(template.read_text() + '\nReviewed template clarification.\n')
        before = tree_state(self.target)
        with patch.object(initializer, '__file__', str(scratch / 'scripts/conductor_init.py')):
            blocked = self.generate()
            self.assertEqual(blocked['status'], 'blocked')
            self.assertEqual(tree_state(self.target), before)
            planned = self.generate(apply=False, update=True)
            self.assertEqual(planned['status'], 'planned')
            self.assertEqual(tree_state(self.target), before)
            installed = self.generate(update=True)
            self.assertEqual(installed['status'], 'installed')
            metadata = json.loads((self.skill_root / 'generation.json').read_text())
            self.assertEqual(metadata['policy_commit'], self.source_sha)
            self.assertEqual(self.generate(update=True)['status'], 'unchanged')
        self.assertEqual((self.target / 'TASKS.md').read_bytes(), before['TASKS.md'][0])


if __name__ == "__main__":
    unittest.main()
