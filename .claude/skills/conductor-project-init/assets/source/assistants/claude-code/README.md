# Claude Code shared-practice template kit

Status: reviewable source templates, not installed configuration. Kit version: `0.1.0-draft`.
Use [shared policy](../../shared/WORKFLOW.md); current jobs belong in project issues.

Conductor is the canonical shared-practice library. This folder holds the thin Claude Code
adapter: how Claude Code discovers instructions and skills, the installable templates, and
the adoption record. It is the one kit Conductor distributes since ADR 0002 (the former sibling kit for another assistant is recoverable from the tag on the last multi-kit commit), laid out so that
every assistant reads one project record; it carries the `conductor-init`,
`conductor-handoff` and `project-verification` skills, generated copies of the two task
boundary skills and a native copy of every shared task wrapper, checked for drift by the
packaging test. Each actual
project repository owns its state, plans, issues, current task owner, checkpoints, code
and data deliverables. This kit creates no runtime, hook, credential or integration.

## Contents

| Source | Purpose / eventual destination |
| --- | --- |
| [global/CLAUDE.md](global/CLAUDE.md) | Small universal adapter → user `~/.claude/CLAUDE.md` (append) |
| [project/CLAUDE.md](project/CLAUDE.md) | Thin project adapter → target repository root `CLAUDE.md`; imports the project `AGENTS.md` |
| [conductor-handoff](global/skills/conductor-handoff/SKILL.md) | General skill → user `~/.claude/skills/conductor-handoff/` |
| [project-verification](project/skills/project-verification/SKILL.md) | Project skill → repository `.claude/skills/project-verification/` |
| [task-start](global/skills/task-start/SKILL.md) | General skill → user `~/.claude/skills/task-start/` (or enabled on the account for project threads); generated copy of the shared `task-start` boundary skill and its `scripts/task_boundary.py` helper |
| [task-finish](global/skills/task-finish/SKILL.md) | General skill → user `~/.claude/skills/task-finish/`; generated copy of the shared `task-finish` boundary skill and the same helper |
| [independent-review](global/skills/independent-review/SKILL.md) | General skill → user `~/.claude/skills/independent-review/`; native copy of the shared `independent-review` wrapper |
| [gate-review](global/skills/gate-review/SKILL.md) | General skill → user `~/.claude/skills/gate-review/`; native copy of the shared `gate-review` wrapper for the lifecycle workflow |
| [grilling](global/skills/grilling/SKILL.md) | General skill → user `~/.claude/skills/grilling/`; native copy of the shared `grilling` technique wrapper |
| [to-tickets](global/skills/to-tickets/SKILL.md) | General skill → user `~/.claude/skills/to-tickets/`; native copy of the shared `to-tickets` wrapper |
| [conductor-init](global/skills/conductor-init/SKILL.md) | Generate a native project initializer; optional personal installation to `~/.claude/skills/conductor-init/` only within that scope |
| [LOCAL-SETUP.md](LOCAL-SETUP.md) | Local installation, discovery check and rollback procedure |
| [CLOUD-SETUP.md](CLOUD-SETUP.md) | Cloud session, Remote Control and Projects (beta) differences |
| [PROJECT-INSTRUCTIONS.template.md](PROJECT-INSTRUCTIONS.template.md) | Unfilled source of a project's **Project instructions** text, generated from the helper; the `claude-code-projects` profile fills it per project and records its digest (see [CLOUD-SETUP.md](CLOUD-SETUP.md#generating-the-project-instructions-the-claude-code-projects-profile)) |
| [MANIFEST.md](MANIFEST.md) | Sources, version, pinning and placeholder contract |
| `SHA256SUMS` | Digests of every other kit file |

These directories are distribution sources. They do not install themselves. A `CLAUDE.md`
inside a template directory is loaded on demand when Claude Code reads files there, so do
not launch project work from inside the template folders.

For repeatable project setup, use [conductor-init](global/skills/conductor-init/SKILL.md).
Its helper, recipe and template are generated copies of the canonical sources under
`shared/`; the helper accepts a verified Claude Code profile and writes the same
`AGENTS.md` and `PROJECT.md` record for every assistant. See
[usage and validation](../../docs/project-initialization.md).

## Unified project record

Claude Code reads `CLAUDE.md`; several other assistants read `AGENTS.md`. The
project adapter therefore starts with the line `@AGENTS.md`, which imports the project's
vendor-neutral `AGENTS.md` at launch. The project facts, boundaries and verification
contract are filled once, in `AGENTS.md`, and every assistant sees the same text. The
Claude `CLAUDE.md` adds only the policy binding, the Claude skill locations and the
precedence of explicit task limits over inherited defaults.

