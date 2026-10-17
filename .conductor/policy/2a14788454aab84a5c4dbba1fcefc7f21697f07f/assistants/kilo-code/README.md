# Kilo Code

Setup draft only. Use [shared policy](../../shared/WORKFLOW.md); current jobs belong in project issues.

Current Kilo docs recognize root `AGENTS.md`; current skill documentation supports `.agents/skills` and native `.kilo/skills`. Use one discovered location, preferably the existing shared wrappers, and verify your CLI/extension version because legacy behavior differs. Current docs distinguish trusted global skills from project skills for embedded shell execution. Keep these wrappers text-only and do not rely on embedded shell expansion, old mode-specific folders or Claude compatibility without checking the installed product. Kilo is a separate client/provider route, not proof of included Grok Build or other subscription usage.

Sources: [custom instructions](https://kilo.ai/docs/customize/custom-instructions), [skills](https://kilo.ai/docs/customize/skills)


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
