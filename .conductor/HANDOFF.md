# Conductor project checkpoint and handoff

Written 2026-10-18 by the main Claude Code cloud session
`https://claude.ai/code/session_01V7XrcQW1m9NzsCJDWAADjz` for a new planning session.
Verify every fact below against the repository and GitHub before relying on it; this file is
a record, not authority. Private chat does not migrate; this file and the issue comments it
names are the handoff. It supersedes the 2026-10-16 checkpoint (every item done) and the
draft in PR #32 from the previous planning session `session_01StPzUiVKVKD13w1SEzRNpu`, whose
facts are folded in below where they still hold.

## Split of sessions, decided by the owner on 2026-10-18

- Main session (this one): the one integration actor. It implements approved records,
  drives pull requests to green, merges when the owner says so, keeps this checkpoint, and
  distributes bounded jobs to sub-agents. It is the only writer of this file.
- Planning session (the successor reading this): grills the owner, drafts decision records
  and task records for approval, prioritizes, reviews pull requests advisory-only. It does
  not implement, merge, or edit this file; it reports through comments on the records and
  through chat with the owner.
- Nobody else claims a task; GitHub labels are not locks. A sub-agent never owns anything.

## Repository state

- Repository: https://github.com/alhanaei/Conductor; `main` at `7ff3b7f` (PR #22 merged).
- Merged today, in order: PR #17 (#14, shared `backlog-task` wrapper), PR #23 (#15, three
  Claude Code wrapper copies), PR #24 (#16, package check fails on a missing or stale kit
  wrapper copy; allowlist trimmed to the Codex kit plus the Claude `backlog-task` copy),
  PR #4 (#8, lifecycle workflow, phase plan template, `gate-review`), PR #27 (#26, Merge
  danger section in the PR templates), PR #28 (#25, `grilling` technique and `to-tickets`
  workflow with wrappers and Claude copies), then on the owner's word PR #34 (#33, the
  linked-task check accepts record-only pull requests with `Refs #n`), PR #20 (#18, Claude
  Code Projects in the kit) and PR #22 (#19, verified-background-mode sentence in the handoff
  workflow). CI green on `main` after each. PR #32 closed as superseded by this file.
- Open pull requests:

  | PR | Task | Head | State | Next |
  | --- | --- | --- | --- | --- |
  | #35 | refs #3, this checkpoint | see PR | record-only; `linked-task` runs under the #34 rule once the head carries it | owner merge |
  | #30 | refs #29, ADR 0001 invocation axis (Proposed) | `476604e` | `verify` green; `linked-task` passes on its next run now that #34 is on `main` and the head is refreshed | held on decision D1 below |

- Working trees: nothing unpushed on any branch of this session.

## Policy binding

