> Blank project-owned template. Adapt and keep the completed record in the real project repository, not in Conductor.

# Handoff: <task-id>

- Updated at UTC:
- Current state and reason for handoff:
- Original outcome and task-contract path:
- Current owner / intended next owner:
- Repository / base SHA / head SHA:
- Branch / PR / issue links, if published with authorization:
- Local-only or cloud-only artifacts and how to retrieve them:
- Dirty tracked files / untracked files / unstaged changes:

## What is complete
List completed acceptance criteria with evidence. Separate implemented from verified.

## Verification ledger
For each check: exact command, runtime/data version, tested SHA, date, result, log/artifact path. Identify baseline failures and skipped checks.

## Decisions and useful discoveries
Record decisions, short rationale, assumptions and relevant source paths. Do not include secrets, raw confidential datasets or private reasoning transcripts.

## Remaining work
List the next concrete actions in execution order, starting with the next command or file to inspect. Include blockers, reproduction steps, failing output summary and unresolved review findings.

## Authority and environment
- Approved actions that remain applicable, with original user request reference:
- Actions still awaiting approval:
- Required services, dependencies and safe configuration names, without values:
- Active processes/jobs with verified identifiers and states:
- Temporary resources needing cleanup and authority to stop them:
- Quota/time limit observed, if any; do not guess remaining usage:

## Resume check
The next agent must read the contract and this record, verify the actual repository/worktree and SHA, inspect the diff, and reconcile any newer changes before editing. Re-run a targeted baseline check. Confirm ownership has transferred; do not run two writers on the same branch/worktree. A prior agent's success claim is not substitute evidence.


## Cross app handoff
- Last confirmed state, timestamp and reporting app:
- Update freshness: current / stale / unknown
- What is in shared records versus still local:
- Ownership release and reassignment confirmation:
- New app read/write capability check:

Do not infer running work from a missing update. Resume approved artifacts in a new app session; no private-chat migration or universal provider control is implied. If direct publication is unavailable, provide this record for the user or another authorized assistant to post.
