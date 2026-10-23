#!/usr/bin/env python3
"""Portable two-stage Conductor setup. Standard library only; never runs workloads."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import subprocess
import tempfile
import textwrap
import uuid


class InitError(Exception):
    """A trust, ownership, or path invariant prevents setup."""


BEGIN = "<!-- conductor:init:begin -->"
END = "<!-- conductor:init:end -->"
SKILL_NAME = "conductor-project-init"
# Verified native mappings. Policy stays canonical; only entrypoints and discovery differ.
# This table is the only place the helper names a product; adoption records written by
# earlier generators may name LEGACY_ASSISTANT and are read as data so they can migrate.
PROFILES = {
    "claude-code": {
        "label": "Claude Code", "native_skills": ".claude/skills", "native_instructions": "CLAUDE.md",
        "kit": "assistants/claude-code", "checksums": "assistants/claude-code/SHA256SUMS",
        "verification_skill": "assistants/claude-code/project/skills/project-verification",
        "verification_assets": ("SKILL.md",),
        "ui_metadata": False, "invocation": "/conductor-project-init",
    },
}
DEFAULT_PROFILE = "claude-code"
LEGACY_ASSISTANT = "codex"
# The pinned snapshot is the policy tree only: the common workflow and the files it links.
SNAPSHOT_PREFIX = "shared/"

# Adapter profiles generate always-on instruction text for a runtime from an existing
# adoption record. They need no generated skill and no source tree: PROJECT.md facts,
# .conductor/adoption.json and the pinned policy file inside the project are the inputs.
ADAPTER_DIR = ".conductor/adapters"
ADAPTER_PROFILES = {
    "claude-code-projects": {
        "label": "Claude Code Projects", "native_profile": "claude-code",
        "instructions_limit": 16000,
        "instructions": "project-instructions.md", "checklist": "OWNER-CHECKLIST.md",
        "boundary_skills": ("task-start", "task-finish"),
        "backlog_variable": "CONDUCTOR_BACKLOG_REVIEW_ISSUE",
    },
}
ADAPTER_DEFAULTS = {"default_branch": "main", "max_parallel_threads": 2, "integration_branch": None}
# Approval modes (ADR 0005): the project fact `approval_mode` in PROJECT.md, `manual` when
# absent. `auto` delegates everything below a top-level record to the assistants and GitHub;
# the generator refuses it until the adoption record holds the branch protection evidence.
APPROVAL_MODES = ("manual", "auto")
REQUIRED_CHECKS = ("verify", "linked-task")
APPROVAL_MODE_VARIABLE = "CONDUCTOR_APPROVAL_MODE"
INTEGRATION_BRANCH_VARIABLE = "CONDUCTOR_INTEGRATION_BRANCH"

# Source of the Claude Code Projects project-instructions text. The kit copy
# assistants/claude-code/PROJECT-INSTRUCTIONS.template.md is generated from this constant
# by tests/package_conductor_init.py; edit it here.
PROJECT_INSTRUCTIONS_TEMPLATE = """\
This project is {{PROJECT_NAME}}: {{ONE_LINE_GOAL}}. Work happens in {{REPOSITORY}} and the task
records at {{TASK_RECORDS_URL}}. Shared practice is the pinned policy at
`{{POLICY_SNAPSHOT_PATH}}` (SHA-256 `{{POLICY_SHA256}}`) inside the clone, plus the repository's
`AGENTS.md` and `PROJECT.md`. Read them before dependent work; if the snapshot is missing or its
digest differs, say so in your first message and stop.

Roles

- The coordinator is the Planner: it files and grills task records and proposes threads. A
  thread is the Implementer of exactly one task. A thread asked to review a pull request is
  the Reviewer and changes nothing. {{GATES_SENTENCE}}

Tasks and ownership

- Every thread starts from one labelled task record that carries `status:ready`. {{FILING_RULE}}
  If the record is not ready, say so and stop.
- Before changing anything, record the claim on the task record: this project, the thread
  reference, the time and your role. Do not treat labels or a note as an exclusive lock.
- Take exactly the task you were given. Anything found mid-task is proposed and left as a
  comment on the record it belongs to.
- Each task carries exactly one priority and exactly one category before it is worked.

Task boundaries

- Start with `/task-start #N` when that skill is in your skill list. Without it, do the same
  by hand: refuse without `status:ready` on #N and name the missing Ready fact; post the claim
  comment on #N (runtime, thread reference, time, role) before changing anything; branch from
  `{{INTEGRATION_BRANCH}}`; write `.git/conductor-local/claim.json` with the task number, the
  branch and the allowed paths copied from the record, and stay inside those paths.
- Finish with `/task-finish`, or `/task-finish --stopped` when blocked. Without the skill:
  run the verification contract below on the exact head and write
  `.git/conductor-local/verification.json` with the tested SHAs; open or update the pull
  request with `Closes #N` and the ledger; update the checkpoint with branch, head, task and
  next action; post the milestone on #N; list anything found mid-task under "Found and left"
  on the record. When stopping, post the blocker and the next step and open no pull request.

Branches and pull requests

- Branch from `{{INTEGRATION_BRANCH}}` and open the pull request against it. One branch and
  one pull request per thread, closing exactly the task it names with `Closes #N`.
- Open the pull request only when the task's acceptance is met and the verification below has
  run on the exact head; fill the repository's pull request template, including the
  verification table with tested SHAs.
- Never merge by hand, never mark a draft ready, never approve, force-push, rewrite history,
  edit branch protection or required checks, or push to {{PROTECTED_BRANCHES}} without a pull
  request. {{MERGE_RULE}} Commit and push work in progress on long tasks; a resumed sandbox can
  lose uncommitted changes.

Verification before done

- Run, from the repository root: {{VERIFICATION_COMMANDS}}. Paste the result lines and the
  tested SHA in your final message and in the pull request.
- A claim without the recorded command is not verification. Do not infer commands from another
  repository or from memory.

When something is missing

- If you cannot reach a repository, file, secret, service, connector, or the pinned policy, say
  exactly what is missing in your first message and stop. Do not substitute, mock, or guess.
- Pause for the owner before any deployment, spending, credential or access change,
  publication outside GitHub, or destructive action.

Checkpoints and memory

- Before ending, or when context runs low, update `{{CHECKPOINT_PATH}}` with head SHA, checks
  run, decisions, blocker, and next action, and post the milestone on the task record.
- Decisions go to the task record or the repository's decision records; pitfalls go to the
  repository's docs or `CLAUDE.md`. Project memory may hold reminders of them, but it is not
  the record and can be pruned without loss.

Coordination

- Propose threads and wait for the owner's go-ahead before starting them, and run at most
  {{MAX_PARALLEL_THREADS}} threads at a time. Parallel threads need distinct task records and
  separate branches, and a conflict review for files, APIs, migrations, services, or data they
  share.
- Post when a thread finishes, is blocked, or needs the owner; do not narrate each step.
"""

PROJECT_INSTRUCTIONS_HEADING = """\
# Project instructions template for Claude Code Projects

Source template for the **Project settings > Memory > Project instructions** field of a Claude
Code project (beta). Generated copy: the text below is `PROJECT_INSTRUCTIONS_TEMPLATE` in
`shared/skills/conductor-init/scripts/conductor_init.py`, and `tests/package_conductor_init.py
--write` regenerates this file; edit the generator, not this file. Do not fill it by hand: run
`conductor_init.py generate --profile claude-code-projects --target <repo>` in an adopted
repository. That fills every `{{PLACEHOLDER}}` from `PROJECT.md`, `.conductor/adoption.json` and
the pinned policy, writes the text to `.conductor/adapters/claude-code-projects/` with an owner
checklist, records the text's SHA-256 in `.conductor/adoption.json`, and refuses a text over the
field's 16,000 characters. The field is not in Git: `check --profile claude-code-projects`
compares the recorded digest with the generated text and the file on disk and names what
differs. Repository rules stay in that repository's `CLAUDE.md`; shared policy stays the pinned
snapshot named below. Project memory is notes Claude writes for itself, never policy.

---

