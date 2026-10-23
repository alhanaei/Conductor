# Session roles

A session holds exactly one role at a time and declares it when it claims work: in the
claim comment on the task record and in the project checkpoint. Roles describe what a
session may do inside the [common workflow](../WORKFLOW.md); they grant no authority of
their own, and a role never bypasses an owner gate or the project's platform controls.

| Role | Holds | Does | Never |
| --- | --- | --- | --- |
| Owner (human) | the three owner gates: File, Ready, Merge | sets priorities, reorders the queue, approves records, readies them, merges | — |
| Planner | the queue between the gates | proposes records with title and problem, grills them to Ready, splits them with the [to-tickets workflow](to-tickets.md), reviews pull requests advisory-only, keeps the Backlog issue | implements, pushes, files a record without File approval, applies `status:ready` without Ready approval |
| Implementer | one Ready record at a time | claims it by comment, works on a branch, drives the pull request to green, records verification against the exact head, stops at the Merge gate | merges, widens scope, starts a record that is not Ready |
| Reviewer (optional) | an independent read of one pull request against its record | reports findings as advisory review comments | approves as a merge authorization, pushes to the branch |

## Owner gates

The three decisions that stay human, named "owner gates" everywhere in this library to
keep them apart from the lifecycle workflow's phase gates (G0 to G5):

| Owner gate | Transition | Proposed by | Record of approval |
| --- | --- | --- | --- |
| File | an idea becomes a task record | Planner, or anyone | the record's first comment names the approval, its date and where it was given |
| Ready | Backlog becomes Ready | Planner, with the Ready facts written | the `status:ready` label, applied with a comment naming the approving message |
| Merge | a pull request lands | Implementer | the merge itself |

Everything between the gates is the assistants' work. When the owner confirms a
to-tickets granularity round, that confirmation is the Ready approval for every slice in
it; the slices are labelled together with one comment naming the round. The pull-request
check reads the label: nothing merges for a record the owner never readied, whoever
opened the pull request.

## Claims and delegation

- A claim is a comment on the record with the role, the session reference, the start
  time and the branch or workspace. Labels, assignees and notes are descriptive, not
  locks; an ambiguous claim pauses conflicting writes under the common workflow.
- An Implementer may hand a bounded sub-task to a sub-agent or another assistant and
  remains its owner; the result returns through the Implementer and is verified before it
  is reported. Delegation never transfers ownership or a role.
- Two Implementers on one project fall under the common workflow's parallel-work
  exception: distinct Ready records, separate branches, one integrator.
- A session that needs to change role ends its claim first: it checkpoints, releases the
  record by comment, and claims again in the new role.
