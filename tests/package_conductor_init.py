#!/usr/bin/env python3
"""Regenerate/check distributed initializer assets and package identities."""
import argparse
import hashlib
import json
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]


def sha(data):
    return hashlib.sha256(data).hexdigest()


def packaged(root):
    return {str(p.relative_to(ROOT)) for p in (ROOT / root).rglob("*")
            if p.is_file() and p.suffix in (".md", ".json", ".yaml", ".py", ".docx")
            and "__pycache__" not in p.parts}


def check_skill_resources(content):
    """Check this package's simple scalar frontmatter and concrete source links."""
    skills = ("shared/skills/conductor-init/SKILL.md", "codex/global/skills/conductor-init/SKILL.md",
              "shared/skills/conductor-init/assets/project-skill.md",
              "codex/global/skills/conductor-init/assets/project-skill.md")
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
            continue  # Links refer to the generated snapshot/metadata, checked by fixtures.
        for target in re.findall(r"\[[^\]]+\]\(([^)]+)\)", text):
            if "://" not in target and not target.startswith("#"):
                linked = str((Path(key).parent / target).as_posix())
                if linked not in content.outputs and not (ROOT / linked).is_file():
                    raise ValueError(f"Broken resource link: {key} -> {target}")
    ui = content("codex/global/skills/conductor-init/agents/openai.yaml").decode()
    for field in ("display_name", "short_description", "default_prompt"):
        match = re.search(r"^  " + field + r": (.+)$", ui, re.M)
        if not match or not isinstance(json.loads(match[1]), str):
            raise ValueError("UI metadata must use quoted string fields")
    if "$conductor-init" not in ui:
        raise ValueError("UI invocation must name the skill")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--write", action="store_true")
    args = parser.parse_args()
    common = "shared/skills/conductor-init/"
    native = "codex/global/skills/conductor-init/"
    outputs = {
        common + "references/project-init.md": (ROOT / "shared/workflows/project-init.md").read_bytes(),
        native + "references/project-init.md": (ROOT / "shared/workflows/project-init.md").read_bytes(),
        native + "scripts/conductor_init.py": (ROOT / (common + "scripts/conductor_init.py")).read_bytes(),
        native + "assets/project-skill.md": (ROOT / (common + "assets/project-skill.md")).read_bytes(),
    }

    def content(key):
        return outputs[key] if key in outputs else (ROOT / key).read_bytes()

    content.outputs = outputs
    check_skill_resources(content)

    codex = sorted(packaged("codex") | {key for key in outputs if key.startswith("codex/")})
    outputs["codex/SHA256SUMS"] = "".join(
        f"{sha(content(key))}  {key[len('codex/') :]}\n" for key in codex).encode()
    manifest = json.loads((ROOT / "MANIFEST.json").read_bytes())
    keys = set(manifest["files"]) | packaged("shared") | packaged("tests") | packaged("docs") | set(codex)
    keys.update(outputs)
    keys.update(("docs/project-initialization.md", "codex/SHA256SUMS"))
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
    print(f"{'Regenerated' if args.write else 'Verified'} {len(outputs)} outputs; "
          f"{len(keys)} root digests, {len(codex)} native digests")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