"""



def profile_for(capabilities):
    """Return the verified native profile for a capability record, or None."""
    name = capabilities.get("assistant")
    spec = PROFILES.get(name)
    if not spec:
        return None
    verified = (capabilities.get("verified") is True
                and capabilities.get("native_skills") == spec["native_skills"]
                and capabilities.get("native_instructions") == spec["native_instructions"]
                and capabilities.get("scope", "project") == "project"
                and capabilities.get("execution") in ("local", "cloud")
                and bool(capabilities.get("surface")) and bool(capabilities.get("evidence_ref")))
    return dict(spec, name=name) if verified else None


def native_root(spec):
    return spec["native_skills"] + "/" + SKILL_NAME


def native_checksums(metadata):
    """Earlier single-profile generators recorded the checksum identity under a legacy key."""
    return metadata.get("native_checksums_sha256", metadata.get(f"source_{LEGACY_ASSISTANT}_checksums_sha256"))


def digest(data):
    return hashlib.sha256(data).hexdigest()


def encoded(value):
    return (json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False) + "\n").encode()


def safe(root, relative):
    """Reject links and traversal before reading or planning any managed file."""
    root = Path(root).absolute()
    p = PurePosixPath(str(relative))
    if not str(relative) or p.is_absolute() or ".." in p.parts or "\\" in str(relative):
        raise InitError(f"Unsafe project-relative path: {relative}")
    if root.is_symlink():
        raise InitError("Root is a symlink; use its explicit canonical directory")
    root = root.resolve()
    if root.exists() and not root.is_dir():
        raise InitError("Target root is not a directory")
    current = root
    for index, part in enumerate(p.parts):
        current /= part
        if current.is_symlink():
            raise InitError(f"Symlink in managed path: {relative}")
        if index < len(p.parts) - 1 and current.exists() and not current.is_dir():
            raise InitError(f"Non-directory ancestor in managed path: {relative}")
    return current


def read(root, relative):
    path = safe(root, relative)
    if path.exists() and not path.is_file():
        raise InitError(f"Expected a regular file: {relative}")
    return path.read_bytes() if path.exists() else None


def load(root, relative):
    data = read(root, relative)
    if data is None:
        raise InitError(f"Missing required file: {relative}")
    try:
        return json.loads(data)
    except (ValueError, UnicodeError) as exc:
        raise InitError(f"Invalid JSON: {relative}") from exc


def git(source, *args):
    result = subprocess.run(["git", "--no-pager", "-c", "core.fsmonitor=false", "-C", str(source), *args], capture_output=True)
    if result.returncode:
        raise InitError("Pinned Git source is unavailable or inconsistent")
    return result.stdout


def verified_source(source, sha, capabilities, manifest_sha=None, spec=None):
    spec = spec or dict(PROFILES[DEFAULT_PROFILE], name=DEFAULT_PROFILE)
    if not re.fullmatch(r"[0-9a-f]{40}", sha):
        raise InitError("Source revision must be an immutable full commit SHA")
    manifest_data = read(source, "MANIFEST.json")
    if not manifest_data:
        raise InitError("Source has no manifest")
    manifest = load(source, "MANIFEST.json")
    files = dict(manifest["files"])
    files["MANIFEST.json"] = digest(manifest_data)
    checks = read(source, spec["checksums"])
    if not checks:
        raise InitError(f"Source has no native {spec['label']} checksums")
    # A reviewed artifact needs independent identities, not a digest it reports itself.
    if manifest_sha is not None:
        if digest(manifest_data) != manifest_sha:
            raise InitError("Artifact manifest identity mismatch")
        bound = files.get(spec["checksums"])
        expected = bound or capabilities.get("source_native_checksums_sha256")
        if not expected and spec["name"] == LEGACY_ASSISTANT:
            expected = capabilities.get(f"source_{LEGACY_ASSISTANT}_checksums_sha256")
        if not expected or digest(checks) != expected:
            raise InitError(f"Independent {spec['label']} checksum identity required or mismatched")
    else:
        if git(source, "rev-parse", "HEAD").decode().strip() != sha:
            raise InitError("Git source HEAD does not match the requested pin")
        # Do not use status/diff on working files: configured clean/process filters
        # can execute repository code. Compare the index/tree and raw bytes instead.
        tree = {}
        for entry in git(source, "ls-tree", "-rz", "--full-tree", sha).split(b"\0"):
            if not entry:
                continue
            info, relative = entry.split(b"\t", 1)
            mode, kind, blob = info.split()
            if kind != b"blob" or mode not in (b"100644", b"100755"):
                raise InitError("Source contains a link or submodule; use a reviewed regular-file artifact")
            tree[relative] = (mode, blob)
        index = {}
        for entry in git(source, "ls-files", "--stage", "-z").split(b"\0"):
            if not entry:
                continue
            info, relative = entry.split(b"\t", 1)
            mode, blob, stage = info.split()
            if stage != b"0":
                raise InitError("Source index contains unresolved conflicts")
            index[relative] = (mode, blob)
        if index != tree or git(source, "ls-files", "--others", "--exclude-standard", "-z"):
            raise InitError("Use a clean Git source or a reviewed artifact with external digests")
        for relative, (mode, _) in tree.items():
            key = relative.decode()
            data = read(source, key)
            if data != git(source, "show", f"{sha}:{key}"):
                raise InitError(f"Working source differs from pinned Git blob: {key}")
            if bool(safe(source, key).stat().st_mode & 0o111) != (mode == b"100755"):
                raise InitError(f"Working source mode differs from its pin: {key}")
    files[spec["checksums"]] = digest(checks)
    for line in checks.decode().splitlines():
        if not line.strip():
            continue
        match = re.fullmatch(r"([0-9a-f]{64})\s+\*?(.+)", line)
        if not match:
            raise InitError(f"Invalid {spec['label']} checksum entry")
        key = spec["kit"] + "/" + match[2]
        if key in files and files[key] != match[1]:
            raise InitError(f"Conflicting source digests: {key}")
        files[key] = match[1]
    required = ["shared/WORKFLOW.md", "shared/templates/HANDOFF.md",
                "shared/harness/run-contract.schema.json"]
    required.extend(spec["verification_skill"] + "/" + asset for asset in spec["verification_assets"])
    if any(key not in files for key in required):
        raise InitError("Manifest does not cover required policy and native assets")
    contents = {}
    for relative, expected in files.items():
        data = read(source, relative)
        if data is None or digest(data) != expected:
            raise InitError(f"Source digest mismatch: {relative}")
        if manifest_sha is None and git(source, "show", f"{sha}:{relative}") != data:
            raise InitError(f"Source differs from pinned Git blob: {relative}")
        contents[relative] = data
    return contents


def result(status, changes=None, blockers=None, **extra):
    return {"status": status, "changes": changes or [], "blockers": blockers or [], **extra}


def atomic_write(path, data):
    """Keep the original intact until a complete replacement is ready."""
    path.parent.mkdir(parents=True, exist_ok=True)
    mode = path.stat().st_mode & 0o777 if path.exists() else 0o600
    fd, name = tempfile.mkstemp(prefix=".conductor-write-", dir=path.parent)
    try:
        with os.fdopen(fd, "wb") as stream:
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        os.chmod(name, mode)
        os.replace(name, path)
    finally:
        if os.path.exists(name):
            os.unlink(name)


def prune_empty(target, directory):
    """Remove directories left empty by a removal, never the project root."""
    root = Path(target).resolve()
    directory = Path(directory).resolve()
    while directory != root and root in directory.parents and directory.is_dir() and not any(directory.iterdir()):
        directory.rmdir()
        directory = directory.parent


def apply_plan(target, outputs, apply):
    """Preflight all paths, save real previous contents, then write or remove changed files.

    A value of None removes the file; removals are backed up exactly like updates."""
    changed = {}
    before = {}
    for relative, data in sorted(outputs.items()):
        old = read(target, relative)
        if old != data:
            changed[relative] = data
            before[relative] = old
    if not changed:
        return result("unchanged")
    changes = [{"path": key, "action": "remove" if changed[key] is None
                else "create" if before[key] is None else "update"} for key in changed]
    if not apply:
        return result("planned", changes)
    base = ".conductor/backups/" + uuid.uuid4().hex
    transaction = {"version": 1, "files": {}}
    for key, data in changed.items():
        backup = base + "/before/" + key if before[key] is not None else None
        transaction["files"][key] = {
            "before": digest(before[key]) if before[key] is not None else None,
            "after": digest(data) if data is not None else None, "backup": backup,
        }
        if backup:
            path = safe(target, backup)
            atomic_write(path, before[key])
    record = base + "/transaction.json"
    path = safe(target, record)
    atomic_write(path, encoded(transaction))
    written = []
    try:
        for key, data in changed.items():
            path = safe(target, key)
            if data is None:
                path.unlink()
                prune_empty(target, path.parent)
            else:
                atomic_write(path, data)
            written.append(key)
    except OSError:
        # Restore only writes from this operation. The recorded transaction survives.
        for key in reversed(written):
            path = safe(target, key)
            if before[key] is None:
                path.unlink()
            else:
                atomic_write(path, before[key])
        raise
    return result("installed", changes, transaction=record)


def owned_outputs(target, outputs, old_hashes):
    for key, data in outputs.items():
        previous = read(target, key)
        if previous is not None and previous != data:
            if key not in old_hashes or digest(previous) != old_hashes[key]:
                raise InitError(f"Existing file is custom or edited: {key}")


def check_generated(root, metadata):
    sha = metadata["policy_commit"]
    spec = profile_for(metadata["capabilities"])
    if (not re.fullmatch(r"[0-9a-f]{40}", sha) or metadata.get("scope") != "project"
            or metadata.get("version") != 1 or not spec):
        raise InitError("Invalid generated skill binding or capability profile")
    source_files = verified_source(root / "assets/source", sha, {
        "source_native_checksums_sha256": native_checksums(metadata)
    }, metadata["policy_manifest_sha256"], spec)
    expected = {"assets/source/" + key for key in source_files}
    expected.update(("SKILL.md", "scripts/conductor_init.py"))
    if spec["ui_metadata"]:
        expected.add("agents/openai.yaml")
    if set(metadata["files"]) != expected:
        raise InitError("Generated asset coverage differs from its pinned source")
    for relative, expected in metadata["files"].items():
        data = read(root, relative)
        if data is None or digest(data) != expected:
            raise InitError(f"Generated skill was changed: {relative}")
    skill = read(root, "SKILL.md")
    if (f"`{sha}`".encode() not in skill
            or digest(read(root, "scripts/conductor_init.py")) != metadata["generator_sha256"]):
        raise InitError("Generated skill pin or generator identity differs from metadata")
    return source_files, spec


def locate_generated(target, skill_root=None):
    """Find the generated skill: explicit root, the running helper's own skill, or the only one present."""
    if skill_root:
        return Path(skill_root)
    own = Path(__file__).absolute().parent.parent
    if (own / "generation.json").is_file():
        return own
    found = [safe(target, native_root(spec)) for spec in PROFILES.values()
             if read(target, native_root(spec) + "/generation.json")]
    if len(found) != 1:
        raise InitError(f"Specify the generated skill root; found {len(found)} generated initializers")
    return found[0]


