# Local setup — instructions only

Nothing in this kit installs itself. Run these steps only in a separately authorized
installation. Review and back up existing destination files; append to an existing
`~/.claude/CLAUDE.md` and merge into an existing root `CLAUDE.md` rather than overwriting.

## Prepare a fixed source

Choose either a clean Conductor checkout at an approved full commit ID containing this kit,
or a reviewed artifact with recorded checksums. The checkout base recorded in the manifest
does not contain the kit. Replace the example values before running these read-only checks:

```sh
CONDUCTOR_SOURCE='/absolute/path/to/pinned/Conductor'
CONDUCTOR_REVISION='{{APPROVED_FULL_COMMIT_ID}}'
git -C "$CONDUCTOR_SOURCE" rev-parse HEAD
git -C "$CONDUCTOR_SOURCE" status --porcelain --untracked-files=all
git -C "$CONDUCTOR_SOURCE" rev-parse --verify "$CONDUCTOR_REVISION^{commit}"
(cd "$CONDUCTOR_SOURCE/assistants/claude-code" && shasum -a 256 -c SHA256SUMS)
```

Require the actual HEAD to equal the approved full ID and the status to be clean. A
checksum detects change; establish trust by reviewing the artifact and its source. Keep
the selected source fixed; avoid symlinks to a moving checkout.

## Install deliberately

| Source under this kit | Destination |
| --- | --- |
| Root `shared/WORKFLOW.md` and the files it links | Fixed snapshot, for example `~/.claude/conductor/snapshots/<commit>/shared/`; a snapshot already pinned for another assistant may be reused when its digest matches |
| `global/CLAUDE.md` | `~/.claude/CLAUDE.md` (append and fill) |
| `global/skills/conductor-handoff/` | `~/.claude/skills/conductor-handoff/` (whole directory) |
| `global/skills/conductor-init/` | `~/.claude/skills/conductor-init/` (whole directory, including bundled recipe, helper and template) |
| `project/CLAUDE.md` | Actual project repository root `CLAUDE.md` (merge and fill) |
| `project/skills/project-verification/` | Actual project `.claude/skills/project-verification/` (whole directory) |

The project must already have a filled `AGENTS.md`; the Claude adapter imports it and adds
nothing project-specific beyond the policy binding and checkpoint path. The global adapter
needs an absolute shared-policy path that works across repositories. The project adapter
may point to the same snapshot or a vendored copy with the same digest. Vendored copies
are pinned distributions, not independently edited policy masters. Record the Conductor
source ID, policy digest, installed file digests and destination mapping in a
project-local installation record. Compute SHA-256 with `shasum -a 256 FILE` on macOS or
`sha256sum FILE` on Linux. Fill all adapter placeholders using verified facts.

Discovery rules to respect while installing:

- A root `CLAUDE.md` stops Claude Code from reading `AGENTS.md` by itself. Keep the
  `@AGENTS.md` import as the first line of the installed project adapter.
- Imports resolve relative to the file that contains them. Do not import the home-directory
  snapshot from the project file; a project import outside the working directory prompts
  for approval on every machine. Reference the path in backticks instead.
- Personal skills win over project skills with the same name. Install `conductor-handoff`
  only at user scope and `project-verification` only at project scope, so no name is
  installed twice for Claude Code. Copies for other assistants live in other directories
  (`.agents/skills/`) that Claude Code does not read.
- `CLAUDE.local.md`, `.claude/rules/` and `claudeMdExcludes` settings can change what
  loads. Inspect them before and after installation.
- Instructions load once per session. Start a fresh session after installation, or run
  `/reload-skills` for a newly created skills directory.

## Confirm and maintain

In a fresh Claude Code session at the actual project root, run `/context` and `/skills`,
then ask it to list the loaded instruction sources, read the pinned policy and report its
digest, name the discovered skills, and explain the project's verification commands
without executing them. Check the report against the files. Scan the installed files for
unresolved `{{...}}` placeholders. A headless check is possible with
`claude -p --max-turns 1` and a prompt asking for the loaded sources; it still uses a
model turn, so record it as a model-reported observation.

Adopt upgrades as reviewed changes between tasks: compare source diffs, update snapshots,
digests and installation records together, then start a fresh session. For rollback,
restore the backed-up `~/.claude/CLAUDE.md`, remove only the files this installation
added, and restart. Do not discard unrelated edits made since installation. No GitHub
publication is implied by local installation.
