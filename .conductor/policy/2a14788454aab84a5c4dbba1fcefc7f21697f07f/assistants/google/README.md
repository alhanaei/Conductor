# Google Antigravity and Jules

Setup draft only. Use [shared policy](../../shared/WORKFLOW.md); current jobs belong in project issues.

Google AI Ultra's current benefits page includes Antigravity and Jules. This is not a guarantee of unlimited usage, current account access or interchangeable API credits; check actual availability and quota in each product. Do not reduce the Google route to a historical Gemini CLI entitlement.

Antigravity currently recognizes `AGENTS.md` and `GEMINI.md` and uses `.agents/skills`; legacy `.agent/skills` remains supported. Start with the shared AGENTS.md and one skill location. If extra modular rules are needed, `.agents/rules/*.md` requires documented YAML such as `trigger: always_on`; unsupported/missing triggers can silently discard rules. Avoid extra rules if AGENTS.md suffices.

Jules documents root `AGENTS.md` and repository environment setup. The reviewed Jules documentation did not establish discovery of the Agent Skills SKILL.md format. Treat Jules as AGENTS.md plus explicit task/workflow references until the actual product and current official docs demonstrate skill support. Its setup should invoke verified project preparation/testing steps and preserve existing CI, not invent a new pipeline.

Sources: [Google AI Ultra benefits](https://support.google.com/googleone/answer/16286513?hl=en), [Antigravity rules](https://www.antigravity.google/docs/rules), [Antigravity skills](https://www.antigravity.google/docs/skills), [Jules AGENTS.md](https://jules.google/docs/), [Jules environment setup](https://jules.google/docs/environment/)


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
