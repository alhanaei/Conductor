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
import uuid


class InitError(Exception):
    """A trust, ownership, or path invariant prevents setup."""


BEGIN = "<!-- conductor:init:begin -->"
END = "<!-- conductor:init:end -->"
NATIVE = ".agents/skills/conductor-project-init"


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


def verified_source(source, sha, capabilities, manifest_sha=None):
    if not re.fullmatch(r"[0-9a-f]{40}", sha):
        raise InitError("Source revision must be an immutable full commit SHA")
    manifest_data = read(source, "MANIFEST.json")
    if not manifest_data:
        raise InitError("Source has no manifest")
    manifest = load(source, "MANIFEST.json")
    files = dict(manifest["files"])
    files["MANIFEST.json"] = digest(manifest_data)
    checks = read(source, "codex/SHA256SUMS")
    if not checks:
        raise InitError("Source has no native Codex checksums")
    # A reviewed artifact needs independent identities, not a digest it reports itself.
    if manifest_sha is not None:
        if digest(manifest_data) != manifest_sha:
            raise InitError("Artifact manifest identity mismatch")
        bound = files.get("codex/SHA256SUMS")
        expected = bound or capabilities.get("source_codex_checksums_sha256")
        if not expected or digest(checks) != expected:
            raise InitError("Independent Codex checksum identity required or mismatched")
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
    files["codex/SHA256SUMS"] = digest(checks)
    for line in checks.decode().splitlines():
        if not line.strip():
            continue
        match = re.fullmatch(r"([0-9a-f]{64})\s+\*?(.+)", line)
        if not match:
            raise InitError("Invalid Codex checksum entry")
        key = "codex/" + match[2]
        if key in files and files[key] != match[1]:
            raise InitError(f"Conflicting source digests: {key}")
        files[key] = match[1]
    required = ["shared/WORKFLOW.md", "shared/templates/HANDOFF.md",
                "shared/harness/run-contract.schema.json",
                "codex/project/skills/project-verification/SKILL.md",
                "codex/project/skills/project-verification/agents/openai.yaml"]
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