def build_generation(spec, source_files, source_sha, profile):
    """Outputs of a native generated skill for a verified source, plus its metadata."""
    package = Path(__file__).absolute().parent.parent
    outputs = {"assets/source/" + key: value for key, value in source_files.items()}
    outputs["scripts/conductor_init.py"] = Path(__file__).read_bytes()
    template = read(package, "assets/project-skill.md")
    if template is None:
        raise InitError("Generic generator template missing; invoke stage one from the source skill")
    skill = template
    for placeholder, value in (("@SOURCE_SHA@", source_sha), ("@ASSISTANT@", spec["label"]),
                               ("@NATIVE_SKILLS@", spec["native_skills"]), ("@INVOCATION@", spec["invocation"])):
        skill = skill.replace(placeholder.encode(), value.encode())
    outputs["SKILL.md"] = skill
    if spec["ui_metadata"]:
        outputs["agents/openai.yaml"] = (
            'interface:\n  display_name: "Conductor Project Init"\n'
            '  short_description: "Onboard a project to pinned Conductor policy"\n'
            '  default_prompt: "Use $conductor-project-init to onboard this project."\n').encode()
    metadata = {"version": 1, "scope": "project", "assistant": spec["name"], "policy_commit": source_sha,
                "policy_manifest_sha256": digest(source_files["MANIFEST.json"]),
                "native_checksums_sha256": digest(source_files[spec["checksums"]]),
                "capabilities": profile, "generator_sha256": digest(outputs["scripts/conductor_init.py"]),
                "template_sha256": digest(template),
                "files": {key: digest(value) for key, value in outputs.items()}}
    if spec["name"] == LEGACY_ASSISTANT:
        # Earlier single-profile generators recorded this key; keep it so their pins stay recognizable.
        metadata[f"source_{LEGACY_ASSISTANT}_checksums_sha256"] = metadata["native_checksums_sha256"]
    outputs["generation.json"] = encoded(metadata)
    return outputs, metadata


def generate(target, source, source_sha, capabilities, apply=False, manifest_sha=None, update=False):
    target, source = Path(target), Path(source)
    profile = capabilities
    spec = profile_for(profile)
    if not spec:
        supported = " or ".join(item["label"] for item in PROFILES.values())
        return result("draft", blockers=[f"Verify a native capability mapping; this helper supports project-scoped {supported} only"])
    native = native_root(spec)
    safe(target, native)
    source_files = verified_source(source, source_sha, profile, manifest_sha, spec)
    outputs, metadata = build_generation(spec, source_files, source_sha, profile)
    root = safe(target, native)
    old = load(root, "generation.json") if read(root, "generation.json") else None
    if old:
        check_generated(root, old)
        if old != metadata:
            same_pin = (all(old.get(key) == metadata.get(key) for key in (
                "policy_commit", "policy_manifest_sha256", "capabilities"))
                and native_checksums(old) == native_checksums(metadata))
            if not update or not same_pin:
                return result("blocked", blockers=["Existing generation differs; use a reviewed --update for generator changes at the same policy/capability pin, or 'migrate' to move the adoption to a new policy source"])
    hashes = dict(old["files"]) if old else {}
    if old:
        hashes["generation.json"] = digest(read(root, "generation.json"))
    owned_outputs(root, outputs, hashes)
    return apply_plan(target, {native + "/" + key: value for key, value in outputs.items()}, apply)


def block(data):
    if data is None:
        return None
    text = data.decode()
    if BEGIN not in text and END not in text:
        return None
    if text.count(BEGIN) != 1 or text.count(END) != 1:
        raise InitError("Ambiguous managed instruction markers")
    start, finish = text.index(BEGIN), text.index(END)
    if finish < start:
        raise InitError("Invalid managed instruction marker order")
    return text[start:finish + len(END)].encode()


def append_block(previous, body):
    managed = (BEGIN + "\n" + body + "\n" + END).encode()
    current = block(previous)
    if current is not None:
        return previous.replace(current, managed), managed
    prefix = previous or b""
    return prefix + (b"\n\n" if prefix else b"") + managed + b"\n", managed


def facts_blockers(target, facts):
    missing = [key for key in ("name", "purpose", "repository", "task_records", "checkpoint")
               if not facts.get(key)]
    if facts.get("kind") not in ("software", "analytics"):
        missing.append("kind: software or analytics")
    if facts.get("lifecycle") not in ("Active", "Parked", "Closed"):
        missing.append("lifecycle: Active, Parked, or Closed")
    if facts.get("approval_mode") is not None and facts["approval_mode"] not in APPROVAL_MODES:
        missing.append("approval_mode: " + " or ".join(APPROVAL_MODES))
    if not facts.get("verification"):
        missing.append("evidenced verification contract")
    if missing:
        return ["Missing essential facts: " + ", ".join(missing)]
    checkpoint = str(PurePosixPath(facts["checkpoint"]))
    safe(target, checkpoint)
    reserved_roots = {"AGENTS.md", "PROJECT.md", "AGENTS.override.md", ".git"}
    for spec in PROFILES.values():
        reserved_roots.update((spec["native_instructions"], spec["native_skills"].split("/")[0]))
    if (checkpoint in (".", ".conductor", ".conductor/policy", ".conductor/backups")
            or checkpoint.split("/")[0] in reserved_roots
            or checkpoint == ".conductor/adoption.json"
            or checkpoint.startswith((".conductor/policy/", ".conductor/backups/"))):
        raise InitError("Checkpoint collides with a reserved managed/configuration path")
    for reference in facts["task_records"]:
        if "://" not in reference and read(target, reference) is None:
            missing.append("authoritative task record " + reference)
    for contract in facts["verification"]:
        if not all(contract.get(key) for key in ("name", "command", "cwd", "prerequisites", "expected", "source")):
            missing.append("complete verification contract")
            continue
        safe(target, contract["cwd"])
        if read(target, contract["source"]) is None:
            missing.append("verification evidence " + contract["source"])
    owner = facts.get("owner")
    if owner and (owner.get("confirmed") is not True or not owner.get("name") or not owner.get("ref")):
        missing.append("confirmed owner and authoritative assignment reference")
    return ["Unresolved: " + value for value in missing]


