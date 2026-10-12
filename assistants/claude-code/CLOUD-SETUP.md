# Cloud setup — instructions only

Claude Code has two remote modes that behave differently. A cloud session (claude.ai/code
or `claude --cloud`) runs on hosted infrastructure from a fresh clone of the repository's
remote branch. Remote Control drives a session that still runs on the local machine and
sees local files. Treat each cloud environment as a separate installation. This kit
changes no saved home files, credentials, permissions or published environment.

## What reaches a cloud session

Carried over from the repository: root `CLAUDE.md`, `.claude/rules/`, `.claude/skills/`,
`.claude/agents/`, `.claude/commands/`, and repository `.claude/settings.json` hooks and
permissions in a single-repository session. Not carried over: `~/.claude/CLAUDE.md`,
personal `~/.claude/skills/`, user-scope plugins and MCP servers, and local or managed
settings files. Skills enabled on the claude.ai account load separately.

Consequences for this kit:

- The project adapter and `project-verification` skill travel with the repository once
  committed and pushed. The global adapter and `conductor-handoff` do not.
- The shared-policy snapshot must be readable inside the clone. Prefer a vendored, pinned
  copy of `shared/WORKFLOW.md` inside the repository with its digest recorded in
  `AGENTS.md`, or a cloud setup script that places the snapshot at the bound path. A
  home-directory path from the Mac does not exist remotely.
- A cloud session uses the pushed branch, not local uncommitted edits. Confirm the exact
  remote revision before relying on adapters or policy copies in that session.

## Acceptance check in a new cloud session

1. Confirm actual repository identity and revision; inspect existing changes without reset.
2. Run `/context` and `/skills`; compare loaded memory files and skills with the intended
   mapping. Expect no personal skills unless the account provides them.
3. Resolve and read the pinned policy; compare its hash and source ID to the project binding.
4. Confirm `project-verification` is discovered and no confusing duplicate exists.
5. Resolve all required placeholders and identify real verification commands without
   running application code merely to install this documentation kit.
6. Record the environment identity, source binding and discovery result in the project's
   installation record. Stop dependent work on missing files or mismatches.

GitHub access must be supported and working before any remote operation; authentication
does not authorize writes. Prepare local progress drafts if posting is not authorized.
No central runtime, distributed lock service, chat migration or simultaneous assistants
are required to use this kit. Follow the canonical [shared practice](../../shared/WORKFLOW.md).
