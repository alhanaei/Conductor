# Initializer validation — 11 October 2026

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