def existing_declarations(data, field):
    """Recognize ordinary bullets, emphasis, JSON-like values and Markdown tables."""
    if not data:
        return []
    text = data.decode()
    text = re.sub(r"[*_`\"']", "", text)
    matches = re.findall(r"\b" + field + r"\s*(?::|\|)\s*([^\n|]+)", text, re.I)
    return [item.strip() for item in matches if item.strip()]


def project_record(facts):
    lines = ["# Conductor project facts", ""]
    for key in ("name", "kind", "purpose", "repository", "lifecycle"):
        lines.append(f"- {key.title()}: {facts[key]}")
    if facts.get("approval_mode"):
        lines.append(f"- Approval mode: {facts['approval_mode']}")
    links = ", ".join(f"[{value}]({value})" for value in facts["task_records"])
    lines.append("- Authoritative tasks: " + links)
    lines.append(f"- Checkpoint: [{facts['checkpoint']}]({facts['checkpoint']})")
    for key, value in facts.items():
        if key not in ("name", "kind", "purpose", "repository", "lifecycle", "approval_mode",
                       "task_records", "checkpoint", "verification"):
            lines.append(f"- {key.replace('_', ' ').title()}: {json.dumps(value, ensure_ascii=False)}")
    lines.extend(("", "## Verification contract", ""))
    for check in facts["verification"]:
        lines.append(f"- {check['name']}: `{check['command']}` from `{check['cwd']}`; "
                     f"prerequisites: {check['prerequisites']}; expected: {check['expected']}; "
                     f"evidence: [{check['source']}]({check['source']}).")
    lines.extend(("", "Task progress: Backlog / Ready / In progress / Review / Done.",
                  "Execution state: Ready / Running / Waiting quota / Blocked / Needs approval / null.",
                  "Done requires verification, review and null execution state. Task records remain authoritative;",
                  "labels do not acquire ownership or locks. Missing optional facts remain unknown."))
    return "\n".join(lines)


def native_adapter(spec, previous, always_on=None):
    """Thin native instruction section; project facts stay in the shared AGENTS.md.

    always_on: the lines an adapter profile adds to this file (see always_on_lines)."""
    text = (previous or b"").decode()
    current = block(previous)
    outside = text.replace(current.decode(), "") if current else text
    imports = "" if re.search(r"^@AGENTS\.md\s*$", outside, re.M) else "@AGENTS.md\n\n"
    body = (f"# Conductor {spec['label']} adapter\n\n" + imports +
            "Project facts, policy binding and verification contract are in the imported `AGENTS.md` and in `PROJECT.md`; nothing is restated here.\n"
            f"Native skills: `{native_root(spec)}` for setup and `{spec['native_skills']}/project-verification` for recorded checks.\n"
            "Explicit task limits in `AGENTS.md` or the checkpoint take precedence over inherited commit, push, worktree or delegation defaults.")
    if always_on:
        body += "\n\n" + "\n".join(always_on)
    return body


def approval_mode(facts, override=None):
    """The project's approval mode: the override, else the fact, else manual."""
    mode = override or facts.get("approval_mode") or APPROVAL_MODES[0]
    if mode not in APPROVAL_MODES:
        raise InitError("approval_mode must be one of " + ", ".join(APPROVAL_MODES))
    return mode


def protected_branches(default_branch, integration_branch):
    """The branches a pull request lands on, default branch last, each named once."""
    branches = [integration_branch] if integration_branch != default_branch else []
    return branches + [default_branch]


def branch_phrase(default_branch, integration_branch):
    return " or ".join(f"`{name}`" for name in protected_branches(default_branch, integration_branch))


def mode_text(mode, default_branch, integration_branch):
    """The mode-dependent sentences of the project instructions and the always-on lines."""
    promotion = (f" and promotes `{integration_branch}` into `{default_branch}`"
                 if integration_branch != default_branch else "")
    if mode == "manual":
        return {
            "GATES_SENTENCE": "The owner alone files, readies and merges (approval mode `manual`).",
            "FILING_RULE": ("If no record exists for what you were asked, propose the title, the problem in one or two "
                            "sentences and the open record it belongs to, then wait; do not file it. The owner files work "
                            "related to an open record as a sub-issue of that record, never as a separate issue; a parent "
                            "that only holds sub-issues is a tracking record."),
            "MERGE_RULE": "Merge is the owner's gate.",
            "SHORT": "the owner files, readies and merges.",
        }
    return {
        "GATES_SENTENCE": (f"Approval mode `auto`: the owner files and readies top-level records, sets priorities{promotion}; "
                           "the coordinator files and readies sub-issues of a readied parent; GitHub squash-merges a green "
                           "pull request; CI deploys on merge."),
        "FILING_RULE": ("If no record exists for what you were asked, propose the title, the problem in one or two "
                        "sentences and the open record it belongs to. When that record is open and carries `status:ready`, "
                        "the coordinator files the work as its sub-issue with the Ready facts and the native parent link "
                        "and applies `status:ready` with a comment naming the parent; a top-level record waits for the "
                        "owner. A parent that only holds sub-issues is a tracking record; the coordinator closes it after "
                        "its last child."),
        "MERGE_RULE": ("After opening the pull request, enable GitHub auto-merge with squash; GitHub merges it when "
                       f"`{REQUIRED_CHECKS[0]}` and `{REQUIRED_CHECKS[1]}` are green."
                       + (f" Promotion of `{integration_branch}` into `{default_branch}` is the owner's merge."
                          if integration_branch != default_branch else " The owner never clicks merge for a sub-issue.")),
        "SHORT": ("the owner files and readies top-level records; sub-issues of a readied parent are filed and "
                  "readied by the Planner and squash-merged by GitHub on green."),
    }


def always_on_lines(sha, policy_sha256, default_branch, integration_branch=None, mode="manual"):
    """The three lines every session of an adapter profile reads; task-start prints the same."""
    integration_branch = integration_branch or default_branch
    text = mode_text(mode, default_branch, integration_branch)
    return (
        f"Pinned policy: `{policy_path(sha)}` (SHA-256 `{policy_sha256}`); `PROJECT.md` holds the facts and the verification contract.",
        "Every task starts with `/task-start #N` on a record carrying `status:ready` and ends with `/task-finish`; "
        f"between them your own practice runs. Approval mode `{mode}`: {text['SHORT']}",
        f"Never merge by hand, mark a draft ready, approve, force-push, edit branch protection or push to "
        f"{branch_phrase(default_branch, integration_branch)} without a pull request; verification is the recorded "
        "commands run on the exact head, nothing inferred.",
    )


def policy_path(sha):
    return ".conductor/policy/" + sha + "/shared/WORKFLOW.md"


def recorded_always_on(adoption, spec):
    """always_on lines for a native profile when the adoption record holds its adapter profile."""
    for name, profile in ADAPTER_PROFILES.items():
        entry = (adoption or {}).get("adapters", {}).get(name)
        if entry and profile["native_profile"] == spec["name"]:
            inputs = entry.get("inputs", {})
            default_branch = inputs.get("default_branch", ADAPTER_DEFAULTS["default_branch"])
            return always_on_lines(adoption["policy_commit"], entry["policy_sha256"], default_branch,
                                   inputs.get("integration_branch") or default_branch,
                                   approval_mode(adoption.get("facts", {})))
    return None


def adoption_policy_sha256(target, adoption):
    """Digest of the pinned policy file inside the project, cross-checked with the record."""
    sha = adoption["policy_commit"]
    data = read(target, policy_path(sha))
    if data is None:
        raise InitError(f"Pinned policy file missing: {policy_path(sha)}")
    actual = digest(data)
    recorded = adoption.get("policy_sha256") or adoption.get("files", {}).get(policy_path(sha))
    if recorded and recorded != actual:
        raise InitError(f"Pinned policy file differs from the adoption record: {policy_path(sha)}")
    return actual


