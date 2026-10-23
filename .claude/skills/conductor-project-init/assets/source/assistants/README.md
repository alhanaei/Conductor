# Assistant setup notes

This folder holds the one kit Conductor distributes (ADR 0002): stable setup, capabilities,
entrypoints, known limitations and adoption verification for Claude Code. Active jobs and
project facts remain in real project repositories. The kit references the canonical
[common workflow](../shared/WORKFLOW.md); it does not duplicate it, and nothing in `shared/`
names a product, so any other assistant can read `shared/` as plain documentation.

For project setup, use the [portable conductor-init skill](../shared/skills/conductor-init/SKILL.md)
and [initialization usage](../docs/project-initialization.md). The recipe is included in the
skill folder; policy and project templates still come from the verified adopted Conductor source.

A generated native adapter or required snapshot must record source SHA/path/hash and its own
hash in the project-owned adoption manifest. See [contributing](../docs/contributing.md).

- [Claude Code](claude-code/README.md): installable templates, native copies of the shared
  skill wrappers, Projects brief template, cloud and local setup notes

Adapters for other assistants are generated from `shared/` by profile, as ADR 0004 decides,
and appear here as generated output when their profile lands. The retired hand-written notes
for other vendors are recoverable from the Git tag on the last multi-kit commit.
