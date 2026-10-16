# Grok Build

Setup draft only. Use [shared policy](../../shared/WORKFLOW.md); current jobs belong in project issues.

Use root `AGENTS.md`; native project skills live under `.grok/skills/<name>/SKILL.md`. Grok also documents Claude compatibility, but native placement plus a discovery check is less ambiguous than relying on inherited compatibility. The documented `grok inspect` command identifies discovered configuration/instructions/skills; run only if installed and available.

Important non-portability: Grok's documented `allowed-tools` skill metadata does not grant or restrict tools; certain other frontmatter fields are accepted but not applied. Do not use a skill header as a permission boundary. Verify actual Build subscription/account access separately from Grok chat, Grok Bot, xAI API and any third-party host.

Sources: [skills and compatibility](https://docs.x.ai/build/features/skills-plugins-marketplaces), [CLI reference](https://docs.x.ai/build/cli/reference), [overview](https://docs.x.ai/build/overview)


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