def adapter_inputs(options):
    inputs = dict(ADAPTER_DEFAULTS)
    for key, value in (options or {}).items():
        if key not in inputs:
            raise InitError(f"Unknown adapter input: {key}")
        if value is not None:
            inputs[key] = value
    if not re.fullmatch(r"[A-Za-z0-9._/-]+", str(inputs["default_branch"])):
        raise InitError("default_branch must be a plain branch name")
    if not isinstance(inputs["max_parallel_threads"], int) or inputs["max_parallel_threads"] < 1:
        raise InitError("max_parallel_threads must be a positive integer")
    inputs["integration_branch"] = inputs["integration_branch"] or inputs["default_branch"]
    if not re.fullmatch(r"[A-Za-z0-9._/-]+", str(inputs["integration_branch"])):
        raise InitError("integration_branch must be a plain branch name")
    return inputs


def protection_blockers(adoption, branches):
    """Why approval mode auto cannot be generated: each branch without recorded protection evidence.

    The record is `protection.<branch>` in .conductor/adoption.json, written from a thread's
    reading of the live settings: bypass_allowed false, approvals_required false, the
    required checks, a verified date and an evidence link."""
    recorded = adoption.get("protection", {}) or {}
    blockers = []
    for branch in branches:
        entry = recorded.get(branch)
        if not isinstance(entry, dict):
            blockers.append(f"`{branch}` has no `protection` entry")
            continue
        problems = []
        if entry.get("bypass_allowed") is not False:
            problems.append("bypass_allowed is not false")
        if entry.get("approvals_required") not in (False, 0):
            problems.append("approvals_required is not false")
        missing = [check for check in REQUIRED_CHECKS if check not in (entry.get("required_checks") or [])]
        if missing:
            problems.append("required_checks lack " + ", ".join(missing))
        if not entry.get("verified"):
            problems.append("no verified date")
        if problems:
            blockers.append(f"`{branch}`: " + "; ".join(problems))
    return blockers


def project_instructions(facts, sha, policy_sha256, inputs):
    """The filled Claude Code Projects instructions text."""
    commands = "; ".join(
        f"`{check['command']}` from `{check['cwd']}` (expect: {check['expected']})"
        for check in facts["verification"])
    mode = approval_mode(facts)
    text = mode_text(mode, inputs["default_branch"], inputs["integration_branch"])
    values = {
        "APPROVAL_MODE": mode, "INTEGRATION_BRANCH": inputs["integration_branch"],
        "PROTECTED_BRANCHES": branch_phrase(inputs["default_branch"], inputs["integration_branch"]),
        "GATES_SENTENCE": text["GATES_SENTENCE"], "FILING_RULE": text["FILING_RULE"], "MERGE_RULE": text["MERGE_RULE"],
        "PROJECT_NAME": facts["name"], "ONE_LINE_GOAL": facts["purpose"].rstrip("."),
        "REPOSITORY": facts["repository"], "TASK_RECORDS_URL": ", ".join(facts["task_records"]),
        "POLICY_SNAPSHOT_PATH": policy_path(sha), "POLICY_SHA256": policy_sha256,
        "DEFAULT_BRANCH": inputs["default_branch"], "VERIFICATION_COMMANDS": commands,
        "CHECKPOINT_PATH": facts["checkpoint"], "MAX_PARALLEL_THREADS": str(inputs["max_parallel_threads"]),
    }
    text = PROJECT_INSTRUCTIONS_TEMPLATE
    for key, value in values.items():
        text = text.replace("{{" + key + "}}", str(value))
    left = re.findall(r"{{[A-Z_]+}}", text)
    if left:
        raise InitError("Unfilled project-instructions placeholders: " + ", ".join(sorted(set(left))))
    return rewrap(text)


def rewrap(text, width=96):
    """Re-flow paragraphs and bullets after substitution so long values do not leave ragged lines."""
    blocks = []
    for paragraph in text.strip("\n").split("\n\n"):
        items = []
        for line in paragraph.splitlines():
            if line.startswith("- ") or not items:
                items.append(line)
            else:
                items[-1] += " " + line.strip()
        wrapped = []
        for item in items:
            bullet = item.startswith("- ")
            wrapped.append(textwrap.fill(item, width, subsequent_indent="  " if bullet else "",
                                         break_long_words=False, break_on_hyphens=False))
        blocks.append("\n".join(wrapped))
    return "\n\n".join(blocks) + "\n"


def owner_checklist(profile, facts, sha, policy_sha256, inputs, instructions_sha256, length):
    """One-time owner steps the generator cannot do; each is recorded on the task record."""
    paths = adapter_paths(profile)
    skills = " and ".join(f"`{name}`" for name in profile["boundary_skills"])
    mode = approval_mode(facts)
    default_branch, integration_branch = inputs["default_branch"], inputs["integration_branch"]
    branches = " and ".join(f"`{name}`" for name in protected_branches(default_branch, integration_branch))
    checks = " and ".join(f"`{name}`" for name in REQUIRED_CHECKS)
    mode_steps = [
        f"Set the repository variable `{APPROVAL_MODE_VARIABLE}` to `{mode}`, the `Approval mode` fact of `PROJECT.md`, "
        "so the `linked-task` check applies the same gates as the instructions.",
    ]
    if integration_branch != default_branch:
        mode_steps.append(
            f"Set the repository variable `{INTEGRATION_BRANCH_VARIABLE}` to `{integration_branch}`, and name the staging "
            f"deploy job that runs on merge to `{integration_branch}` in the verification contract of `PROJECT.md`.")
    if mode == "auto":
        mode_steps.append(
            "Allow auto-merge in the repository settings (Settings > General > Pull Requests); GitHub squash-merges "
            "a sub-issue's pull request when the required checks are green, and the owner's click is kept for "
            + (f"promoting `{integration_branch}` into `{default_branch}`." if integration_branch != default_branch
               else "top-level records only."))
    checklist = "\n".join(f"- [ ] {item}" for item in (
        f"Paste [{paths['instructions']}]({paths['instructions']}) into **Project settings > Memory > Project instructions** "
        f"({length} of {profile['instructions_limit']} characters) and record its SHA-256 `{instructions_sha256}` on the task record.",
        f"Enable the boundary skills {skills} on the claude.ai account from the kit's `global/skills/` "
        "and record the SHA-256 of each uploaded `SKILL.md` from the kit `SHA256SUMS`; repository skills do not load in a thread.",
        "Create the Backlog issue, pin it, and keep it the only queue.",
        f"Set the repository variable `{profile['backlog_variable']}` to that issue's number so the backlog review names it.",
        f"On {branches}, require a pull request, turn **Do not allow bypassing** on, keep approvals off, "
        f"and require the {checks} checks; then have a thread read the live protection and record it under "
        "`protection.<branch>` in `.conductor/adoption.json` (bypass_allowed, approvals_required, required_checks, "
        "verified date, evidence link). Approval mode `auto` is generated only from that record.",
        *mode_steps,
        "From one new thread, have it quote its loaded memory files and its skill list, confirm "
        f"`{policy_path(sha)}` resolves with SHA-256 `{policy_sha256}`, run "
        f"`conductor_init.py check --profile {profile['name']} --target .`, and record the result and date under "
        f"`adapters.{profile['name']}.discovery` in `.conductor/adoption.json`.",
    ))
    return (f"# Owner checklist: {profile['label']} adapter for {facts['name']}\n\n"
            f"Generated for policy commit `{sha}`. Each step needs the owner's account or repository settings; "
            "a thread never changes them. Record the evidence for each on the task record.\n\n" + checklist + "\n")


def adapter_paths(profile):
    base = ADAPTER_DIR + "/" + profile["name"]
    return {"instructions": base + "/" + profile["instructions"], "checklist": base + "/" + profile["checklist"]}


def adapter_profile(name):
    spec = ADAPTER_PROFILES.get(name)
    if not spec:
        raise InitError("Unknown adapter profile; supported: " + ", ".join(sorted(ADAPTER_PROFILES)))
    return dict(spec, name=name)


