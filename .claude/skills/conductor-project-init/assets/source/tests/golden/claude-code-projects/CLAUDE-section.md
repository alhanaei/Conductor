<!-- conductor:init:begin -->
# Conductor Claude Code adapter

Project facts, policy binding and verification contract are in the imported `AGENTS.md` and in `PROJECT.md`; nothing is restated here.
Native skills: `.claude/skills/conductor-project-init` for setup and `.claude/skills/project-verification` for recorded checks.
Explicit task limits in `AGENTS.md` or the checkpoint take precedence over inherited commit, push, worktree or delegation defaults.

Pinned policy: `.conductor/policy/2a14788454aab84a5c4dbba1fcefc7f21697f07f/shared/WORKFLOW.md` (SHA-256 `adefbfa603a3b050593035410ce07bbb42fd27ebbfa4ba0212d48fcbe7a4a0b2`); `PROJECT.md` holds the facts and the verification contract.
Every task starts with `/task-start #N` on a record carrying `status:ready` and ends with `/task-finish`; between them your own practice runs.
Never merge, mark a draft ready, approve, force-push, change CI or push to `main`; verification is the recorded commands run on the exact head, nothing inferred.
<!-- conductor:init:end -->