def apply_plan(target, outputs, apply):
    """Preflight all paths, save real previous contents, then write changed files."""
    changed = {}
    before = {}
    for relative, data in sorted(outputs.items()):
        old = read(target, relative)
        if old != data:
            changed[relative] = data
            before[relative] = old
    if not changed:
        return result("unchanged")
    changes = [{"path": key, "action": "create" if before[key] is None else "update"}
               for key in changed]
    if not apply:
        return result("planned", changes)
    base = ".conductor/backups/" + uuid.uuid4().hex
    transaction = {"version": 1, "files": {}}
    for key, data in changed.items():
        backup = base + "/before/" + key if before[key] is not None else None
        transaction["files"][key] = {
            "before": digest(before[key]) if before[key] is not None else None,
            "after": digest(data), "backup": backup,
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
    if (not re.fullmatch(r"[0-9a-f]{40}", sha) or metadata.get("scope") != "project"
            or metadata.get("version") != 1 or not codex_profile(metadata["capabilities"])):
        raise InitError("Invalid generated skill binding or capability profile")
    source_files = verified_source(root / "assets/source", sha, {
        "source_codex_checksums_sha256": metadata["source_codex_checksums_sha256"]
    }, metadata["policy_manifest_sha256"])
    expected = {"assets/source/" + key for key in source_files}
    expected.update(("SKILL.md", "scripts/conductor_init.py", "agents/openai.yaml"))
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
    return source_files


def codex_profile(profile):
    return (profile.get("assistant") == "codex" and profile.get("verified") is True
            and profile.get("native_skills") == ".agents/skills"
            and profile.get("native_instructions") == "AGENTS.md"
            and profile.get("scope", "project") == "project"
            and profile.get("execution") in ("local", "cloud")
            and bool(profile.get("surface")) and bool(profile.get("evidence_ref")))


def generate(target, source, source_sha, capabilities, apply=False, manifest_sha=None, update=False):
    target, source = Path(target), Path(source)
    profile = capabilities
    if not codex_profile(profile):
        return result("draft", blockers=["Verify a native capability mapping; this helper supports project-scoped Codex only"])
    safe(target, NATIVE)
    source_files = verified_source(source, source_sha, profile, manifest_sha)
    package = Path(__file__).absolute().parent.parent
    outputs = {"assets/source/" + key: value for key, value in source_files.items()}
    outputs["scripts/conductor_init.py"] = Path(__file__).read_bytes()
    template = read(package, "assets/project-skill.md")
    if template is None:
        raise InitError("Generic generator template missing; invoke stage one from the source skill")
    outputs["SKILL.md"] = template.replace(b"@SOURCE_SHA@", source_sha.encode())
    outputs["agents/openai.yaml"] = (
        'interface:\n  display_name: "Conductor Project Init"\n'
        '  short_description: "Onboard a project to pinned Conductor policy"\n'
        '  default_prompt: "Use $conductor-project-init to onboard this project."\n').encode()
    metadata = {"version": 1, "scope": "project", "policy_commit": source_sha,
                "policy_manifest_sha256": digest(source_files["MANIFEST.json"]),
                "source_codex_checksums_sha256": digest(source_files["codex/SHA256SUMS"]),
                "capabilities": profile, "generator_sha256": digest(outputs["scripts/conductor_init.py"]),
                "template_sha256": digest(template),
                "files": {key: digest(value) for key, value in outputs.items()}}
    outputs["generation.json"] = encoded(metadata)
    root = safe(target, NATIVE)
    old = load(root, "generation.json") if read(root, "generation.json") else None
    if old:
        check_generated(root, old)
        if old != metadata:
            if (not update or any(old[key] != metadata[key] for key in (
                    "policy_commit", "policy_manifest_sha256", "source_codex_checksums_sha256", "capabilities"))):
                return result("blocked", blockers=["Existing generation differs; use a reviewed --update for generator changes at the same policy/capability pin, or reconcile a policy migration explicitly"])
    hashes = dict(old["files"]) if old else {}
    if old:
        hashes["generation.json"] = digest(read(root, "generation.json"))
    owned_outputs(root, outputs, hashes)
    return apply_plan(target, {NATIVE + "/" + key: value for key, value in outputs.items()}, apply)


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
    if not facts.get("verification"):
        missing.append("evidenced verification contract")
    if missing:
        return ["Missing essential facts: " + ", ".join(missing)]
    checkpoint = str(PurePosixPath(facts["checkpoint"]))
    safe(target, checkpoint)
    if (checkpoint in (".", ".conductor", ".conductor/policy", ".conductor/backups")
            or checkpoint.split("/")[0] in ("AGENTS.md", "PROJECT.md", "CLAUDE.md", "AGENTS.override.md", ".git", ".agents", ".claude", ".codex")
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
    links = ", ".join(f"[{value}]({value})" for value in facts["task_records"])
    lines.append("- Authoritative tasks: " + links)
    lines.append(f"- Checkpoint: [{facts['checkpoint']}]({facts['checkpoint']})")
    for key, value in facts.items():
        if key not in ("name", "kind", "purpose", "repository", "lifecycle", "task_records", "checkpoint", "verification"):
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


def onboard(target, facts, skill_root=None, apply=False):
    target = Path(target)
    root = Path(skill_root) if skill_root else safe(target, NATIVE)
    if root.resolve() != safe(target, NATIVE).resolve():
        raise InitError("Generated skill must be inside this project at its recorded native path")
    metadata = load(root, "generation.json")
    source_files = check_generated(root, metadata)
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
        if old["policy_commit"] != metadata["policy_commit"] or old["facts"] != facts:
            return result("blocked", blockers=["Existing adoption facts, ownership, or pin differ; reconcile explicitly before changing them"])
        for key, expected in old["managed_blocks"].items():
            current = block(read(target, key))
            if current is None or digest(current) != expected:
                raise InitError(f"Managed content changed: {key}")
    else:
        for key in ("AGENTS.md", "PROJECT.md"):
            if block(read(target, key)) is not None:
                raise InitError("Unowned Conductor managed section requires reconciliation")
        if existing_declarations(project_old, "(?:Owner|Assigned to)"):
            return result("blocked", blockers=["Existing owner needs explicit reconciliation before adoption"])
    sha = metadata["policy_commit"]
    pin = ".conductor/policy/" + sha
    body = ("# Conductor project adapter\n\n"
            f"Read `{pin}/shared/WORKFLOW.md` as the pinned common policy.\n"
            f"Policy commit: `{sha}`; SHA-256: `{digest(source_files['shared/WORKFLOW.md'])}`.\n"
            "Read `PROJECT.md` for project facts, verification and authoritative task links.\n"
            "Verification contract: the Verification contract section in `PROJECT.md`; read its source evidence before executing checks.\n"
            "Keep project lifecycle separate from task progress and execution state.\n"
            "Respect Parked/Closed lifecycle and confirmed task ownership; initialization does not start work.\n"
            f"Checkpoint destination: `{facts['checkpoint']}`. Read existing checkpoints before resuming.\n"
            "Verify recorded checks before reporting task completion; never infer an unrecorded command.\n"
            "This adapter grants no deployment, credential, cloud, scheduling, or publication authority.")
    project = project_record(facts)
    outputs = {}
    managed = {}
    for key, text in (("AGENTS.md", body), ("PROJECT.md", project)):
        outputs[key], section = append_block(read(target, key), text)
        managed[key] = digest(section)
    for key, data in source_files.items():
        outputs[pin + "/" + key] = data
    verification_root = ".agents/skills/project-verification"
    native_assets = {key: source_files["codex/project/skills/project-verification/" + key]
                     for key in ("SKILL.md", "agents/openai.yaml")}
    native_path = safe(target, verification_root)
    # Preserve an existing custom/incomplete skill as a whole, without mixing assets.
    native_compatible = not native_path.exists() or (
        all(read(target, verification_root + "/" + key) == data
            for key, data in native_assets.items())
        and {str(p.relative_to(native_path)) for p in native_path.rglob("*") if p.is_file()}
            == set(native_assets))
    if native_compatible:
        for key, data in native_assets.items():
            outputs[verification_root + "/" + key] = data
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
    hashes = old.get("files", {}) if old else {}
    # Managed sections permit arbitrary custom text outside their owned markers.
    owned_outputs(target, {key: value for key, value in outputs.items()
                           if key not in managed}, hashes)
    adoption = {"version": 1, "scope": "project", "policy_commit": sha,
                "policy_manifest_sha256": metadata["policy_manifest_sha256"],
                "generator_sha256": metadata["generator_sha256"], "facts": facts,
                "managed_blocks": managed,
                "files": {key: digest(value) for key, value in outputs.items()
                          if key not in managed and key != checkpoint},
                "native_discovery": "unverified; check in a fresh native session"}
    outputs[".conductor/adoption.json"] = encoded(adoption)
    response = apply_plan(target, outputs, apply)
    if not native_compatible:
        response["notes"] = ["Existing custom verification skill preserved as a whole; review its mapping to PROJECT.md"]
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
        if current is None or digest(current) != info["after"]:
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
        else:
            atomic_write(path, previous)
    return result("rolled_back", changes)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="operation", required=True)
    first = sub.add_parser("generate")
    first.add_argument("--source", type=Path, required=True)
    first.add_argument("--source-sha", required=True)
    first.add_argument("--capabilities", type=Path, required=True)
    first.add_argument("--manifest-sha")
    first.add_argument("--update", action="store_true", help="Reviewed generator update retaining the existing policy and capability pin")
    second = sub.add_parser("onboard")
    second.add_argument("--facts", type=Path, required=True)
    third = sub.add_parser("rollback")
    third.add_argument("--transaction", type=Path, required=True)
    for command in (first, second, third):
        command.add_argument("--target", type=Path, required=True)
        command.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    try:
        if args.operation == "generate":
            response = generate(args.target, args.source, args.source_sha,
                                json.loads(args.capabilities.read_text()), args.apply, args.manifest_sha, args.update)
        elif args.operation == "onboard":
            response = onboard(args.target, json.loads(args.facts.read_text()), apply=args.apply)
        else:
            response = rollback(args.target, args.transaction, args.apply)
    except (InitError, OSError, ValueError, KeyError, TypeError) as exc:
        response = result("blocked", blockers=[str(exc)])
    print(json.dumps(response, indent=2))
    return 2 if response["status"] in ("blocked", "draft") else 0


if __name__ == "__main__":
    raise SystemExit(main())
