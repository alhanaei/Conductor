---
name: conductor-init
description: Generate a native Claude Code project initializer from a verified Conductor pin, then use it to onboard a software or analytics project while preserving existing rules and records.
---

# Generate a Claude Code project initializer

Read [the shared procedure](references/project-init.md). Resolve the named target,
verified source SHA, project scope, execution location and native capabilities.
The [helper](scripts/conductor_init.py) generates `.claude/skills/conductor-project-init/`
with the [native template](assets/project-skill.md), relative policy snapshot and
generation metadata. Preview `generate`, apply authorized setup, then invoke the
generated `/conductor-project-init` to gather facts and preview/apply onboarding.

Onboarding writes the same vendor-neutral `AGENTS.md` and `PROJECT.md` managed sections
that every assistant reads, plus a thin `CLAUDE.md` section whose first line is
`@AGENTS.md`, because a root `CLAUDE.md` stops the automatic `AGENTS.md` read.
A project already onboarded by another assistant keeps its record; reuse the facts in
`.conductor/adoption.json` so both assistants share one pin and one set of facts.

Preserve project instructions, `CLAUDE.local.md`, custom skills, task records and
checkpoints. Missing facts or unavailable capabilities mean an inactive draft. Changed
managed content or an existing pin needs reconciliation; do not guess or overwrite.
Lifecycle and task state remain separate. Setup starts no implementation and grants
no home/global, credential, cloud, deployment or publication authority.

Install this whole source folder personally (`~/.claude/skills/conductor-init/`) only
when that separate scope is requested. Helper/recipe/template are generated copies of
canonical shared sources. Native discovery remains unverified until observed in a fresh
target session with `/context` and `/skills`.
