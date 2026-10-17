> Blank project-owned template. Adapt and keep the completed record in the real project repository, not in Conductor.

# Task contract: <task-id>

## Outcome
- User-visible result / decision this supports:
- Task type: implementation / analytics / independent review
- Task record / issue link:
- Priority (exactly one from the project scale) and owner-blocked marker, if any:
- Category (exactly one project kind):
- Parent task, when this is a part of tracked work:
- Selection basis (highest open priority; tie-break reference):
- Request source and authorized scope:
- Owner platform/session:
- Authenticated GitHub actor and credential route, if used:
- Assignment approved by / evidence:
- Task attempt/session reference:
- Independent reviewer:
- Integrator / final approver:

## State
- Project lifecycle source record/link (do not duplicate its live value here):
- Task Status: Backlog / Ready / In progress / Review / Done
- Execution state: Ready / Running / Waiting quota / Blocked / Needs approval / none active
- Blocker or waiting reason:
- Next eligible time, if known:
- Last checkpoint and exact next action:
- Last confirmed state, timestamp and reporting app:
- Freshness: current / stale / unknown

## Workspace and boundaries
- Repository and visibility:
- Base branch and exact base SHA:
- Task branch/worktree/cloud workspace:
- Owned files/components/data outputs:
- Read-only context:
- Interfaces/dependencies with other tasks:
- Out of scope:

## Acceptance criteria
Number each observable behavior or analytical result. For each, identify the test, inspection or calculation that will establish it.
1. Criterion:
   Evidence:

## Execution
- Required environment, runtime and commands:
- Approved inputs, data snapshot/version and location:
- Existing CI checks to preserve:
- Milestones and checkpoint locations:
- Compute/time budget if specified:
- Known risks and baseline failures:

## Authorization
- Local file edits permitted:
- GitHub push / PR allowed? Exact repository, branch and purpose:
- Additional external write actions explicitly allowed:
- Deployment: no, unless a separate exact authorization is recorded
- Spend / paid API / top-up: no, unless amount, provider and purpose are approved
- Credential or access changes: no; request separate approval and use secure setup
- Private data may go to these explicitly approved destinations only:

## Stop / pause conditions
Stop when acceptance criteria and required review gates are established within the authorized scope. Pause the affected work for missing authority, irreconcilable requirements, unavailable essential data, usage limits or verified infrastructure blockers. Preserve a handoff instead of starting a new paid route or widening access. Continue unaffected authorized work when useful.

## Completion record
- Exact delivered SHA or artifact identifiers:
- Verification results and unresolved exceptions:
- Independent review result against SHA:
- Next user decision / gate:
