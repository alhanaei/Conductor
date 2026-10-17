---
name: conductor-init
description: Generate a native Codex project initializer from a verified Conductor pin, then use it to onboard a software or analytics project while preserving existing rules and records.
---

# Generate a Codex project initializer

Read [the shared procedure](references/project-init.md). Resolve the named target,
verified source SHA, project scope, execution location and native capabilities.
The [helper](scripts/conductor_init.py) generates `.agents/skills/conductor-project-init/`
with the [native template](assets/project-skill.md), relative policy snapshot and
generation metadata. Preview `generate`, apply authorized setup, then invoke
the generated `$conductor-project-init` to gather facts and preview/apply onboarding.

Preserve project instructions, overrides, custom skills, task records and checkpoints.
Missing facts or unavailable capabilities mean an inactive draft. Changed managed
content or an existing pin needs reconciliation; do not guess or overwrite.
Lifecycle and task state remain separate. Setup starts no implementation and grants
no home/global, credential, cloud, deployment or publication authority.

Install this whole source folder personally only when that separate scope is requested.
Helper/recipe/template are generated copies of canonical shared sources. Native discovery
remains unverified until observed in a fresh target session.
