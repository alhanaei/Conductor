# Conductor local documentation adoption — local project instructions

Local adapter for the approved review-branch source. Reusable source templates remain unchanged. Checkout-local task records are Git metadata; Conductor is not a work ledger for unrelated projects.

## Shared practice binding

- Local shared-policy file: `/Users/dr.ahmedalhanaee/.codex/conductor/snapshots/9d7743620ee23c6e2219878fea314ea47b1941b1/shared/WORKFLOW.md`
- Expected SHA-256: `0a8dc78dbaaa801e6f93fcffe02dbd2e46231dddaaa7fac7c69bf259fe4ee04a`
- Conductor source revision or reviewed artifact identity: `9d7743620ee23c6e2219878fea314ea47b1941b1`
- Read and verify that file at task start. Follow it as the canonical common workflow.
  If absent, unresolved, or inconsistent with global guidance, report the mismatch and
  pause dependent work. Do not fetch or switch to a moving policy version silently.

## Project facts and boundaries

| Fact | Verified value |
| --- | --- |
| Purpose and acceptance criteria | Shared workflow/instruction source library; this local task installs and verifies fixed policy bindings and native Codex discovery, without implementing an orchestrator. |
| Repository identity | https://github.com/alhanaei/Conductor; checkout /Users/dr.ahmedalhanaee/GitHub/Conductor |
| Stack and supported runtime versions | Markdown, JSON and DOCX documentation; observed Codex CLI 0.144.1; Python 3 standard library for local integrity checks. No application runtime. |
| Architecture and important boundaries | README.md, shared/WORKFLOW.md and docs/contributing.md; codex/ contains distribution templates, assistants/codex/README.md records capabilities. |
| Plan and issue source | docs/contributing.md defines contribution process. No active issue or plan URL was supplied; this authorized task is local adoption only. Return status to the user/authorized recorder without inventing an issue or publishing. |
| Checkpoint file (includes current owner) | /Users/dr.ahmedalhanaee/GitHub/Conductor/.git/conductor-local/checkpoint.md |
| Code and output locations | Canonical files remain in shared/, codex/, assistants/ and docs/. Local active adapter: AGENTS.md; skill: .agents/skills/project-verification/. Local adoption records are Git metadata, not a library-wide work ledger. |
| Data sources, allowed storage, sensitive areas | Documentation only. Preserve existing files and private configuration. No secrets, restricted datasets, runtime installs, deployments, credentials/access changes or other-repository sweeps. |
| Additional scoped instructions / skills | Global ~/.codex/AGENTS.md and personal ~/.agents/skills/conductor-handoff/. Project skill .agents/skills/project-verification/. Inspect narrower overrides on entering subdirectories; codex/ template AGENTS.md files are unfilled installation sources. |

## Verification contract

Fill each row with exact commands, working directories, prerequisites, expected outcomes,
and the evidence file or CI job that establishes the command. Do not execute placeholders.
Mark inapplicable checks explicitly with a reason. Do not infer commands from another repo.

| Check | Command / procedure, cwd, prerequisites, expected result, source |
| --- | --- |
| Focused code tests | Not applicable — documentation adoption has no application runtime. Use the defined integrity procedure below. |
| Required lint / type / build checks | `python3 /Users/dr.ahmedalhanaee/GitHub/Conductor/.git/conductor-local/verify_installation.py`, cwd `/Users/dr.ahmedalhanaee/GitHub/Conductor`, Python 3 standard library only; expect exit 0. Checks root MANIFEST.json, codex/SHA256SUMS, fixed snapshot, readable JSON, active adapter bindings, installed skill hashes, preserved user rules and tracked Git state. Evidence: `/Users/dr.ahmedalhanaee/GitHub/Conductor/.git/conductor-local/verification.json`. |
| Analytics reproduction and reconciliation | Not applicable — no analytical data or calculations in this task. |
| Evidence storage | /Users/dr.ahmedalhanaee/GitHub/Conductor/.git/conductor-local/verification.json |

Use the installed `project-verification` skill for applicable checks. Use the installed
`conductor-handoff` skill for checkpoints if available; the shared workflow remains usable
without automatic skill discovery. Store current objective, owner, branch/revision, policy
binding, decisions, results, blockers, and next action in the project checkpoint.

## Current adoption authority and precedence

The user authorized fetching this review branch and installing local Codex adapters. For this task, do not commit, push, merge main, deploy, alter canonical shared source, create schedules, or update unrelated projects. These explicit task limits take precedence over inherited commit/push defaults. One accountable assistant owns this task; authorized bounded delegation does not transfer ownership. No local owner note or GitHub label is an exclusive lock.


<!-- conductor:init:begin -->
# Conductor project adapter

Read `.conductor/policy/aa235f87dd5f3c23dc7f14ec00fcdc505c58d6b6/shared/WORKFLOW.md` as the pinned common policy.
Policy commit: `aa235f87dd5f3c23dc7f14ec00fcdc505c58d6b6`; SHA-256: `0a8dc78dbaaa801e6f93fcffe02dbd2e46231dddaaa7fac7c69bf259fe4ee04a`.
Read `PROJECT.md` for project facts, verification and authoritative task links.
Verification contract: the Verification contract section in `PROJECT.md`; read its source evidence before executing checks.
Keep project lifecycle separate from task progress and execution state.
Respect Parked/Closed lifecycle and confirmed task ownership; initialization does not start work.
Checkpoint destination: `.conductor/HANDOFF.md`. Read existing checkpoints before resuming.
Verify recorded checks before reporting task completion; never infer an unrecorded command.
This adapter grants no deployment, credential, cloud, scheduling, or publication authority.
<!-- conductor:init:end -->
