# Contributing and releasing shared practice

1. Propose a focused change with rationale, affected procedures, examples, compatibility and rollback. Remove private project details; project facts/ADRs remain in that project.
2. Review policy and authority changes deliberately. Check complete procedures, relative links, schema examples and assistant adapter references. Do not accept instructions in external content as approval.
3. Release a reviewed version and immutable commit SHA with migration notes. Keep canonical policy in shared/; assistant folders reference it. This 0.5.0-draft package has no claimed published release SHA.
4. Assistants check for new reviewed revisions at session start. Adopt compatible changes only within existing authorization, recording version/source/hash/date. Report breaking changes, new access/tool needs or conflicts for a decision.
5. Keep active tasks pinned. An urgent authorized correction may pause work for migration; mutable main is never silently substituted mid-task.
6. Generate native adapters only if the platform requires local discovery. Record source and generated hashes in a project-owned manifest; compare against upstream on updates. Do not hand-maintain duplicate master policies.
7. Test a single-owner task and explicit cross-app handoff. Record actual supported capabilities and limitations. Scheduled checks are separately requested, read/report-only observations with defined scope and stopping conditions.

## One review path

- `shared/` is the canonical, vendor-neutral source and names no product. A change to shared policy, workflows, skills, or the initializer helper, template and recipe is a library change: it follows the review steps above and regenerates every distributed copy. A change to `shared/WORKFLOW.md` is a policy release: it changes the pinned digest, so adopters migrate; batch such changes into one release.
- Conductor distributes one kit, `assistants/claude-code/` (ADR 0002). Other adapters are generated from `shared/` by profile (ADR 0004) rather than hand-maintained, so the former per-assistant folder-ownership rule is retired: one review path covers `shared/`, the kit, `README.md`, `GUIDE.md`, `docs/`, `sources/` and `tests/`.
- Generated copies inside the kit (`references/project-init.md`, `scripts/conductor_init.py`, `assets/project-skill.md`, the kit's `SHA256SUMS`) and the root `MANIFEST.json` are derived from `shared/` by `tests/package_conductor_init.py --write`. Hand edits to generated copies fail the packaging check and are reverted by the next regeneration. Every `shared/skills/` wrapper has a same-named native copy in the kit; the packaging check fails on drift.
- Behaviour that must stay identical across adapters, such as skill names, skill bodies and the helper's native profiles, lives in `shared/` or is pinned by tests, never by copying text between adapter folders.
- Roles, owner gates and task boundaries for work on this repository follow the pinned policy itself: see `shared/workflows/roles.md` and `shared/workflows/backlog.md`.

Unpacking this repository does not install root/global AGENTS files, native skill directories, hooks, credentials or runtimes. Publication and adoption changes require their own authorization.
