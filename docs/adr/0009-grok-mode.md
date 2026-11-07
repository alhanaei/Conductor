# ADR 0009: `grok` mode: Grok as the readying and reviewing identity

- Status: Accepted (owner decision of 2026-11-07, "Accept the recommendation. And ready 108"
  at 21:32 UTC in the project thread "Give assistants their own GitHub app identity",
  recorded in the Gate Ready comment on #108; the record itself filed on the owner's "Ok
  file it" at 17:54 UTC)
- Date: 2026-11-07
- Deciders: repository owner
- Task record: #108 (sub-issue of #97, which closed before it; kept as filed on the owner's
  word)
- Amends: ADR 0008 (the identity its §5 leaves open: who applies `status:ready` other than
  the owner's login, and so what its actor test can see)
- Roles: decision grilled by the Planner (project coordinator); this record written by the
  Implementer (a project thread)

## Context

ADR 0008 §5 names its own limit: the `linked-task` actor test is a no-op while every
assistant acts through the owner's GitHub login, because every `labeled` event then names
the owner. It left the identity to a separate record, Backlog #66 line T1.

The identity spike ran on 2026-11-07. The owner installed the GitHub App `grok-conductor`
(App ID 5660598) on the repository, and a comment on #108 at 21:07 UTC was posted with a
short-lived installation token as `grok-conductor[bot]` (user id 353875953, author
association `NONE`). That is a GitHub identity distinct from the owner's login, so the actor
test of ADR 0008 §3 can see it. The same day showed the other path does not work: the `P2`
and `kind:decision` labels on #108 were applied by Grok through the `grok-by-xai` connector
and GitHub recorded them as the owner (`performed_via_github_app`, actor `alhanaei`), which
the actor test reads as an owner Ready. A Claude App identity is not planned: a Claude cloud
session cannot mint or carry an App token (the session proxy refuses the `/app/*` paths and
overwrites the `Authorization` header, re-tested 2026-11-07), so a Claude identity could
only run inside GitHub Actions and is filed only if Claude must ready records.

ADR 0005 chose two approval modes and rejected a third; `pr-policy.yml` accepts only `manual`
and `auto` for `CONDUCTOR_APPROVAL_MODE`. This record changes neither.

## Decision

1. `grok` mode is approval mode `auto` run with Grok as the Planner and Reviewer runtime. It
   is a name for that arrangement, not a third value of `CONDUCTOR_APPROVAL_MODE`, which
   stays `auto`; the thresholds of ADR 0008 and every owner gate of ADR 0005 apply unchanged.
   The assistant labels gain `agent:grok`. Grok holds the Planner and Reviewer roles only; it
   takes no Implementer role, so it never claims a record for a branch or pushes.
2. Grok readies and reviews only with the `grok-conductor` installation token, so that every
   `labeled` and review event it causes names `grok-conductor[bot]`, never through the
   `grok-by-xai` connector, which GitHub records as the owner. A record whose `status:ready`
   `labeled` event names the owner's login while Grok readied it is the stop condition of
   #108 met: Grok stops and reports instead of readying.
3. Admission rules. Grok applies `status:ready` to a record only when every one of these
   holds: the record was filed by a bot identity, not by the owner; its priority is within
   `CONDUCTOR_ASSISTANT_PRIORITY_CAP`; its category is not in `CONDUCTOR_OWNER_CATEGORIES`;
   its category is not `kind:decision`; every Ready fact of the issue form has an answer; its
   allowed paths lie inside one repository. Every Ready comment Grok posts names the
   admission rule it met, with the approving message, as the Owner gates require.
4. The loop. Every four hours Grok triages the bot-filed records that are new since its last
   pass (readying those that meet §3, leaving a comment naming the missing fact on the
   rest), reviews the open pull requests whose checks are green as the advisory Reviewer
   of ADR 0007 (a Grok review of a Claude or Codex pull request satisfies the different-
   runtime rule), and posts one summary naming what it readied, what it reviewed and what
   waits on the owner. The loop is read-only except for labels and review comments: no
   pushes, no merges, no edits to records it did not file, no settings.
5. Kill switch. Setting `CONDUCTOR_APPROVAL_MODE` to `manual` ends `grok` mode: in `manual`
   every gate is the owner's, so a Grok Ready authorizes nothing and `linked-task` refuses the
   pull request. Uninstalling or suspending the `grok-conductor` App has the same effect on
   the identity.
6. Owner-only actions are unchanged: promotion merges into the default branch, branch
   protection, required checks and repository variables, every P0 and P1 record, every
   `kind:security` record and every top-level record are the owner's to ready or act on.
   `linked-task` needs no change: a `grok-conductor[bot]` Ready on a record above the cap or
   in an owner-only category fails the actor test of ADR 0008 §3, and a record within the cap
   never reads the timeline.
7. App permissions and key location are `unknown` from a session (the installation cannot be
   read through the proxy). The target the owner accepted: Issues and Pull requests write,
   Contents read, Metadata read, no Administration; the private key held only in Grok's
   environment, never in this repository.

## Alternatives considered

- A third approval mode, `grok`, as a value of `CONDUCTOR_APPROVAL_MODE`. Rejected: ADR 0005
  rejected a third mode and `pr-policy.yml` would have to change, which is a non-goal of
  #108; `auto` with a named Planner runtime gives the same behaviour with no new setting.
- Grok acting through the `grok-by-xai` connector. Rejected: GitHub records it as the owner,
  which makes the actor test a no-op and the owner's Ready indistinguishable from a bot's.
- A Claude App identity alongside Grok's. Deferred: unreachable from a cloud session; a
  Backlog line only if Claude must ready records.
- Letting Grok ready `kind:decision` records within the cap. Rejected: a decision record
  changes the rules themselves and stays with the owner.
- Letting Grok implement. Rejected: one identity that files, readies and implements its own
  records would collapse the gates; the Implementer stays a separate runtime.

## Consequences

- New: this record; `agent:grok` as an assistant label; the "Amended by: ADR 0009" line under
  the Status of ADR 0008.
- Changed: one `AGENTS.md` bullet (the assistant labels, with the installation-token rule).
- Owner steps: create the `agent:grok` label; keep the App's permissions at the target in §7
  and the private key outside the repository; the loop, its schedule and its summary channel
  live outside this repository and are not created by this record.
- Limit: the actor test can see `grok-conductor[bot]` only on records above the cap or in
  an owner-only category; within the cap the page rule in §3 is the whole of the enforcement.
- Unchanged: `linked-task` code and tests, the two modes, the merge on green, the
  `review:required` gate, branch protection, the three owner gates on top-level records.

## Rollback

Set `CONDUCTOR_APPROVAL_MODE` to `manual` (the kill switch of §5), or uninstall the App;
remove `agent:grok` and the installation-token sentence from `AGENTS.md`, delete this record
and remove the "Amended by" line from ADR 0008.

## Source

#108, its Gate Ready comment and the `grok-conductor[bot]` comment of 2026-11-07 21:07 UTC;
the owner's "Accept the recommendation. And ready 108" (2026-11-07 21:32 UTC) in the project
thread "Give assistants their own GitHub app identity"; ADR 0008 §5; Backlog #66 line T1.
