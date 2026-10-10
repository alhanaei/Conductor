# Local setup — instructions only

Nothing in this kit has been installed on the Mac or any user's home. Run these steps only
in a separately authorized installation. Review and back up existing destination files;
merge content rather than overwriting an existing `AGENTS.md` or skill directory.

## Prepare a fixed source

Choose either a clean Conductor checkout at an approved full commit ID containing this kit,
or a reviewed artifact with recorded checksums. The checkout base recorded in the manifest does not contain the kit. Use the
full commit ID that actually contains the reviewed kit, or its reviewed artifact digests.

For a future committed checkout, replace the example values before running these read-only
checks (the values are deliberate placeholders):

```sh
CONDUCTOR_SOURCE='/absolute/path/to/pinned/Conductor'
CONDUCTOR_REVISION='{{APPROVED_FULL_COMMIT_ID}}'
git -C "$CONDUCTOR_SOURCE" rev-parse HEAD
git -C "$CONDUCTOR_SOURCE" status --porcelain --untracked-files=all
git -C "$CONDUCTOR_SOURCE" rev-parse --verify "$CONDUCTOR_REVISION^{commit}"
```

Require the actual HEAD to equal the approved full ID and the status to be clean. For an
artifact, verify its recorded file digests instead. A checksum detects change; establish
trust by reviewing the artifact and its source, not by accepting an untrusted digest alone.
Keep the selected source fixed; avoid symlinks to a moving checkout.

## Install deliberately

| Source under this kit | Destination |
| --- | --- |
| `shared/PRACTICE.md` plus referenced root `shared/` files | Fixed snapshot preserving relative layout, or bind directly to root `shared/WORKFLOW.md` |
| `global/AGENTS.md` | `${CODEX_HOME:-$HOME/.codex}/AGENTS.md` (merge and fill) |
| `global/skills/conductor-handoff/` | `$HOME/.agents/skills/conductor-handoff/` (whole directory) |
| `project/AGENTS.md` | Actual project repository root `AGENTS.md` (merge and fill) |
| `project/skills/project-verification/` | Actual project `.agents/skills/project-verification/` (whole directory) |

The global adapter needs an absolute shared-policy path that works across repositories.
The project adapter may point to the same snapshot or a vendored copy with the same digest.
Vendored copies are pinned distributions, not independently edited policy masters.
Record the Conductor source ID, policy digest, installed skill digests, and destination
mapping in a project-local installation record. Compute SHA-256 with `shasum -a 256 FILE`
on macOS or `sha256sum FILE` on Linux. Fill all adapter placeholders using verified facts.
Project skill commands come from the filled project verification contract.

Inspect global and project `AGENTS.override.md` and nested instructions before merging:
an override takes precedence within its directory, and deeper guidance can supersede
earlier guidance. Instructions are loaded once per run/session; start a fresh session
after installation. Keep the instruction chain within the configured size limit (default
32 KiB). These discovery details follow the [official AGENTS.md guide](https://learn.chatgpt.com/docs/agent-configuration/agents-md).

User skills live under `.agents/skills`, independently of `CODEX_HOME`. Check for duplicate
skill names across scopes; same-name skills do not override each other. Rename intentionally
and update references, or remove a superseded installation only with authorization.
See the [official skills guide](https://learn.chatgpt.com/docs/build-skills).

## Confirm and maintain

In a fresh Codex session at the actual project root, ask it to list loaded instruction
sources, read the pinned policy and report its digest, identify discovered skills, and
explain the project's verification commands without executing them. Check the report
against the files. Scan the installed files for unresolved `{{...}}` placeholders.

Adopt upgrades as reviewed changes between tasks: compare source diffs, update snapshots,
digests and installation records together, then start a fresh session. For rollback,
restore the backed-up files or prior pinned snapshot and restart. Do not discard unrelated
edits made since installation. No GitHub publication is implied by local installation.

The compatibility entrypoint links to the repository-root shared workflow. Do not copy
it alone. Verify the root MANIFEST.json and preserve all referenced shared files at the
same reviewed revision; the entrypoint digest alone does not verify the workflow.
