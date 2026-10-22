# Initializer validation

## 22 October 2026 — claude-code-projects adapter profile (#47)

`conductor_init.py generate --profile claude-code-projects` and `check --profile
claude-code-projects` added. The profile reads an adopted project's `.conductor/adoption.json`,
the `PROJECT.md` facts and the pinned policy file, and writes the filled project-instructions
text and an owner checklist under `.conductor/adapters/claude-code-projects/`, the three
always-on lines in the `CLAUDE.md` managed section (kept by later `onboard` runs), and the
text's digest, inputs and `discovery` field under `adapters.claude-code-projects` in the
adoption record. The kit's `PROJECT-INSTRUCTIONS.template.md` is now generated from the
helper's template by `tests/package_conductor_init.py`. `tests/test_conductor_init_projects.py`
(8 tests) compares the four outputs with `tests/golden/claude-code-projects/`, asserts the
field limit, the policy path and digest, the verification commands and the fallback boundary
steps, checks that `check` names a changed record digest, an edited file, an edited `CLAUDE.md`
section and changed inputs, and runs the helper against this repository expecting
`unchanged` and `verified`. Suite: 80 tests.

```sh
python3 tests/package_conductor_init.py
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s tests
git diff --check
```

## 17 October 2026 — wrapper copies rule

`tests/package_conductor_init.py` now fails when a kit listed in `NATIVE` lacks a native
copy of a `shared/skills` wrapper under its `global/skills/`, naming the kit and the skill.
`WRAPPER_ALIASES` maps a shared name to a kit's name (`checkpoint-handoff` is carried as
`conductor-handoff`); `WRAPPER_ALLOWLIST` records deliberate omissions per kit with the task
record that tracks each, and an entry whose copy exists fails as stale so the list shrinks
as copies land. `tests/test_package_check.py` covers the missing, aliased, allowlisted,
stale and per-kit cases and runs the rule on the repository itself. Suite: 72 tests.
Allowlist at the first green run on `main`: the Codex kit for `coding-task`, `analytics-task`,
`independent-review` and `backlog-task` (copies requested on #15); the Claude Code kit for
`backlog-task` only, the other three having landed with PR #23.

## 12 October 2026 — Claude Code mapping added

Validated the helper after adding the Claude Code native profile, on disposable projects
using Python 3.12.7. No real project, personal instructions, credentials, cloud
environment or deployment was modified by these tests.

Evaluated helper SHA-256:
`85f55cac3f77aea10946dae576a1ce2f80a62890e6a1a531aadfd16bc4423a13`.

```sh
python3 tests/package_conductor_init.py
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s tests -v
git diff --check
```

**57 tests passed**: the 47 Codex tests unchanged, plus 10 Claude Code tests in
`tests/test_conductor_init_claude.py`. The Claude Code tests build their fixture from the
package's own manifest-bound working-tree files, so they also prove the packaging check is
current. They cover: the generated `.claude/skills/conductor-project-init/` layout without
Codex UI metadata and pinned to `assistants/claude-code/SHA256SUMS`; onboarding that writes
the shared `AGENTS.md` and `PROJECT.md` sections, installs `.claude/skills/project-verification/`
and adds a `CLAUDE.md` section beginning with `@AGENTS.md`; an existing `@AGENTS.md` line
not duplicated and existing rules preserved; exact-byte repeat no-ops; mismatched or
unverified mappings rejected without writes; Codex then Claude Code onboarding the same
project with one byte-identical `AGENTS.md` section, both native skills, both assistants in
`.conductor/adoption.json`, and both reruns unchanged; a second assistant blocked from
changing shared facts; automatic location of a single generated skill and refusal when two
exist; rollback restoring an original `CLAUDE.md`; and generated-skill portability.

Packaging checks passed: 80 root digests, 16 Codex digests, 12 Claude Code digests, equality
of canonical and distributed helper/template/recipe for both kits, frontmatter, template
placeholders, resource links and absence of author paths. Native fresh-session discovery
for the generated Claude Code skill was not observed in this run.

## 11 October 2026 — Codex reference

Validated the two-stage source generator and the Codex native example on disposable
projects using Python 3.14.6. No real project, personal instructions, credentials, cloud
environment or deployment was modified by these tests.

Evaluated helper SHA-256:
`2aa0041de7d95e6da22c7f09336146589ec7871eb621457a6fa45857c3754834`.

## Reproducible behavioral checks

```sh
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s tests -v
python3 tests/package_conductor_init.py
git diff --check
```

**47 tests passed.** The suite covers both setup stages, software and analytics facts,
local/cloud profiles with project-only scope, dry runs, exact byte/mtime no-op reruns,
existing instructions and custom native skills, reviewed generator updates, lifecycle
and owner conflicts, overrides, missing facts/capabilities, backup restoration and
refusal after later edits, atomic replacement failure, path traversal/symlinks and
reserved path collisions, manifest/native asset integrity and generation metadata.
Git source tests verify clean raw blobs and reject dirty/staged sources without running
configured clean filters or fsmonitor commands.

Fixtures archive policy commit `9d7743620ee23c6e2219878fea314ea47b1941b1` and supply
independent manifest/checksum identities; additional Git-source cases create disposable
local commits. They do not rely on the author's active adapters or home files.

Packaging checks passed: **67 root digests, 16 Codex digests**, equality of canonical and
distributed helper/template/recipe, basic required frontmatter, quoted UI metadata,
skill resource links and absence of author paths/scaffold tokens. The Skill Creator
`quick_validate.py` invocation could not run because PyYAML is unavailable; no dependency
was installed. The dependency-free package check validates this package's simple scalar
frontmatter, not the full YAML grammar.

## Independent forward evaluation

An independent assistant received only the raw source skill and realistic software and
analytics fixture files. It generated native project-init skills, previewed/applied
onboarding, derived facts from the files, performed reviewed generator updates to the
helper identity above and verified the resulting projects.

- Software remained Active; analytics remained Parked with its confirmed owner preserved.
- All 11 original files' content was preserved. Project workload commands were not run.
- Each project verified 57 generated asset digests, 56 adoption file digests, both
  managed sections, project task/checkpoint/evidence links and backup hashes.
- Final generation and onboarding reruns returned `unchanged`, preserving bytes and mtimes.
- No setup blockers, home/cloud changes, dependency installs, commits or pushes occurred
  during the fixture evaluation.

## Limits

Only Codex has an executable native reference adapter. Other assistants follow the
portable generation procedure after verifying their native mapping; unsupported mappings
remain inactive drafts. Native fresh-session discovery and hosted-cloud behavior were
not observed in this evaluation. An artifact's association with its declared Git commit
depends on the independently reviewed distribution identity. Policy migrations and
lifecycle transitions remain explicit review steps. Atomic individual writes do not
provide a concurrent-writer lock or a crash-atomic multi-file transaction.