def adapter_outputs(target, profile, adoption, inputs, strict=True):
    """Everything the adapter profile emits for a target, and its record entry.

    strict: refuse when a managed section was edited; a check reports it instead."""
    native = dict(PROFILES[profile["native_profile"]], name=profile["native_profile"])
    if native["name"] not in adoption.get("assistants", []):
        raise InitError(f"{native['label']} has not onboarded this project; run generate and onboard first")
    if strict:
        managed_blocks_intact(target, adoption)
    facts = adoption["facts"]
    blockers = facts_blockers(target, facts)
    if blockers:
        raise InitError("; ".join(blockers))
    sha = adoption["policy_commit"]
    policy_sha256 = adoption_policy_sha256(target, adoption)
    mode = approval_mode(facts)
    if mode == "auto":
        missing = protection_blockers(adoption, protected_branches(inputs["default_branch"], inputs["integration_branch"]))
        if missing:
            raise InitError("Approval mode auto needs recorded branch protection in .conductor/adoption.json: "
                            + "; ".join(missing) + ". Have a thread read the live settings and record them first (owner checklist).")
    text = project_instructions(facts, sha, policy_sha256, inputs)
    if len(text) > profile["instructions_limit"]:
        raise InitError(f"Project instructions would be {len(text)} characters, over the {profile['instructions_limit']} field limit; "
                        "shorten the facts or drop a rule with the owner")
    paths = adapter_paths(profile)
    instructions = text.encode()
    checklist = owner_checklist(profile, facts, sha, policy_sha256, inputs, digest(instructions), len(text)).encode()
    outputs = {paths["instructions"]: instructions, paths["checklist"]: checklist}
    lines = always_on_lines(sha, policy_sha256, inputs["default_branch"], inputs["integration_branch"], mode)
    outputs[native["native_instructions"]], section = append_block(
        read(target, native["native_instructions"]), native_adapter(native, read(target, native["native_instructions"]), lines))
    entry = {"profile": profile["name"], "policy_commit": sha, "policy_sha256": policy_sha256,
             "inputs": inputs, "project_instructions": paths["instructions"], "project_instructions_sha256": digest(instructions),
             "project_instructions_chars": len(text), "owner_checklist": paths["checklist"],
             "owner_checklist_sha256": digest(checklist), "always_on_lines": list(lines),
             "discovery": (adoption.get("adapters", {}).get(profile["name"], {}) or {}).get(
                 "discovery", "unverified; run the owner checklist's discovery step from a thread")}
    return outputs, entry, {native["native_instructions"]: digest(section)}


def generate_adapter(target, name, options=None, apply=False, mode=None):
    """Emit an adapter profile's always-on text, owner checklist and record entry.

    mode: an approval-mode override; it becomes the `approval_mode` fact in the adoption
    record and the managed PROJECT.md section, so the fact and the generated text agree."""
    target = Path(target)
    profile = adapter_profile(name)
    inputs = adapter_inputs(options)
    if not read(target, ".conductor/adoption.json"):
        return result("blocked", blockers=["No adoption record; onboard the project before generating an adapter"])
    adoption = load(target, ".conductor/adoption.json")
    facts_changed = {}
    if mode and approval_mode(adoption["facts"], mode) != adoption["facts"].get("approval_mode"):
        adoption = dict(adoption, facts=dict(adoption["facts"], approval_mode=approval_mode({}, mode)))
        managed_blocks_intact(target, adoption)
        facts_changed["PROJECT.md"], section = append_block(read(target, "PROJECT.md"), project_record(adoption["facts"]))
        facts_changed_digest = {"PROJECT.md": digest(section)}
    outputs, entry, managed = adapter_outputs(target, profile, adoption, inputs)
    if facts_changed:
        outputs.update(facts_changed)
        managed.update(facts_changed_digest)
    hashes = dict(adoption.get("files", {}))
    owned_outputs(target, {key: value for key, value in outputs.items() if key not in managed}, hashes)
    updated = dict(adoption)
    updated["facts"] = adoption["facts"]
    updated["adapters"] = dict(adoption.get("adapters", {}), **{profile["name"]: entry})
    updated["managed_blocks"] = dict(adoption.get("managed_blocks", {}), **managed)
    files = dict(hashes)
    files.update({key: digest(value) for key, value in outputs.items() if key not in managed})
    updated["files"] = files
    outputs[".conductor/adoption.json"] = encoded(updated)
    return apply_plan(target, outputs, apply)


def check_adapter(target, name, options=None):
    """Report every way the recorded adapter differs from what the project would generate now."""
    target = Path(target)
    profile = adapter_profile(name)
    if not read(target, ".conductor/adoption.json"):
        return result("blocked", blockers=["No adoption record"])
    adoption = load(target, ".conductor/adoption.json")
    entry = adoption.get("adapters", {}).get(profile["name"])
    if not entry:
        return result("blocked", blockers=[f"Adapter {profile['name']} is not recorded in .conductor/adoption.json; run generate --profile {profile['name']}"])
    inputs = adapter_inputs(dict(entry.get("inputs", {}), **{k: v for k, v in (options or {}).items() if v is not None}))
    outputs, expected, managed = adapter_outputs(target, profile, adoption, inputs, strict=False)
    mismatches = []
    for key in ("project_instructions_sha256", "owner_checklist_sha256", "policy_sha256", "project_instructions_chars", "inputs"):
        if entry.get(key) != expected[key]:
            mismatches.append(f"recorded {key} {entry.get(key)!r} differs from the generated value {expected[key]!r}")
    for key in ("project_instructions", "owner_checklist"):
        path = entry.get(key) or expected[key]
        data = read(target, path)
        if data is None:
            mismatches.append(f"{key} file missing: {path}")
        elif digest(data) != entry.get(key + "_sha256"):
            mismatches.append(f"{key} file {path} (SHA-256 {digest(data)}) differs from the recorded digest {entry.get(key + '_sha256')}")
    for key, expected_digest in managed.items():
        current = block(read(target, key))
        recorded = adoption.get("managed_blocks", {}).get(key)
        if current is None:
            mismatches.append(f"{key} has no managed section")
        elif digest(current) != expected_digest:
            mismatches.append(f"{key} managed section differs from the generated always-on lines")
        elif recorded != expected_digest:
            mismatches.append(f"{key} managed section digest is not the recorded one")
    if mismatches:
        return result("blocked", blockers=mismatches, adapter=profile["name"])
    return result("verified", adapter=profile["name"], project_instructions_sha256=expected["project_instructions_sha256"],
                  discovery=entry.get("discovery"))


def adapter_body(sha, source_files, facts):
    """The vendor-neutral AGENTS.md section every assistant reads."""
    pin = ".conductor/policy/" + sha
    return ("# Conductor project adapter\n\n"
            f"Read `{pin}/shared/WORKFLOW.md` as the pinned common policy.\n"
            f"Policy commit: `{sha}`; SHA-256: `{digest(source_files['shared/WORKFLOW.md'])}`.\n"
            "Read `PROJECT.md` for project facts, verification and authoritative task links.\n"
            "Verification contract: the Verification contract section in `PROJECT.md`; read its source evidence before executing checks.\n"
            "Keep project lifecycle separate from task progress and execution state.\n"
            "Respect Parked/Closed lifecycle and confirmed task ownership; initialization does not start work.\n"
            f"Checkpoint destination: `{facts['checkpoint']}`. Read existing checkpoints before resuming.\n"
            "Verify recorded checks before reporting task completion; never infer an unrecorded command.\n"
            "This adapter grants no deployment, credential, cloud, scheduling, or publication authority.")


def verification_outputs(target, spec, source_files, owned_hashes=None):
    """The native verification skill assets, unless a custom skill occupies that folder.

    An existing folder is replaceable when it is identical to the new assets or when
    every file in it is owned by the adoption record; stale owned assets are removed."""
    verification_root = spec["native_skills"] + "/project-verification"
    native_assets = {key: source_files[spec["verification_skill"] + "/" + key]
                     for key in spec["verification_assets"]}
    native_path = safe(target, verification_root)
    existing = {}
    if native_path.exists():
        for p in native_path.rglob("*"):
            if p.is_file():
                key = str(p.relative_to(native_path))
                existing[key] = read(target, verification_root + "/" + key)
    owned = owned_hashes or {}
    replaceable = (not existing or existing == native_assets or all(
        verification_root + "/" + key in owned and digest(data) == owned[verification_root + "/" + key]
        for key, data in existing.items()))
    if not replaceable:
        return {}, False
    outputs = {verification_root + "/" + key: data for key, data in native_assets.items()}
    for key in existing:
        if key not in native_assets:
            outputs[verification_root + "/" + key] = None
    return outputs, True


