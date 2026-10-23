# ADR 0003: Three human gates, session roles and a single backlog queue

- Status: Accepted (owner decision of 2026-10-18, recorded on #37)
- Amended by: ADR 0004 (2026-10-22): Claude Code Projects mode resumed; the comment
  amendments of #37 (rounds 3 to 5, roles, identity, Projects round, merge gate) recorded.
- Date: 2026-10-18
- Deciders: repository owner
- Task record: #37
- Roles: decision grilled by the Planner session; this record written by the Implementer session

## Context

Every change in Conductor has needed its own approved, labelled GitHub issue: sixteen
issues for nineteen pull requests at the time of the decision. The owner finds that heavy
for a one-person project with assistants doing the work, and wants the assistants to
manage the queue while three decisions stay human: what gets filed, what is ready to
build, and what merges. The owner also runs sessions in two roles today, planning and
implementing, and wants that split written down rather than improvised each session.

The canonical workflow already names one accountable owner per task, says delegation
never transfers ownership, and runs records through Backlog, Ready, In progress and Done.
It does not say who may move a record between those states, and no priority label has a
written definition.

## Decision

### Three human gates

| Gate | Transition | Proposed by | Approved by | Record of approval |
| --- | --- | --- | --- | --- |
| File | an idea becomes a task record | Planner, or anyone | Owner | the record's first comment names the approval and its date |
| Ready | Backlog becomes Ready | Planner, after grilling, with the Ready facts written | Owner, or a Reviewer's recommendation plus the Owner | `status:ready` label applied by the main session with the approving comment |
| Merge | a pull request lands | Implementer | Owner | the merge itself |

Everything between the gates is the assistants' work: ordering the queue, grilling,
splitting, implementing, reviewing. When the owner confirms a `to-tickets` granularity
round, that confirmation is the Ready approval for every slice in it; the slices are
labelled together with one comment naming the round.

### Roles

A session holds one role at a time and declares it when it claims work, in the claim
comment and in the project checkpoint.

- Owner (human): holds the three gates, sets priorities, reorders the queue.
- Planner: proposes records, grills them to Ready, splits them with `to-tickets`, reviews
  pull requests advisory-only. Never implements, never pushes.
- Implementer: takes Ready records in priority order, one at a time; claims each by
  comment with its session reference and start time; works on branches; drives pull
  requests to green; stops at the merge gate. May hand a bounded sub-task to a sub-agent
  or another assistant and remains its owner; the result returns through the Implementer.
- Reviewer (optional, later): independent review of a pull request against its record;
  advisory, as the review workflow already says.

Two Implementers on one project fall under the existing parallel-work exception: distinct
Ready records, separate branches, one integrator.

### Mechanical enforcement

The `linked-task` pull-request check also requires `status:ready` on the task the pull
request closes. Filing and merging stay human by rule; readiness becomes human by rule and
by check, so nothing merges for a record the owner never readied, whoever opened it.

### The queue

One pinned "Backlog" issue whose body is the queue, written only by the main session.
Ideas sit there as one-liners with a proposed priority. Promoting a line to its own issue
is Gate File. Records that have passed Gate File are ordinary issues, as today.

### Priority scale

- P0: a live risk or blocker; drop other work and say so.
- P1: next up, or blocks a P1.
- P2: planned; worked after the P1s.
- P3: only when already working in that code.

Ties go to the oldest record.

### Library default

These rules become the default in `shared/` (the backlog workflow, `to-tickets`, the issue
form, the pull-request check, the Projects brief template) and the wording on record
approval and ownership in `shared/WORKFLOW.md`. That change lands in one policy release
together with ADR 0002's restructuring, so adopters migrate once.

## Alternatives considered

- Drop owner approval of new records and let the main session file, order and close tasks
  with the owner vetoing afterwards. Rejected by the owner: filing, readiness and merge
  stay human decisions.
- A `BACKLOG.md` file in the repository as the queue, written only by the main session.
  Durable in Git history, but the copy on `main` lags until each pull request merges and
  the checks and reconciliation would need rewriting. Rejected in favour of the pinned
  issue, which is always current and leaves the checks as they are.
- The assistant's own task list as the only queue. Lost with the session. Rejected.
- GitHub Projects as the board. Fits the owner's habits, but the sessions' GitHub tools
  cannot read or write Projects. Not chosen for now.

## Consequences

- New: `shared/workflows/roles.md`; the `status:ready` requirement in
  `shared/templates/github/workflows/pr-policy.yml` and this repository's copy; a roles
  line in `assistants/claude-code/PROJECT-INSTRUCTIONS.template.md`; the pinned Backlog
  issue for this repository.
- Changed: `shared/workflows/backlog.md` (gates, queue issue, priority definitions),
  `shared/workflows/to-tickets.md` (batch Ready approval), the issue form, `PROJECT.md`'s
  task-source row, and the approval and ownership wording in `shared/WORKFLOW.md`, which
  changes the pinned digest and is why this lands in the single re-pin with ADR 0002.
- Unchanged: one accountable owner per task; delegation never transfers ownership; merge
  is the owner's gate; findings found mid-task are proposed and left.
- ADR 0001: `backlog-task` and `to-tickets` stay user-invoked, since both end at a human
  gate; `grilling` stays model-invoked.

## Rollback

Remove the `status:ready` requirement from the check, delete `roles.md`, and restore the
previous backlog wording in the next policy release. Records already labelled keep the
label harmlessly. The pinned Backlog issue can be closed; its lines are proposals, not
records.

## Source

#37 and its Gate File and Gate Ready comments; the owner's answers to the Planner's
grilling round 1 (Q2 to Q5) and the roles model agreed with the Implementer on
2026-10-18; `shared/WORKFLOW.md` at the 2a14788 pin and `shared/workflows/backlog.md` at
`main` ec6d1b0.
