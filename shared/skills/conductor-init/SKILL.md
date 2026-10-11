---
name: conductor-init
description: Generate an assistant-specific project-initialization skill from verified Conductor policy and native capabilities, then use that skill to onboard a named software or analytics project.
---

# Conductor initializer generator

Use two stages: generate the assistant's native **conductor-project-init** skill, then
invoke it to onboard the named project. Read
[the generation and onboarding procedure](references/project-init.md).

Resolve target, scope, execution location, assistant surface and immutable policy source
from the user's request or an existing verified binding. Read the source's
`shared/WORKFLOW.md`. Preserve an existing adoption's pin. Verify native skill paths,
instruction entrypoints and precedence from current primary docs or observed discovery;
never assume another assistant implements Codex features.

The [standard-library helper](scripts/conductor_init.py) implements project-scoped
Codex generation and onboarding. Its [output template](assets/project-skill.md) is the
working native example. Other assistants use the same procedure to generate a thin
native initializer after verifying their mapping. Unsupported capabilities produce a
reviewable inactive draft. File copying does not prove native discovery.

Keep policy snapshots immutable, relative to the destination, and bound by full commit
SHA and digests. Record generator identity separately. Never copy the author's Mac paths
or local metadata. Preview first; apply only authorized setup. Preserve instructions,
overrides, records and custom skills; changed managed content needs reconciliation.
Setup grants no implementation, global changes, publication, credential, scheduling or
cloud authority. Personal installation of this repository source is a separate action.

The bundled recipe is generated from `shared/workflows/project-init.md`; maintain that
canonical file and regenerate copies rather than editing duplicate procedures.
