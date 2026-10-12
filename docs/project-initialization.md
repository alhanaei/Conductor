# Generate a project initializer, then onboard the project

[Conductor Init](../shared/skills/conductor-init/SKILL.md) is the portable repository
source skill. It generates an assistant-specific **conductor-project-init** skill, then
that skill onboards the named project. The
[Codex source adapter](../codex/global/skills/conductor-init/SKILL.md) and the
[Claude Code source adapter](../assistants/claude-code/global/skills/conductor-init/SKILL.md)
carry the same helper, recipe and template for independent distribution. No folder
implies a personal installation.

Ask the assistant:

> Use conductor-init to generate a native project initializer for this assistant,
> then use it to onboard my named project from the verified Conductor source. Preserve
> existing instructions, task records and checkpoints. Preview changes first.

The reference helper needs Python 3 and, for Git sources, Git. It installs no packages.
Use a clean reviewed checkout pinned to a full SHA or a reviewed artifact with
independently recorded digests. Do not publish the author's active local adapters.
Existing adoptions keep their policy pin.

## Working Codex example

Save this profile in an approved scratch directory. Confirm it for the actual surface
before setting `verified` true. Native paths are documented in
[skills](https://learn.chatgpt.com/docs/build-skills) and
[instructions](https://learn.chatgpt.com/docs/agent-configuration/agents-md).

```json
{
  "assistant": "codex",
  "surface": "cli",
  "scope": "project",
  "execution": "local",
  "native_skills": ".agents/skills",
  "native_instructions": "AGENTS.md",
  "verified": true,
  "evidence_ref": "https://learn.chatgpt.com/docs/build-skills"
}
```

From the source skill folder, preview:

```sh
python3 scripts/conductor_init.py generate --target /approved/project --source /reviewed/Conductor --source-sha <full-sha> --capabilities /approved/scratch/capabilities.json
```

Review, then repeat with `--apply` for authorized setup. Artifact sources add
`--manifest-sha <independent-digest>`. Older manifests not covering
`codex/SHA256SUMS` also require `source_codex_checksums_sha256` in the profile from
the independent distribution. The helper cannot prove an artifact digest's external
association with its claimed commit.

## Working Claude Code example

The same helper accepts a verified Claude Code profile. Native paths are documented in
[skills](https://code.claude.com/docs/en/skills) and
[memory](https://code.claude.com/docs/en/memory); confirm them for the actual surface
before setting `verified` true.

```json
{
  "assistant": "claude-code",
  "surface": "desktop",
  "scope": "project",
  "execution": "local",
  "native_skills": ".claude/skills",
  "native_instructions": "CLAUDE.md",
  "verified": true,
  "evidence_ref": "https://code.claude.com/docs/en/skills"
}
```

Stage one then creates `.claude/skills/conductor-project-init/` without Codex UI
metadata, pinned to `assistants/claude-code/SHA256SUMS` instead of `codex/SHA256SUMS`.
Stage two writes the same `AGENTS.md` and `PROJECT.md` managed sections as Codex, installs
`.claude/skills/project-verification/`, and adds a managed section to `CLAUDE.md` whose
first line is `@AGENTS.md`, because a root `CLAUDE.md` stops Claude Code from reading
`AGENTS.md` on its own. An existing `@AGENTS.md` line outside the section is not
duplicated. Invoke the generated skill as `/conductor-project-init`.

A project onboarded by Codex can be onboarded by Claude Code afterwards, and vice versa,
with the same facts: the shared `AGENTS.md` section is left byte-identical, each assistant
keeps its own native skills, and `.conductor/adoption.json` lists both under `assistants`.
When both generated initializers exist, pass `--skill-root` to `onboard`.

## Facts and onboarding

Invoke `$conductor-project-init` (Codex) or `/conductor-project-init` (Claude Code) in the
target, or explicitly read its SKILL.md while fresh native discovery is pending. It
gathers evidenced facts JSON, for example:

```json
{
  "name": "Example service",
  "kind": "software",
  "purpose": "Serve the documented project API",
  "repository": "https://github.com/example/service",
  "lifecycle": "Active",
  "task_records": ["TASKS.md"],
  "checkpoint": ".conductor/HANDOFF.md",
  "architecture": "unknown",
  "verification": [{
    "name": "Project check",
    "command": "python3 checks.py",
    "cwd": ".",
    "prerequisites": "Documented project runtime",
    "expected": "Exit 0",
    "source": "checks.py"
  }]
}
```

This is fictional: task files and verification sources must actually exist and support
the facts. Analytics projects use `kind: analytics`, approved data/storage references,
reproduction or reconciliation procedures, units and tolerances relevant to their
evidence. No software test suite is inferred. Manual procedures can be recorded as
commands when their reproducible steps are evidenced by the named project document.

From the target project (use `.claude/skills/...` for the Claude Code copy):

```sh
python3 .agents/skills/conductor-project-init/scripts/conductor_init.py onboard --target . --facts /approved/scratch/facts.json
```

Review, then repeat with `--apply`. Outputs: managed sections in `AGENTS.md` and
`PROJECT.md` (plus `CLAUDE.md` for Claude Code), `.conductor/adoption.json`,
`.conductor/policy/<sha>/`, an absent setup checkpoint and an absent/unmodified native
verification skill. Existing custom skills, other assistants' files and text outside
managed sections remain intact. Bindings are relative,
with SHA/digests; generator provenance is separate from policy provenance.

Project/global scope and local/cloud execution are independent. `execution: cloud`
does not create a saved cloud environment or expand project installation scope.

## Reruns, rollback and limitations

Identical reruns are exact no-ops. Missing essential facts or unsupported capabilities
return `draft`. Changed managed content, overrides, owner/pin/fact conflicts and Closed
projects need reconciliation. There is no automatic policy upgrade or force-overwrite
switch; migration and lifecycle transitions remain explicit reviewed steps. To update
an unmodified generated skill with a reviewed newer generator, use `generate --update`
(preview, then `--apply`) with the same policy and capability pin. This updates helper
and template identity without silently rewriting project adoption. Other native adapters
use the portable generation/update procedure after capability verification.

Backups contain real previous contents. Preview rollback with the reported transaction:

```sh
python3 .agents/skills/conductor-project-init/scripts/conductor_init.py rollback --target . --transaction .conductor/backups/<id>/transaction.json
```

Add `--apply` for authorized rollback. It refuses subsequent edits. Keep exclusive
access during setup: atomic per-file writes do not make a multi-file crash-atomic
transaction or acquire a writer lock. Project commands never run during installation.
Confirm effective precedence and discovery separately in a fresh native session;
packaging checks do not confirm every assistant or hosted surface. The Codex and Claude
Code mappings have executable references here; other native mappings remain drafts
until verified. Initialization grants no implementation, home/global editing, credential,
schedule, publication, deployment or cloud-configuration authority.

## Source maintenance and validation

The [canonical recipe](../shared/workflows/project-init.md), helper and native-output
template live under `shared/`. Run `python3 tests/package_conductor_init.py --write`
to regenerate recipe/helper/template distribution copies and manifests; run without
`--write` to check them. The root manifest binds native checksums without self-hashes.

Run isolated fixtures:

```sh
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s tests -v
```

The Codex tests archive historical policy commit `9d7743620ee23c6e2219878fea314ea47b1941b1`
and use disposable software/analytics projects. They check both stages, preservation,
repeatability, trust/path boundaries, lifecycle/ownership and rollback. The Claude Code
tests build their fixture from this package's own manifest-bound files, so the packaging
check must be current; they cover the native layout, the `AGENTS.md` import, shared
records across both assistants and rollback. Tests are not installed into generated
projects.

See the [validation record](initializer-validation.md) for actual test results and the
independent forward evaluation's scope and limitations.
