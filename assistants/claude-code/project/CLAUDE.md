@AGENTS.md

# {{PROJECT_NAME}} — Claude Code project adapter TEMPLATE

Fill and merge into this project's root `CLAUDE.md` before use. The first line imports the
project's vendor-neutral `AGENTS.md`, which holds the project facts, boundaries and
verification contract that every assistant reads. If this project has no filled
`AGENTS.md`, create one from the shared project adapter template first; do not restate
the project facts here. Resolve required bindings; use `not applicable — reason` only for
optional facts. Keep live task state in the checkpoint, not in Conductor.

## Shared practice binding

- Local shared-policy file: `{{PROJECT_SHARED_PRACTICE_FILE}}`
- Expected SHA-256: `{{PROJECT_SHARED_PRACTICE_SHA256}}`
- Conductor source revision or reviewed artifact identity: `{{CONDUCTOR_SOURCE_ID}}`
- Read and verify that file at task start. Follow it as the canonical common workflow.
  If absent, unresolved, or inconsistent with the imported `AGENTS.md` or global guidance,
  report the mismatch and pause dependent work. Do not fetch or switch to a moving policy
  version silently.

## Claude Code specifics

- Project skills: `.claude/skills/project-verification/` runs the verification contract
  defined in `AGENTS.md`; `.claude/skills/gate-review/` reviews a phase against its
  lifecycle gate (G0–G5) and returns a decision for the project record. Personal skill:
  `~/.claude/skills/conductor-handoff/` prepares the project checkpoint at
  `{{PROJECT_CHECKPOINT_PATH}}`. The shared workflow remains usable without skill discovery.
- Same-named skills installed for other assistants (for example `.agents/skills/`) are
  pinned copies of the same source; do not edit one copy independently.
- Explicit task limits recorded in `AGENTS.md` or the checkpoint take precedence over
  inherited commit, push, worktree or delegation defaults.
