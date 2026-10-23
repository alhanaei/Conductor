<!-- conductor:init:begin -->
# Conductor Claude Code adapter

Project facts, policy binding and verification contract are in the imported `AGENTS.md` and in `PROJECT.md`; nothing is restated here.
Native skills: `.claude/skills/conductor-project-init` for setup and `.claude/skills/project-verification` for recorded checks.
Explicit task limits in `AGENTS.md` or the checkpoint take precedence over inherited commit, push, worktree or delegation defaults.

Pinned policy: `.conductor/policy/084387daacd2bae8a307ab4671e3d4d95f135f56/shared/WORKFLOW.md` (SHA-256 `539902dd4198ebd101bb0b49a4211949ab031f5b2766497213d734e175133f6c`); `PROJECT.md` holds the facts and the verification contract.
Every task starts with `/task-start #N` on a record carrying `status:ready` and ends with `/task-finish`; between them your own practice runs.
Never merge, mark a draft ready, approve, force-push, change CI or push to `main`; verification is the recorded commands run on the exact head, nothing inferred.
<!-- conductor:init:end -->