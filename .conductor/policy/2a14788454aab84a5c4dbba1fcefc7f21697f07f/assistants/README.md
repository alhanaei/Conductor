# Assistant setup notes

These folders hold stable setup, capabilities, entrypoints, known limitations and adoption verification only. Active jobs and project facts remain in real project repositories. All adapters reference the canonical [common workflow](../shared/WORKFLOW.md); they do not duplicate it.

Official documentation was checked on 9 October 2026. Actual installed versions, account entitlement, tools and permissions are unverified until tested in the target app. Files here are setup drafts, not installed native entry files. For plain chat without native discovery, explicitly attach or read the verified procedure.

For project setup, use the [portable conductor-init skill](../shared/skills/conductor-init/SKILL.md)
and [initialization usage](../docs/project-initialization.md). The recipe is included in the
skill folder; policy and project templates still come from the verified adopted Conductor source.

Use the platform folder below. A generated native adapter or required snapshot must record source SHA/path/hash and its own hash in the project-owned adoption manifest. See [contributing](../docs/contributing.md).

- [Codex / ChatGPT coding surfaces](codex/README.md); installable templates in the root [codex/](../codex/README.md) kit
- [Claude Code](claude-code/README.md); installable templates in the same folder, sharing skill names and bodies with the Codex kit
- [GitHub Copilot](copilot/README.md)
- [Google Antigravity and Jules](google/README.md)
- [Grok Build](grok-build/README.md)
- [Kilo Code](kilo-code/README.md)

- [ChatGPT app](chatgpt/README.md)
