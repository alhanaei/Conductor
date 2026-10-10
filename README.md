# Shared GitHub workflow for coding and analytics

Conductor is the canonical shared practice library for the assistant apps you already use. Common workflow, status definitions, reusable skills, techniques, architecture patterns and harness contracts live here. Each real project repository owns its specific plans, ADRs, issues, progress, ownership, checkpoints, code and safe data-output references. Usually one assistant works on a project at a time; parallel work is an explicitly approved exception.

This kit is documentation and templates only. It installs no root/global instructions, native skills, credentials, integrations, schedules or runtime. The former application is retired to Git history. There is no project directory or current-state ledger in this library.

## Start here
- [Full guide](GUIDE.md), with its generated [editable Word export](docs/shared-github-workflow-coding-analytics.docx)
- [Common workflow](shared/WORKFLOW.md)
- [Read-only bootstrap prompt](shared/prompts/bootstrap.md)
- [Assistant setup and discovery](assistants/README.md)
- [Contribution and release process](docs/contributing.md)
- [Dated source register](sources/SOURCE-REGISTER.md)

## Structure
- `shared/workflows/`: complete coding, analytics, review and handoff procedures
- `shared/skills/`: minimal skill wrappers; generate native copies only after discovery is verified
- `shared/techniques/`: reusable practical methods
- `shared/patterns/`: general architecture options; actual decisions remain project ADRs
- `shared/harness/`: portable task/checkpoint schema, fictional examples and contract guidance
- `shared/templates/`: blank templates to adapt inside the real project, never a live project ledger here
- `shared/prompts/`: reusable adoption, task, review and resume prompts
- `assistants/<vendor>/`: thin setup, capabilities, entrypoints, known limits and tested/adopted version metadata
- `docs/`: contributions, compatibility and releases
- `sources/`: primary evidence checked on 9 October 2026

## Adoption
Read first. Confirm an immutable released source SHA and the project's authority before changing files. A project's adopted-version record and task records belong in that project. If native discovery requires a local copy, generate only the necessary adapter/snapshot with source path, SHA and hash manifest. Do not maintain hand-edited duplicate master policy. Check for newer reviewed releases at session start; adopt compatible updates only within authority, report breaking changes, and never silently change mid-task policy.

No app is assumed to read private chats or control another vendor's sessions. A connected authorized assistant can read project records; it writes only through supported authorized tools. Otherwise it returns a standard update for the user or another authorized recorder.

## Validation
The manifest lists every packaged file and SHA-256. Contract examples use fictional URLs and dummy identities; they grant no authority. Schema validation checks structure, not truthful evidence, access or semantic completion. Native discovery and a single-owner project checkpoint/handoff test remain required adoption checks.
