#!/usr/bin/env python3
"""Regenerate/check distributed initializer assets and package identities."""
import argparse
import hashlib
import json
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]
COMMON = "shared/skills/conductor-init/"
# Native distribution copies: kit prefix -> (skill folder, checksum file).
NATIVE = {
    "assistants/claude-code/": ("assistants/claude-code/global/skills/conductor-init/",
                                "assistants/claude-code/SHA256SUMS"),
}
TEMPLATE_PLACEHOLDERS = ("@SOURCE_SHA@", "@ASSISTANT@", "@NATIVE_SKILLS@", "@INVOCATION@")
# Every shared/skills wrapper needs a same-named native copy in each kit's global skills,
# except where WRAPPER_ALIASES maps the shared name to the kit's name. WRAPPER_ALLOWLIST
# records deliberate omissions per kit with the task record that tracks each; a listed
# name whose copy exists fails as stale, so the list shrinks as copies land.
WRAPPER_SKILLS = "global/skills/"
WRAPPER_ALIASES = {"checkpoint-handoff": "conductor-handoff"}
WRAPPER_ALLOWLIST = {}


def sha(data):
    return hashlib.sha256(data).hexdigest()


def packaged(root):
    return {str(p.relative_to(ROOT)) for p in (ROOT / root).rglob("*")
            if p.is_file() and p.suffix in (".md", ".json", ".yaml", ".yml", ".py", ".docx")
            and "__pycache__" not in p.parts}


def check_wrapper_copies(shared_names, kit_skills, allowlist=WRAPPER_ALLOWLIST, aliases=WRAPPER_ALIASES):
    """Fail when a kit lacks a native copy of a shared wrapper, or allowlists one it has.

    shared_names: folder names under shared/skills; kit_skills: kit prefix -> native
    skill folder names under that kit's global skills. Returns the kits checked.
    """
    for prefix in sorted(kit_skills):
        present = set(kit_skills[prefix])
        allowed = allowlist.get(prefix, {})
        for shared in sorted(shared_names):
            native = aliases.get(shared, shared)
            if native in present:
                if shared in allowed:
                    raise ValueError(
                        f"Stale wrapper allowlist entry: {prefix} has {native}; remove {shared!r}")
                continue
            if shared in allowed:
                continue
            raise ValueError(
                f"Missing wrapper copy: {prefix}{WRAPPER_SKILLS}{native}/SKILL.md for shared/skills/{shared}"
                " (add the copy or allowlist it with its task record)")
    return sorted(kit_skills)


def skill_names(folder):
    """Folder names under a skills directory that carry a SKILL.md."""
    return {path.parent.name for path in (ROOT / folder).glob("*/SKILL.md")}


def check_skill_resources(content):
    """Check this package's simple scalar frontmatter and concrete source links."""
    skills = [COMMON + "SKILL.md", COMMON + "assets/project-skill.md"]
    for folder, _ in NATIVE.values():
        skills.extend((folder + "SKILL.md", folder + "assets/project-skill.md"))
    for key in skills:
        text = content(key).decode()
        if not text.startswith("---\n") or "\n---\n" not in text[4:]:
            raise ValueError(f"Missing frontmatter: {key}")
        front = text.split("---\n", 2)[1]
        fields = dict(line.split(": ", 1) for line in front.strip().splitlines())
        if (not re.fullmatch(r"[a-z0-9-]{1,63}", fields.get("name", ""))
                or not fields.get("description") or len(fields["description"]) > 1024):
            raise ValueError(f"Invalid skill name/description: {key}")
        if any(marker in text for marker in ("/Users/", "rKBm9m", "Tnd8b9", "TODO", "[INSERT")):
            raise ValueError(f"Nonportable path or unfinished scaffold: {key}")
        if "/assets/" in key:
            if text.count("@SOURCE_SHA@") != 1:
                raise ValueError("Native template must contain one explicit policy placeholder")
            if any(marker not in text for marker in TEMPLATE_PLACEHOLDERS):
                raise ValueError("Native template must carry every assistant placeholder")
            continue  # Links refer to the generated snapshot/metadata, checked by fixtures.
        for target in re.findall(r"\[[^\]]+\]\(([^)]+)\)", text):
            if "://" not in target and not target.startswith("#"):
                linked = str((Path(key).parent / target).as_posix())
                if linked not in content.outputs and not (ROOT / linked).is_file():
                    raise ValueError(f"Broken resource link: {key} -> {target}")
    claude = content(NATIVE["assistants/claude-code/"][0] + "SKILL.md").decode()
    if ".claude/skills/conductor-project-init" not in claude or "@AGENTS.md" not in claude:
        raise ValueError("Claude Code skill must name its native path and the AGENTS.md import")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--write", action="store_true")
    args = parser.parse_args()
    recipe = (ROOT / "shared/workflows/project-init.md").read_bytes()
    outputs = {COMMON + "references/project-init.md": recipe}
    for folder, _ in NATIVE.values():
        outputs[folder + "references/project-init.md"] = recipe
        outputs[folder + "scripts/conductor_init.py"] = (ROOT / (COMMON + "scripts/conductor_init.py")).read_bytes()
        outputs[folder + "assets/project-skill.md"] = (ROOT / (COMMON + "assets/project-skill.md")).read_bytes()

    def content(key):
        return outputs[key] if key in outputs else (ROOT / key).read_bytes()

    content.outputs = outputs
    check_skill_resources(content)
    check_wrapper_copies(skill_names("shared/skills"),
                         {prefix: skill_names(prefix + WRAPPER_SKILLS) for prefix in NATIVE})

    native_counts = {}
    for prefix, (_, checksums) in NATIVE.items():
        kit = sorted(packaged(prefix.rstrip("/")) | {key for key in outputs if key.startswith(prefix)})
        kit = [key for key in kit if key != checksums]
        outputs[checksums] = "".join(
            f"{sha(content(key))}  {key[len(prefix):]}\n" for key in kit).encode()
        native_counts[checksums] = len(kit)
    manifest = json.loads((ROOT / "MANIFEST.json").read_bytes())
    keys = (set(manifest["files"]) | packaged("shared") | packaged("tests") | packaged("docs")
            | packaged("assistants"))
    # Deleted paths drop out of the manifest instead of failing as missing sources.
    keys = {key for key in keys if key in outputs or (ROOT / key).is_file()}
    keys.update(outputs)
    keys.update(("docs/project-initialization.md",))
    keys.discard("MANIFEST.json")
    manifest["version"] = "0.5.0-draft"
    manifest["files"] = {key: sha(content(key)) for key in sorted(keys)}
    outputs["MANIFEST.json"] = (json.dumps(manifest, indent=2) + "\n").encode()
    changed = []
    for key, data in sorted(outputs.items()):
        path = ROOT / key
        if not path.exists() or path.read_bytes() != data:
            changed.append(key)
            if args.write:
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(data)
    if changed and not args.write:
        print("Out of date: " + ", ".join(changed))
        return 1
    natives = ", ".join(f"{count} {name} digests" for name, count in native_counts.items())
    print(f"{'Regenerated' if args.write else 'Verified'} {len(outputs)} outputs; "
          f"{len(keys)} root digests, {natives}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