- Pinned policy `.conductor/policy/084387daacd2bae8a307ab4671e3d4d95f135f56/shared/WORKFLOW.md`,
  SHA-256 `539902dd4198ebd101bb0b49a4211949ab031f5b2766497213d734e175133f6c`, recorded as
  `policy_commit` and `policy_sha256` in `.conductor/adoption.json` and in the managed section
  of `AGENTS.md` (`CLAUDE.md` imports it). Single re-pin of 2026-10-22/23 (#45, from 2a14788
  `adefbfa6…` via the interim release d447a4b `7be78c35…`, superseded when `main`'s sprint
  work #44, #46 and #47 was merged in): roles, owner gates, task boundaries, `status:ready`
  check, one kit, sub-issue rule. The snapshot holds the `shared/` tree only;
  `.conductor/backups/` is local and ignored.
  Migration record: the comment on #45. Checkpoint pointer rule: `shared/workflows/handoff.md`.

## Owner decisions pending, in order; the planning session's first job is to ready these

- D1 Shape of Conductor. The owner wants a lightweight library around one main assistant.
  Today `main` carries eight assistant folders, two full kits (Codex, Claude Code), per-kit
  profiles and pins in the initializer, a folder-ownership rule and a wrapper-copy drift
  check. Options: one kit (Claude Code) with `shared/` kept vendor-neutral in wording;
  or keep multi-kit. Recommendation on record: one kit, delete rather than park the others,
  migrate `adoption.json` once. Affects #29, #31, the Codex requests below, and the kit
  copies added by PR #23 and PR #28.
- D2 Where the durable backlog lives. The owner finds per-task GitHub issues heavy and wants
  the main assistant to manage tasks. Options: GitHub issues as now; a repository backlog
  file written only by the main session (recommended; sessions die, files do not); the
  assistant's own task tools only (loses the queue with the session). Changes
  `shared/workflows/backlog.md`, the `to-tickets` output target, `pr-policy.yml`, the
  reconciliation workflow, and `PROJECT.md`'s task-source row.
- D3 ADR 0001 scope (PR #30). Accept the invocation axis for one kit (Claude Code
  `disable-model-invocation: true`) or for every kit. Follows D1.

Each decision becomes one `kind:decision` record, grilled with the owner by the planning
session, then an ADR under `docs/adr/` opened by the main session with `Refs #n` once #34
is on `main`.

## Open task records, by priority, and who moves them

| Record | Priority | State | Planning session | Main session |
| --- | --- | --- | --- | --- |
| #3 Define phase, orchestrator MVP | P1 | Backlog; #4 dependency cleared | Grill to Ready and G1 criteria after D1 and D2 are decided, since the MVP shape depends on both; then `to-tickets` the Define outputs | Implements the sub-tasks |
| #29 invocation axis rollout | P3 | Backlog; waits on D3 | Re-scope after D3 | Implements after acceptance |
| #31 retro step in handoff | P3 | Backlog; depends on #25 (merged) | Confirm scope after D1 (Codex allowlist line falls away under one kit) | Implements |

Requests on record for a Codex maintainer, if D1 keeps Codex: wrapper copies on #15,
`gate-review` on #3, `grilling` and `to-tickets` on #25. Under one kit these close as
not planned.

## Borrowing from mattpocock/skills (register entry S1, MIT, at 49dd158)

- Landed: `grilling`, `to-tickets` (PR #28), Merge danger section from `pr` (PR #27).
- Proposed, open: invocation axis (#29, ADR in PR #30), `retro` (#31).
- Rejected by the previous planning session, agreed by the main session: the triage state
  machine (conflicts with the backlog workflow) and the local scratch tracker.
- Candidates after D1 and D2, not yet proposed: `writing-for-agents` (Conductor has no
  guidance on writing instructions and skills, and is a library of them); `code-review` and
  `tdd` as the discipline behind `independent-review` and `coding-task`; `handoff` compared
  with `checkpoint-handoff`; the plugin packaging model itself, which fits a one-kit
  Conductor (a generated Claude Code plugin with the skills plus hooks enforcing the digest
  check, no-merge and PR-names-task rules).
- Conflict to resolve with D2: `to-tickets` files one sub-issue per slice; under a file
  backlog it writes slices there instead. The text already says "the project's task
  source".

## Verification at `main` 7ff3b7f

- `python3 tests/package_conductor_init.py`, cwd `.`: verified; 103 root digests.
- `PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s tests`, cwd `.`: OK (72 tests).
- `git diff --check`: clean everywhere.
- `sha256sum shared/WORKFLOW.md`: `adefbfa6…` everywhere.
- Cloud-clone note from the previous planning session, not reproduced here (this clone is
  full): the suite needs commit `9d77436` reachable; a shallow clone needs
  `git fetch --depth=200 origin main` first.

## Verified background mode (recorded per the sentence PR #22 adds)

Claude Code on the web, cloud session, verified 2026-10-17 to 2026-10-18 in this session:
scheduled self check-ins armed with `send_later` fired on time across hours of idleness;
GitHub events on subscribed pull requests woke the session; CI results arrived without
polling. Limits: the container is ephemeral and reclaimed after inactivity, so anything
not pushed is lost; a cloud session cannot see the owner's home folder (`~/.claude`), so
home-skill discovery checks run on the Mac only. A prompt alone still guarantees nothing;
the wakeups above came from armed triggers and subscriptions, not from instructions.

## Next executable steps for the planning session

1. Read `PROJECT.md`, this file, `shared/workflows/backlog.md`, `shared/techniques/grilling.md`
   and `shared/workflows/to-tickets.md` at the pinned policy.
2. Propose three `kind:decision` records for D1, D2, D3 (title and problem to the owner
   first; file only on approval). Grill the owner on D1 and D2 in one round each; write the
   answers to the records.
3. Hand the accepted decisions to the main session by comment on each record; the main
   session opens the ADRs (record-only pull requests with `Refs #n`) and the restructuring
   tasks.
4. Only then grill #3 to Ready and run `to-tickets` on its Define outputs.
5. Review PR #30 advisory-only; findings go on the pull request, never a push.

## Rules both sessions keep

- Every change starts from a labelled record; propose before filing; the pull request names
  it (`Closes #n`, or `Refs #n` for a record-only pull request; the check reads the
  workflow from the pull request's own head, so a branch older than #34 must merge `main`
  first).
- Highest open priority first; anything found mid-task is proposed on its record and left.
- Merge is the owner's gate; the main session merges only when the owner says so.
- `shared/` is canonical and generic first; Claude edits only `assistants/claude-code/` and
  the root shared files; generated copies and `MANIFEST.json` come from
  `tests/package_conductor_init.py --write`; other assistants' folders are requests on the
  record, never edits, until D1 says otherwise.
- Generated-file conflicts (`MANIFEST.json`, `SHA256SUMS`) are resolved by regeneration,
  never by hand; merge `main` in with a merge commit, no rebase on a pushed branch.
- Commits end with the session's Co-Authored-By and Claude-Session lines; pull request
  bodies end with the generated-with footer; GitHub comments end with the Claude Code
  attribution footer.

## Blockers and publication state

- No blockers. Nothing unpushed. No deployment, schedule, credential or cloud configuration
  changed. The main session holds one armed self check-in (trigger
  `trig_01LjDSbHbuUSahMpjFpso6SE`, about 16:46 UTC) and a subscription to PR #35; both end
  when it merges.
