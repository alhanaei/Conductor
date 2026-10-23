> Blank project-owned template. Adapt and keep the completed record in the real project repository, not in Conductor.

# Project facts and execution map

Fill this from observed repository files and current official documentation. Do not invent values. Keep this document short and update when the project actually changes.

- Project / repository / visibility:
- Lifecycle: Active / Parked / Closed (explicit project decision)
- Authoritative task/issue records and ownership references:
- Task progress: Backlog / Ready / In progress / Review / Done (in the linked records)
- Execution state: Ready / Running / Waiting quota / Blocked / Needs approval / null (separate from progress)
- Default branch and protected branches:
- Approval mode (manual, or auto once branch protection is recorded) and integration branch:
- Runtime/tool versions and authoritative version files:
- Package managers and lockfiles:
- Install/bootstrap command and prerequisites:
- Build command:
- Lint / format check:
- Typecheck:
- Unit tests:
- Integration / end-to-end tests:
- Test fixtures / local services / permitted test data:
- Existing CI workflow paths and required checks:
- Manual staging gate and authorized operator:
- Manual production gate and authorized operator:
- Known baseline failures, with dated evidence:
- Architecture entrypoints and public interfaces:
- Generated files and regeneration commands:
- Analytics definitions, source-of-truth datasets and approved storage:
- Sensitive paths / prohibited data handling:
- Checkpoint destination and retention:
- Instruction and skill discovery diagnostics per platform:
- Last verified UTC date / evidence commit:

Record this project’s own verified CI and release boundaries. Do not import another project’s deployment rules.

Keep lifecycle separate from task progress and execution state. Closed requires an
authorized transition before new work; Parked does not resume implicitly. Labels are
not ownership locks. Done requires verification, review and null execution state.
Keep the actual ledger at its authoritative task links, not in this blank template.
