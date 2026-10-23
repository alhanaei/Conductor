# Generate a project initializer, then onboard the project

[Conductor Init](../shared/skills/conductor-init/SKILL.md) is the portable repository
source skill. It generates an assistant-specific **conductor-project-init** skill, then
that skill onboards the named project. The
[Claude Code source adapter](../assistants/claude-code/global/skills/conductor-init/SKILL.md)
carries the same helper, recipe and template for independent distribution. No folder
implies a personal installation.

Ask the assistant:

> Use conductor-init to generate a native project initializer for this assistant,
> then use it to onboard my named project from the verified Conductor source. Preserve
> existing instructions, task records and checkpoints. Preview changes first.

The reference helper needs Python 3 and, for Git sources, Git. It installs no packages.
Use a clean reviewed checkout pinned to a full SHA or a reviewed artifact with
independently recorded digests. Do not publish the author's active local adapters.
Existing adoptions keep their policy pin.

## Working Claude Code example

Save this profile in an approved scratch directory. Native paths are documented in
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

From the source skill folder, preview:

```sh
python3 scripts/conductor_init.py generate --target /approved/project --source /reviewed/Conductor --source-sha <full-sha> --capabilities /approved/scratch/capabilities.json
```

Review, then repeat with `--apply` for authorized setup. Artifact sources add
`--manifest-sha <independent-digest>`. A manifest that does not bind the kit's
`SHA256SUMS` also requires `source_native_checksums_sha256` in the profile from the
independent distribution. The helper cannot prove an artifact digest's external
association with its claimed commit.

Stage one creates `.claude/skills/conductor-project-init/` pinned to
`assistants/claude-code/SHA256SUMS`. Stage two writes the managed `AGENTS.md` and
`PROJECT.md` sections every assistant reads, installs `.claude/skills/project-verification/`,
and adds a managed section to `CLAUDE.md` whose first line is `@AGENTS.md`, because a root
`CLAUDE.md` stops Claude Code from reading `AGENTS.md` on its own. An existing `@AGENTS.md`
line outside the section is not duplicated. Invoke the generated skill as
`/conductor-project-init`.

The helper's profile table is the only place it names a product. An adoption record
written by an earlier generator for another assistant is read as data: its entries stay
under `assistants`, `assistant_pins` and `generator_sha256`, and the owner migrates them
when that assistant's generated profile exists again.

## Facts and onboarding

Invoke `/conductor-project-init` in the target, or explicitly read its SKILL.md while
fresh native discovery is pending. It gathers evidenced facts JSON, for example:

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

From the target project:

```sh
python3 .claude/skills/conductor-project-init/scripts/conductor_init.py onboard --target . --facts /approved/scratch/facts.json
```

Review, then repeat with `--apply`. Outputs: managed sections in `AGENTS.md`, `PROJECT.md`
and `CLAUDE.md`, `.conductor/adoption.json`, the pinned snapshot `.conductor/policy/<sha>/shared/`
(the policy file and the files it links, nothing else), an absent setup checkpoint and an
absent/unmodified native verification skill. Existing custom skills, other assistants'
files and text outside managed sections remain intact. Bindings are relative, with
SHA/digests; generator provenance is separate from policy provenance. The pin itself is
one file plus its digest: `.conductor/adoption.json` records `policy_commit` and
`policy_sha256`, the SHA-256 of `shared/WORKFLOW.md` at that commit, and the `AGENTS.md`
section repeats both.

Project/global scope and local/cloud execution are independent. `execution: cloud`
does not create a saved cloud environment or expand project installation scope.

## Migrating to a newer policy source

An adoption stays at its pin until the owner approves a migration. From the new source's
skill folder, preview and then apply:

```sh
python3 scripts/conductor_init.py migrate --target /approved/project --source /reviewed/Conductor --source-sha <new-full-sha>
```

The first assistant to migrate moves the shared record: the `AGENTS.md` section, the policy
snapshot (the previous one is removed in the same transaction, whatever it contained), its
own generated skill and its verification skill when the record owns it. Every other
assistant listed in the record runs the same command for its own skill; until it does, its
`onboard` is blocked and `.conductor/adoption.json` lists it under `assistant_pins` at the
previous pin. The record keeps the history under `migrations`. Rollback uses the
migration's transaction. Personal and global adapters are moved by hand under the same
decision. The full procedure is [shared/workflows/migration.md](../shared/workflows/migration.md).

## Reruns, rollback and limitations

Identical reruns are exact no-ops. Missing essential facts or unsupported capabilities
return `draft`. Changed managed content, overrides, owner/pin/fact conflicts and Closed
projects need reconciliation. There is no automatic policy upgrade or force-overwrite
switch; migration and lifecycle transitions remain explicit reviewed steps. To update
an unmodified generated skill with a reviewed newer generator, use `generate --update`
(preview, then `--apply`) with the same policy and capability pin. This updates helper
and template identity without silently rewriting project adoption.

Backups contain real previous contents and live under `.conductor/backups/`, which the
project should ignore in Git: they are local recovery data for the machine that ran the
setup, not shared state. Preview rollback with the reported transaction:

```sh
python3 .claude/skills/conductor-project-init/scripts/conductor_init.py rollback --target . --transaction .conductor/backups/<id>/transaction.json
```

Add `--apply` for authorized rollback. It refuses subsequent edits. Keep exclusive
access during setup: atomic per-file writes do not make a multi-file crash-atomic
transaction or acquire a writer lock. Project commands never run during installation.
Confirm effective precedence and discovery separately in a fresh native session;
packaging checks do not confirm every assistant or hosted surface. Only the profiles in
the helper's table have executable references here; other native mappings remain drafts
until verified. Initialization grants no implementation, home/global editing, credential,
schedule, publication, deployment or cloud-configuration authority.

The generated skill still vendors the whole verified source tree under `assets/source/`
so that `onboard` can re-verify its pin offline. Replacing that copy with a fetch at the
pinned commit changes the generator's identity checks and is a separate record on the
Backlog issue, not part of the single re-pin.

## Source maintenance and validation

The [canonical recipe](../shared/workflows/project-init.md), helper and native-output
template live under `shared/`. Run `python3 tests/package_conductor_init.py --write`
to regenerate recipe/helper/template distribution copies and manifests; run without
`--write` to check them. The root manifest binds native checksums without self-hashes.

Run isolated fixtures:

```sh
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s tests -v
```

Every suite builds its fixture from this package's own manifest-bound files at the
current `HEAD`, so the packaging check must be current and no historical commit needs to
be reachable. The suites use disposable software/analytics projects and cover both
stages, preservation, repeatability, trust/path boundaries, lifecycle/ownership, the
`shared/`-only snapshot, the recorded policy digest, migration and rollback. Tests are not
installed into generated projects.
