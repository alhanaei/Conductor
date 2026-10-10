# Codex / ChatGPT coding surfaces

Setup draft only. Use [shared policy](../../shared/WORKFLOW.md); current jobs belong in project issues.

- Shared entrypoint: root `AGENTS.md`; global local preferences can live in `~/.codex/AGENTS.md`. Inspect narrower instructions and override files.
- Project skills: `.agents/skills/<name>/SKILL.md`; personal skills: `~/.agents/skills/<name>/SKILL.md`. Keep required project skills in the repository snapshot; local home files should not be assumed present in a cloud task.
- Native long-running mode: current docs show `/goal` in desktop, interactive Codex CLI and IDE extension. For hosted web work, use the supported Work surface with explicit outcome, constraints and review criteria. Verify the actual mode instead of assuming the command works everywhere.
- Current Codex Cloud uses reusable environments prepared and tested from repositories, then published for isolated task workspaces. Environment publication is configuration work requiring user authorization here. Preserve existing environments. The older Cloud setup flow is explicitly labeled legacy; do not apply legacy-only setup instructions to the new surface.

Sources: [AGENTS.md](https://learn.chatgpt.com/docs/agent-configuration/agents-md), [skills](https://learn.chatgpt.com/docs/build-skills), [long-running work](https://learn.chatgpt.com/docs/long-running-work), [Cloud environments](https://learn.chatgpt.com/docs/environments/cloud-environments)


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
