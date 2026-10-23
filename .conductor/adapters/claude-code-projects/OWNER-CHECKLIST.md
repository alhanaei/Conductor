# Owner checklist: Claude Code Projects adapter for Conductor

Generated for policy commit `2a14788454aab84a5c4dbba1fcefc7f21697f07f`. Each step needs the owner's account or repository settings; a thread never changes them. Record the evidence for each on the task record.

- [ ] Paste [.conductor/adapters/claude-code-projects/project-instructions.md](.conductor/adapters/claude-code-projects/project-instructions.md) into **Project settings > Memory > Project instructions** (5425 of 16000 characters) and record its SHA-256 `78c7551d0a64b5605ec8b053b7ba2a64ddee80f528caffbace2ae347710f9830` on the task record.
- [ ] Enable the boundary skills `task-start` and `task-finish` on the claude.ai account from the kit's `global/skills/` and record the SHA-256 of each uploaded `SKILL.md` from the kit `SHA256SUMS`; repository skills do not load in a thread.
- [ ] Create the Backlog issue, pin it, and keep it the only queue.
- [ ] Set the repository variable `CONDUCTOR_BACKLOG_REVIEW_ISSUE` to that issue's number so the backlog review names it.
- [ ] On `main`, require a pull request, turn **Do not allow bypassing** on, keep approvals off, and require the `verify` and `linked-task` checks; merging stays the owner's own action.
- [ ] From one new thread, have it quote its loaded memory files and its skill list, confirm `.conductor/policy/2a14788454aab84a5c4dbba1fcefc7f21697f07f/shared/WORKFLOW.md` resolves with SHA-256 `adefbfa603a3b050593035410ce07bbb42fd27ebbfa4ba0212d48fcbe7a4a0b2`, run `conductor_init.py check --profile claude-code-projects --target .`, and record the result and date under `adapters.claude-code-projects.discovery` in `.conductor/adoption.json`.