def managed_blocks_intact(target, adoption):
    for key, expected in adoption["managed_blocks"].items():
        current = block(read(target, key))
        if current is None or digest(current) != expected:
            raise InitError(f"Managed content changed: {key}")


def onboard(target, facts, skill_root=None, apply=False):
    target = Path(target)
    root = locate_generated(target, skill_root)
    metadata = load(root, "generation.json")
    source_files, spec = check_generated(root, metadata)
    if root.resolve() != safe(target, native_root(spec)).resolve():
        raise InitError("Generated skill must be inside this project at its recorded native path")
    for name in ("AGENTS.override.md",):
        if read(target, name):
            return result("blocked", blockers=["Active native instruction override requires explicit reconciliation: " + name])
    project_old = read(target, "PROJECT.md")
    lifecycle = existing_declarations(project_old, "Lifecycle")
    if any(re.match(r"Closed\b", value, re.I) for value in lifecycle):
        return result("blocked", blockers=["Closed project requires an explicit lifecycle transition"])
    if lifecycle and any(value.lower() != str(facts.get("lifecycle", "")).lower() for value in lifecycle):
        return result("blocked", blockers=["Existing lifecycle differs; reconcile it explicitly"])
    if facts.get("lifecycle") == "Closed":
        return result("blocked", blockers=["Closed project cannot be activated by initialization"])
    blockers = facts_blockers(target, facts)
    if blockers:
        return result("draft", blockers=blockers)
    old = load(target, ".conductor/adoption.json") if read(target, ".conductor/adoption.json") else None
    custom_project = project_old
    section = block(project_old)
    if section is not None:
        custom_project = project_old.replace(section, b"")
    custom_owners = existing_declarations(custom_project, "(?:Owner|Assigned to)")
    owner = facts.get("owner", {})
    if old and custom_owners and (owner.get("confirmed") is not True
            or any(value.casefold() != owner.get("name", "").casefold() for value in custom_owners)):
        return result("blocked", blockers=["Custom project ownership declaration conflicts with or lacks a confirmed adoption owner"])
    if old:
        if old["policy_commit"] != metadata["policy_commit"]:
            return result("blocked", blockers=["The adoption pin differs from this generated skill's pin; run 'migrate' from the new source to move this assistant's skill, or reconcile explicitly"])
        if old["facts"] != facts:
            return result("blocked", blockers=["Existing adoption facts or ownership differ; reconcile explicitly before changing them"])
        managed_blocks_intact(target, old)
    else:
        for key in ("AGENTS.md", "PROJECT.md", spec["native_instructions"]):
            if block(read(target, key)) is not None:
                raise InitError("Unowned Conductor managed section requires reconciliation")
        if existing_declarations(project_old, "(?:Owner|Assigned to)"):
            return result("blocked", blockers=["Existing owner needs explicit reconciliation before adoption"])
    sha = metadata["policy_commit"]
    pin = ".conductor/policy/" + sha
    body = adapter_body(sha, source_files, facts)
    project = project_record(facts)
    adapters = [("AGENTS.md", body), ("PROJECT.md", project)]
    if spec["native_instructions"] != "AGENTS.md":
        adapters.append((spec["native_instructions"],
                         native_adapter(spec, read(target, spec["native_instructions"]), recorded_always_on(old, spec))))
    outputs = {}
    managed = {}
    for key, text in adapters:
        outputs[key], section = append_block(read(target, key), text)
        managed[key] = digest(section)
    for key, data in source_files.items():
        if key.startswith(SNAPSHOT_PREFIX):
            outputs[pin + "/" + key] = data
    # Preserve an existing custom/incomplete skill as a whole, without mixing assets.
    verification, native_compatible = verification_outputs(target, spec, source_files, old.get("files") if old else None)
    outputs.update(verification)
    checkpoint = facts["checkpoint"]
    if str(PurePosixPath(checkpoint)) in outputs:
        raise InitError("Checkpoint collides with a planned managed output")
    if read(target, checkpoint) is None:
        outputs[checkpoint] = (
            "# Conductor setup checkpoint\n\n"
            "Project adoption completed; implementation has not started.\n"
            "Task/issue identity, assignment and worktree for the next task: unknown.\n"
            "Consult PROJECT.md and authoritative task records before resuming.\n"
            "Verification: setup checks only; project commands have not run.\n").encode()
    elif old and checkpoint in old.get("files", {}):
        # Checkpoints are live project state; subsequent work can legitimately edit them.
        pass
    hashes = dict(old.get("files", {})) if old else {}
    # Managed sections permit arbitrary custom text outside their owned markers.
    owned_outputs(target, {key: value for key, value in outputs.items()
                           if key not in managed}, hashes)
    # One project record serves every assistant: merge this assistant's entries into it.
    assistants = sorted(set(old.get("assistants", [LEGACY_ASSISTANT])) | {spec["name"]}) if old else [spec["name"]]
    managed_blocks = dict(old.get("managed_blocks", {})) if old else {}
    managed_blocks.update(managed)
    files = {key: value for key, value in hashes.items() if outputs.get(key, value) is not None}
    files.update({key: digest(value) for key, value in outputs.items()
                  if value is not None and key not in managed and key != checkpoint})
    generators = old.get("generator_sha256", {}) if old else {}
    discovery = old.get("native_discovery", {}) if old else {}
    if isinstance(generators, str):  # record written by the single-profile generator
        generators = {LEGACY_ASSISTANT: generators}
    if isinstance(discovery, str):
        discovery = {LEGACY_ASSISTANT: discovery}
    generators = dict(generators, **{spec["name"]: metadata["generator_sha256"]})
    discovery = dict(discovery)
    discovery.setdefault(spec["name"], "unverified; check in a fresh native session")
    pins = dict(old.get("assistant_pins", {})) if old else {}
    pins[spec["name"]] = sha
    # Keys written by other operations (migration history, other assistants' pins) are kept.
    adoption = dict(old) if old else {}
    adoption.update({"version": 1, "scope": "project", "assistants": assistants, "policy_commit": sha,
                     "policy_sha256": digest(source_files["shared/WORKFLOW.md"]),
                     "policy_manifest_sha256": metadata["policy_manifest_sha256"],
                     "generator_sha256": generators, "facts": facts,
                     "managed_blocks": managed_blocks, "files": files,
                     "native_discovery": discovery, "assistant_pins": pins})
    outputs[".conductor/adoption.json"] = encoded(adoption)
    response = apply_plan(target, outputs, apply)
    if not native_compatible:
        response["notes"] = ["Existing custom verification skill preserved as a whole; review its mapping to PROJECT.md"]
    return response


