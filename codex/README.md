# Codex shared-practice template kit

Status: reviewable source templates, not installed configuration. Kit version: `0.1.0-draft`.

Conductor is the canonical shared-practice library for coding and analytics workflows,
reusable skills, techniques, architecture patterns, and harness guidance. Assistant-specific
adapters stay thin. Each actual project repository owns its state, plans, specific
architecture, issues, current task owner, checkpoints, code, and data deliverables.
This kit creates no central controller, runtime, Orca/Herdr integration, or tmux dependency.
Older application files elsewhere in this repository are historical and remain untouched.

## Contents

| Source | Purpose / eventual destination |
| --- | --- |
| [shared/PRACTICE.md](shared/PRACTICE.md) | Canonical common policy, explicitly read from a pinned local snapshot |
| [global/AGENTS.md](global/AGENTS.md) | Small universal adapter → Codex home `AGENTS.md` |
| [project/AGENTS.md](project/AGENTS.md) | Fillable project adapter → target repository `AGENTS.md` |
| [conductor-handoff](global/skills/conductor-handoff/SKILL.md) | General skill → user `.agents/skills/conductor-handoff/` |
| [project-verification](project/skills/project-verification/SKILL.md) | Project skill → repository `.agents/skills/project-verification/` |
| [LOCAL-SETUP.md](LOCAL-SETUP.md) | Local installation and rollback procedure |
| [CLOUD-SETUP.md](CLOUD-SETUP.md) | Cloud preparation, persistence, and fresh-task checks |
| [MANIFEST.md](MANIFEST.md) | Sources, version, pinning, and placeholder contract |

These directories are distribution sources. They do not install themselves. Avoid launching
project work from inside template directories: an `AGENTS.md` there may be discovered as
directory-scoped instructions. They are not active global or project-root configuration.

## Adoption contract

1. Review this kit, then obtain authorization for the intended installation scope.
2. Make the shared policy available as an immutable local snapshot in every environment
   that runs the assistant. A remote URL in an instruction file is not automatically loaded.
3. Fill the project template from verified repository evidence. Resolve every
   `{{PLACEHOLDER}}`, or use an explicit `not applicable — reason` for optional facts.
   Required policy paths, pins, and checkpoint destinations cannot be marked not applicable.
4. Merge adapters into existing instructions without discarding existing agreements.
   Do not copy the whole shared policy into both adapters.
5. Inspect the final instruction chain and skill discovery in a fresh session before use.

The separate Library guide/kit version 2 is not included, installed, or assumed to exist.
This draft implements the supplied shared-practice direction without claiming parity with
that unavailable artifact. No universal cross-vendor compatibility is claimed.