Once a root `CLAUDE.md` exists, Claude Code no longer reads `AGENTS.md` on its own, so the
import line is required, not optional. The import never causes a double read.

## Discovery facts (docs checked 2026-10-10; Projects checked 2026-10-17)

- Load order at launch: managed policy file, `~/.claude/CLAUDE.md`, then `CLAUDE.md`,
  `.claude/CLAUDE.md` and `CLAUDE.local.md` from the root of the filesystem down to the
  working directory. Subdirectory files load on demand. Files in `--add-dir` directories
  are not loaded unless `CLAUDE_CODE_ADDITIONAL_DIRECTORIES_CLAUDE_MD=1` is set.
- Automatic `AGENTS.md` reading requires Claude Code v2.1.277 by the docs and applies only
  when no `CLAUDE.md` exists in the working directory or above it. A user setting can enable
  reading both; do not rely on it. `AGENTS.override.md` and `.agents/` are never read.
- `@path` imports resolve relative to the containing file, up to four hops. Paths inside
  backticks or fenced code are not imported. A project-level import that resolves outside
  the working directory prompts for approval, so the project adapter references the
  policy snapshot by path in backticks and does not import it.
- Skills: personal `~/.claude/skills/<name>/SKILL.md`; project `.claude/skills/<name>/SKILL.md`
  from the start directory up to the repository root; plugin skills are namespaced.
  Same-name precedence is enterprise, then personal, then project. All frontmatter fields
  are optional; this kit sets `name` and `description` only. A newly created top-level
  skills directory needs `/reload-skills` or a fresh session.
- Diagnostics: `/context` lists memory files loaded at launch; `/memory` lists memory
  locations; `/skills` lists discovered skills; an `InstructionsLoaded` hook can log every
  instruction file as it loads. No documented command lists loaded instructions without
  starting a session.
- Cloud sessions clone the repository's remote branch, not the local checkout. Repository
  `CLAUDE.md` and `.claude/skills/` carry over; `~/.claude/CLAUDE.md` and personal skills
  do not. Remote Control runs on the local machine and sees local files.
- Projects (beta) run each task as a thread, usually a cloud session, from one coordinating
  conversation. Threads load `CLAUDE.md` and `.claude/` skills, agents and commands from
  every project repository; `.claude/settings.json` rules and hooks apply only in a
  one-repository project. Project instructions (16,000 characters, set in the UI) and
  project memory (`MEMORY.md`, Claude-written) reach cloud threads and are not in Git.
  Threads run in auto mode and watch their pull requests with auto-fix on. See
  [CLOUD-SETUP.md](CLOUD-SETUP.md#projects-beta).

Sources: [memory and instruction discovery](https://code.claude.com/docs/en/memory),
[skills](https://code.claude.com/docs/en/skills),
[cloud sessions](https://code.claude.com/docs/en/claude-code-on-the-web),
[projects](https://code.claude.com/docs/en/claude-projects),
[headless mode](https://code.claude.com/docs/en/headless).

## Adoption contract

1. Review this kit, then obtain authorization for the intended installation scope.
2. Make the shared policy available as an immutable local snapshot in every environment
   that runs the assistant. A remote URL in an instruction file is not automatically loaded.
3. Ensure the project has a filled, vendor-neutral `AGENTS.md`. Fill the Claude project
   adapter's bindings; resolve every `{{PLACEHOLDER}}`.
4. Merge adapters into existing instructions without discarding existing agreements.
   Do not copy the whole shared policy into either adapter.
5. Inspect the final instruction chain and skill discovery in a fresh session before use.
   Record the result in the project-local installation record.

## Capability and adoption record

- Documentation checked: 2026-10-10; Projects documentation 2026-10-17
- Actual app/surface and installed version: Claude Code desktop app, CLI 2.1.265 reported
  by `claude --version` on macOS, observed 2026-10-10
- Observed discovery on that build: a repository `AGENTS.md` and a home-directory
  `AGENTS.md` were loaded as project instructions when no `CLAUDE.md` existed in those
  directories, although the docs date automatic `AGENTS.md` reading to v2.1.277.
  Treat the fallback as version-dependent and keep the explicit import.
- Repository read capability: verified in the Conductor checkout
- Authorized project-record write capability: local files only; GitHub writes need the
  task's own authorization
- Native instruction/skill discovery: verify in a fresh session per LOCAL-SETUP.md; the
  Conductor repository's own result is in its project-local installation record
- Tested/adopted practice tag and SHA: locally adopted 2026-10-10 against the review-branch
  source; the exact kit commit is recorded in the project-local installation record, not here
- Stable responsibilities: perform authorized tasks and report evidence under shared
  policy; no cross-provider control assumed
- Project-specific adoption and active assignment: stored only in that project