def migrate(target, source, source_sha, apply=False, manifest_sha=None, skill_root=None):
    """Move this assistant's generated skill, and the shared adoption record, to a new verified source.

    Run from the new source's conductor-init skill. The first assistant to migrate moves
    the shared pin: AGENTS.md section, policy snapshot and adoption record. Each further
    assistant then runs migrate for its own generated skill; until it does, its onboard
    is blocked and the record lists it under assistant_pins at the previous pin."""
    target, source = Path(target), Path(source)
    root = locate_generated(target, skill_root)
    old_meta = load(root, "generation.json")
    _, spec = check_generated(root, old_meta)
    if root.resolve() != safe(target, native_root(spec)).resolve():
        raise InitError("Generated skill must be inside this project at its recorded native path")
    if not read(target, ".conductor/adoption.json"):
        return result("blocked", blockers=["No adoption record to migrate; use generate and onboard for a first adoption"])
    adoption = load(target, ".conductor/adoption.json")
    for name in ("AGENTS.override.md",):
        if read(target, name):
            return result("blocked", blockers=["Active native instruction override requires explicit reconciliation: " + name])
    managed_blocks_intact(target, adoption)
    old_pin, new_pin = adoption["policy_commit"], source_sha
    if old_pin == new_pin and old_meta["policy_commit"] == new_pin:
        return result("unchanged")
    profile = old_meta["capabilities"]
    source_files = verified_source(source, new_pin, profile, manifest_sha, spec)
    skill_outputs, metadata = build_generation(spec, source_files, new_pin, profile)
    native = native_root(spec)
    hashes = dict(adoption.get("files", {}))
    hashes.update({native + "/" + key: value for key, value in old_meta["files"].items()})
    hashes[native + "/generation.json"] = digest(read(root, "generation.json"))
    outputs = {native + "/" + key: value for key, value in skill_outputs.items()}
    for key in old_meta["files"]:
        if key not in skill_outputs:
            outputs[native + "/" + key] = None
    facts = adoption["facts"]
    managed = {}
    if old_pin != new_pin:
        outputs["AGENTS.md"], section = append_block(read(target, "AGENTS.md"), adapter_body(new_pin, source_files, facts))
        managed["AGENTS.md"] = digest(section)
        for key, data in source_files.items():
            if key.startswith(SNAPSHOT_PREFIX):
                outputs[".conductor/policy/" + new_pin + "/" + key] = data
        for key in adoption.get("files", {}):
            if key.startswith(".conductor/policy/" + old_pin + "/"):
                outputs[key] = None
    verification, compatible = verification_outputs(target, spec, source_files, hashes)
    outputs.update(verification)
    owned_outputs(target, {key: value for key, value in outputs.items() if key not in managed}, hashes)
    files = {key: value for key, value in adoption.get("files", {}).items() if outputs.get(key, value) is not None}
    files.update({key: digest(value) for key, value in outputs.items()
                  if value is not None and key not in managed and not key.startswith(native + "/")})
    managed_blocks = dict(adoption.get("managed_blocks", {}))
    managed_blocks.update(managed)
    generators = adoption.get("generator_sha256", {})
    if isinstance(generators, str):
        generators = {LEGACY_ASSISTANT: generators}
    generators = dict(generators, **{spec["name"]: metadata["generator_sha256"]})
    pins = dict(adoption.get("assistant_pins", {}))
    for name in adoption.get("assistants", []):
        pins.setdefault(name, old_pin)
    pins[spec["name"]] = new_pin
    migrations = list(adoption.get("migrations", []))
    if old_pin != new_pin:
        migrations.append({"from": old_pin, "to": new_pin, "assistant": spec["name"]})
    updated = dict(adoption)
    updated.update({"policy_commit": new_pin, "policy_sha256": digest(source_files["shared/WORKFLOW.md"]),
                    "policy_manifest_sha256": metadata["policy_manifest_sha256"],
                    "generator_sha256": generators, "managed_blocks": managed_blocks, "files": files,
                    "assistant_pins": pins, "migrations": migrations})
    outputs[".conductor/adoption.json"] = encoded(updated)
    response = apply_plan(target, outputs, apply)
    notes = []
    pending = sorted(name for name, pin in pins.items() if pin != new_pin)
    if pending:
        notes.append("Assistants still on the previous pin must run migrate for their own skill: " + ", ".join(pending))
    if not compatible:
        notes.append("Existing custom verification skill preserved as a whole; review its mapping to PROJECT.md")
    if notes:
        response["notes"] = notes
    return response


def rollback(target, transaction, apply=False):
    target = Path(target).absolute()
    transaction = Path(transaction)
    if not transaction.is_absolute():
        transaction = target / transaction
    try:
        relative = str(transaction.relative_to(target))
    except ValueError as exc:
        raise InitError("Rollback transaction must be inside the target project") from exc
    if not relative.startswith(".conductor/backups/") or not relative.endswith("/transaction.json"):
        raise InitError("Not a Conductor backup transaction")
    record = load(target, relative)
    replacements = {}
    for key, info in record["files"].items():
        current = read(target, key)
        if info["after"] is None:
            if current is not None:
                raise InitError(f"Rollback refused: a removed file was recreated since setup: {key}")
        elif current is None or digest(current) != info["after"]:
            raise InitError(f"Rollback refused: file changed since setup: {key}")
        previous = None
        if info["backup"]:
            if not info["backup"].startswith(str(transaction.parent.relative_to(target)) + "/before/"):
                raise InitError("Backup is outside the recorded transaction")
            previous = read(target, info["backup"])
            if previous is None or digest(previous) != info["before"]:
                raise InitError(f"Backup content mismatch: {key}")
        replacements[key] = previous
    changes = [{"path": key, "action": "restore" if data is not None else "remove"}
               for key, data in replacements.items()]
    if not apply:
        return result("planned", changes)
    for key, previous in replacements.items():
        path = safe(target, key)
        if previous is None:
            path.unlink()
            prune_empty(target, path.parent)
        else:
            atomic_write(path, previous)
    return result("rolled_back", changes)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="operation", required=True)
    first = sub.add_parser("generate")
    first.add_argument("--source", type=Path, help="Pinned Conductor source (stage one; not used with --profile)")
    first.add_argument("--source-sha", help="Full commit SHA of the source (stage one)")
    first.add_argument("--capabilities", type=Path, help="Verified native capability record (stage one)")
    first.add_argument("--manifest-sha")
    first.add_argument("--update", action="store_true", help="Reviewed generator update retaining the existing policy and capability pin")
    fifth = sub.add_parser("check", help="Compare a recorded adapter profile with what the project generates now")
    for command in (first, fifth):
        command.add_argument("--profile", choices=sorted(ADAPTER_PROFILES),
                             help="Adapter profile generated from the adoption record instead of a source tree")
        command.add_argument("--default-branch", help="Branch threads start from (adapter profiles; default main)")
        command.add_argument("--max-parallel-threads", type=int, help="Thread limit written into the instructions (adapter profiles; default 2)")
        command.add_argument("--integration-branch", help="Branch pull requests target (adapter profiles; default the default branch)")
    first.add_argument("--approval-mode", choices=APPROVAL_MODES,
                       help="Override the project's approval_mode fact; recorded in PROJECT.md and the adoption record (ADR 0005)")
    second = sub.add_parser("onboard")
    second.add_argument("--facts", type=Path, required=True)
    second.add_argument("--skill-root", type=Path, help="Generated skill folder when more than one assistant has generated one")
    third = sub.add_parser("rollback")
    third.add_argument("--transaction", type=Path, required=True)
    fourth = sub.add_parser("migrate", help="Move an existing adoption to a new verified policy source")
    fourth.add_argument("--source", type=Path, required=True)
    fourth.add_argument("--source-sha", required=True)
    fourth.add_argument("--manifest-sha")
    fourth.add_argument("--skill-root", type=Path, help="Generated skill folder when more than one assistant has generated one")
    for command in (first, second, third, fourth, fifth):
        command.add_argument("--target", type=Path, required=True)
        if command is not fifth:
            command.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    try:
        if args.operation == "generate" and args.profile:
            response = generate_adapter(args.target, args.profile, {
                "default_branch": args.default_branch, "max_parallel_threads": args.max_parallel_threads,
                "integration_branch": args.integration_branch}, args.apply, args.approval_mode)
        elif args.operation == "generate":
            if not (args.source and args.source_sha and args.capabilities):
                parser.error("generate needs --source, --source-sha and --capabilities, or --profile")
            response = generate(args.target, args.source, args.source_sha,
                                json.loads(args.capabilities.read_text()), args.apply, args.manifest_sha, args.update)
        elif args.operation == "check":
            if not args.profile:
                parser.error("check needs --profile")
            response = check_adapter(args.target, args.profile, {
                "default_branch": args.default_branch, "max_parallel_threads": args.max_parallel_threads,
                "integration_branch": args.integration_branch})
        elif args.operation == "onboard":
            response = onboard(args.target, json.loads(args.facts.read_text()), args.skill_root, apply=args.apply)
        elif args.operation == "migrate":
            response = migrate(args.target, args.source, args.source_sha, args.apply, args.manifest_sha, args.skill_root)
        else:
            response = rollback(args.target, args.transaction, args.apply)
    except (InitError, OSError, ValueError, KeyError, TypeError) as exc:
        response = result("blocked", blockers=[str(exc)])
    print(json.dumps(response, indent=2))
    return 2 if response["status"] in ("blocked", "draft") else 0


if __name__ == "__main__":
    raise SystemExit(main())
