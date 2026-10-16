# {{PROJECT_NAME}} — project instructions TEMPLATE

Fill and merge into this project's root `AGENTS.md` before use. Resolve required bindings;
use `not applicable — reason` only for optional facts. Keep live task state in the checkpoint,
not in Conductor. Paths below are relative to this repository unless explicitly absolute.

## Shared practice binding

- Local shared-policy file: `{{PROJECT_SHARED_PRACTICE_FILE}}`
- Expected SHA-256: `{{PROJECT_SHARED_PRACTICE_SHA256}}`
- Conductor source revision or reviewed artifact identity: `{{CONDUCTOR_SOURCE_ID}}`
- Read and verify that file at task start. Follow it as the canonical common workflow.
  If absent, unresolved, or inconsistent with global guidance, report the mismatch and
  pause dependent work. Do not fetch or switch to a moving policy version silently.

## Project facts and boundaries

| Fact | Verified value |
| --- | --- |
| Purpose and acceptance criteria | {{PROJECT_PURPOSE_AND_ACCEPTANCE}} |
| Repository identity | {{PROJECT_REPOSITORY}} |
| Stack and supported runtime versions | {{PROJECT_STACK_AND_VERSIONS}} |
| Architecture and important boundaries | {{PROJECT_ARCHITECTURE_PATH}} |
| Plan and issue source | {{PROJECT_PLAN_AND_ISSUE_SOURCE}} |
| Checkpoint file (includes current owner) | {{PROJECT_CHECKPOINT_PATH}} |
| Code and output locations | {{PROJECT_DELIVERABLE_PATHS}} |
| Data sources, allowed storage, sensitive areas | {{PROJECT_DATA_AND_ACCESS_RULES}} |
| Additional scoped instructions / skills | {{PROJECT_SCOPED_GUIDANCE}} |

## Verification contract

Fill each row with exact commands, working directories, prerequisites, expected outcomes,
and the evidence file or CI job that establishes the command. Do not execute placeholders.
Mark inapplicable checks explicitly with a reason. Do not infer commands from another repo.

| Check | Command / procedure, cwd, prerequisites, expected result, source |
| --- | --- |
| Focused code tests | {{PROJECT_FOCUSED_TESTS}} |
| Required lint / type / build checks | {{PROJECT_REQUIRED_CHECKS}} |
| Analytics reproduction and reconciliation | {{PROJECT_ANALYTICS_VERIFICATION}} |
| Evidence storage | {{PROJECT_VERIFICATION_EVIDENCE_PATH}} |

Use the installed `project-verification` skill for applicable checks. Use the installed
`conductor-handoff` skill for checkpoints if available; the shared workflow remains usable
without automatic skill discovery. Store current objective, owner, branch/revision, policy
binding, decisions, results, blockers, and next action in the project checkpoint.
