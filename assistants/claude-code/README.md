# Claude Code

Setup draft only. Use [shared policy](../../shared/WORKFLOW.md); current jobs belong in project issues.

Root `CLAUDE.md` can be the following thin adapter:

    @AGENTS.md

    Read the project task and the canonical procedure at the verified adopted source path.
    Preserve all existing project-specific instructions below this adapter.

Current Claude Code can load AGENTS.md directly starting at v2.1.277, but an existing CLAUDE.md above/in the working directory can change that behavior. The documented explicit import avoids assuming fallback discovery. Verify actual loaded instructions using the session's diagnostics.

Project skills: `.claude/skills/<name>/SKILL.md`. Personal local skills: `~/.claude/skills/<name>/SKILL.md`; those local files are not automatically available in cloud sessions. Account-synced skills are a separate feature requiring the right account context. Cloud sessions run on hosted infrastructure and persist after the laptop closes; terminal Remote Control is distinct. A new CLI cloud task can use the remote branch rather than local unpushed edits, so confirm the precise source revision and any upload path before sending private repository content.

Sources: [memory and instruction discovery](https://code.claude.com/docs/en/memory), [skills](https://code.claude.com/docs/en/skills), [cloud sessions](https://code.claude.com/docs/en/claude-code-on-the-web)


## Capability and adoption record
- Documentation checked: 2026-10-09
- Actual app/surface and installed version: unverified
- Repository read capability: verify in target app
- Authorized project-record write capability: verify; otherwise use user-mediated recording
- Native instruction/skill discovery: verify in a fresh session using the documented diagnostics
- Tested/adopted practice tag and SHA: not adopted
- Last runtime verification and evidence: not performed
- Stable responsibilities: perform authorized tasks and report evidence under shared policy; no cross-provider control assumed
- Project-specific adoption and active assignment: stored only in that project
