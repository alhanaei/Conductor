# Two-stage project initialization

## Stage one: generate the native initializer

Resolve the named target and authority, assistant surface, scope (project/global), and
execution location (local/cloud) separately. The reference helper supports project scope
for Codex and Claude Code; it does not modify saved cloud environments or home instructions. Inspect
existing rules, overrides, native skills, adoption/version records and checkpoints.
Keep the existing policy pin; any upgrade needs an explicit reviewed migration.

Select a reviewed Conductor source. Accept a clean Git checkout whose HEAD is the full
requested 40-character SHA, verifying packaged bytes against Git blobs, root manifest
and native checksums. For an artifact, obtain an independent manifest SHA-256 from the
reviewed distribution; a self-computed digest does not establish identity. If the
manifest does not bind the assistant's native checksum file (`codex/SHA256SUMS` or
`assistants/claude-code/SHA256SUMS`), supply its independent SHA-256 too. The
artifact's association with the claimed commit must be established outside the helper.
Never treat a moving branch or dirty source as the requested immutable revision.

Verify native capabilities using primary documentation and, where available, observed
discovery. Record evidence, assistant, surface, scope, execution location, native skill
folder and instruction entrypoint. Unsupported or unverified features mean an inactive
draft. The Codex profile uses `.agents/skills` and root `AGENTS.md`. The Claude Code
profile uses `.claude/skills` and a root `CLAUDE.md` that imports `AGENTS.md`, so project
facts live in `AGENTS.md` and `PROJECT.md` for every assistant. Respect overrides,
narrower rules and instruction-size limits during the fresh-session check.

From the generic skill folder, preview the reference generator:

```sh
python3 scripts/conductor_init.py generate --target /approved/project --source /reviewed/Conductor --source-sha <full-sha> --capabilities /approved/scratch/capabilities.json
```

For an independently identified artifact, add `--manifest-sha <external-sha256>`.
After reviewing the changes, add `--apply` if setup is authorized. Stage one creates
`conductor-project-init/` under the assistant's native skills folder (`.agents/skills/`
or `.claude/skills/`) containing native instructions, helper, pinned source snapshot and
metadata. No effective project `AGENTS.md` is created yet.
Generator/helper/template identities are separate from the policy source commit.
An older compatible policy can be pinned by a newer reviewed generator.

To update an unmodified generated skill after reviewing a newer generator,
preview the same command with `--update`, then add `--apply` within setup authority.
This retains the same policy and capability pin; custom edits remain blocked for
reconciliation. Updating the skill does not silently rewrite project adoption. Moving an
existing adoption to a different policy source is the `migrate` operation, described in
the [policy migration workflow](migration.md); `generate` at a new pin points there.

For another assistant, generate an equivalent thin native project-init skill using
this shared procedure and that assistant's verified native mapping. Keep shared policy
canonical; translate entrypoints and discovery, not policy. Package the recipe and
pinned policy references needed for the generated skill to work independently. If no
native loader exists, supply an explicitly read draft and describe manual invocation.
The helper rejects unknown mappings; it does not claim a universal adapter.

## Stage two: onboard the actual project

Invoke the generated skill. Discover facts from project-owned files, approved input
references and user choices: name, software/analytics kind, purpose, repository,
lifecycle, authoritative task records, checkpoint path, and verification commands or
procedures with cwd, prerequisites, expected results and source evidence. Unknown
optional facts stay unknown. Do not invent architecture, tools, CI, datasets, storage,
deployment gates or tests. Missing essential facts leave an inactive draft with exact
gaps reported.

Project lifecycle is **Active**, **Parked**, or **Closed**. Keep it separate from task
progress (Backlog, Ready, In progress, Review, Done) and execution state (Ready, Running,
Waiting quota, Blocked, Needs approval, null). Project links identify authoritative task
records; do not create a competing ledger. Done requires verification/review and null
execution state. Preserve current owners; labels are not locks or authority to take
over. Closed needs an explicitly authorized transition; Parked adoption starts no work.

Preview `onboard` with the generated helper and evidenced facts JSON. Apply within the
authorized target. Generate a thin root adapter, managed project facts, project-owned
adoption record, relative pinned snapshot and an absent setup checkpoint. Never put
project state in Conductor. The adoption record is shared: a second assistant onboarding
the same project reuses the recorded facts and pin, adds only its native skill and
instruction file, and leaves the first assistant's entries intact. When more than one
generated initializer exists, name the one to use with `--skill-root`. Preserve user text outside owned markers, existing
checkpoint content and custom native skills as complete directories. An effective
override, unowned markers, changed generated content, owner/fact conflicts or changed
pin blocks automatic replacement. Migration and reconciliation stay explicit.

Store real prior contents and before/after hashes in a project-local transaction before
updates. An identical rerun leaves bytes and mtimes unchanged, including metadata.
Rollback restores/removes only files whose current hash equals the transaction's
installed hash; it refuses intervening edits and keeps unrelated files. Retention is
a separate project decision. The helper preflights paths and uses atomic file replacement
with failure recovery. It is not a concurrency lock or crash-atomic multi-file transaction;
run setup with exclusive access to the named target. Never delete unknown files to fit.

Check packaging, source binding and native discovery separately. Report installed,
verified packaging, observed discovery, draft/blocked items and unrun checks distinctly.
Fresh native discovery may require a new session. Project commands are recorded, never
executed by setup. Dependencies, credentials, hooks, schedules, publication, deployment
and cloud configuration are outside initialization scope.
