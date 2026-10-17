# Global Claude Code baseline — TEMPLATE

Installation: merge into the user's `~/.claude/CLAUDE.md` only after review. Keep existing
personal rules; append this section below them.

- Read applicable project instructions and inspect existing work before changes.
- Read the canonical shared practice at `{{GLOBAL_SHARED_PRACTICE_FILE}}` explicitly at
  task start. Verify its SHA-256 against `{{GLOBAL_SHARED_PRACTICE_SHA256}}`. These values
  must identify an available, fixed local snapshot; a remote URL does not load it.
- Apply that common practice without duplicating it here. If a project pins a different
  version, surface the discrepancy and resolve the binding before dependent work.
- Keep project facts, commands, state, and evidence in the project's own instructions
  and records. Never assume a global project path, stack, test command, or data source.
- Report missing policy bindings rather than inventing them. Do not update shared policy
  or skills during a task without explicit direction and a recorded transition.
- One accountable assistant per project is the shared default. Standing worktree or
  delegation authorization applies to bounded tasks within that ownership; it does not
  imply control of another provider's sessions or authorization for conflicting assignments.
