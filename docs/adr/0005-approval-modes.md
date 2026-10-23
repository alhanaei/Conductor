# ADR 0005: Approval modes per project

- Status: Accepted (owner decisions of 2026-10-23, recorded on #58 from the project thread
  "Approval modes per project")
- Date: 2026-10-23
- Deciders: repository owner
- Task record: #59 (sub-task A of #58)
- Amends: ADR 0003 (the three owner gates become the `manual` default; a project may delegate
  everything below its top-level records)
- Roles: decision grilled by the Planner (project coordinator); this record written by the
  Implementer (a project thread)

## Context

ADR 0003 made File, Ready and Merge human gates and ADR 0004 moved their enforcement into
GitHub: the `linked-task` check requires `status:ready` on the task a pull request closes,
branch protection requires the checks and forbids bypass, and the owner's merge proves the
owner. Since 2026-10-23 (#54, PR #55) related work is filed as a sub-issue of the open record
it belongs to, so a sprint or a plan is a tracking parent whose records are its children.

In practice every step still waits for the owner: each sub-issue is proposed and filed only
on approval, each is readied by hand, each pull request is merged by hand, and the Projects
adapter tells threads to pause before any push, deploy or close. For a one-person project
with assistants doing the work that is the heaviest part of the day. On 2026-10-23 the owner
asked for "an Auto Approve mode while using issues and sub-issues", chosen per project at
init, and after the staging question settled the boundary in one sentence: "let the top
level to owner but rest do anything" (14:38 UTC).

Two facts constrain the design. Project threads and Codex cloud tasks have no hooks, so the
only mechanical enforcement for them is GitHub's (ADR 0004 §6). And `shared/WORKFLOW.md` is
pinned by digest in every adopter; changing it means a policy release and a migration, and
PR #56 had just completed one.

## Decision

### 1. The owner holds the top level; the mode decides what the children inherit

A top-level record (a new parent, a sprint, a standalone task) is filed and readied by the
owner in every mode, and so are priorities, queue order, promotion of the integration branch
into the default branch, and the repository settings that enforce the gates (branch
protection, required checks, repository variables). What a project's approval mode changes
is what happens below a record the owner has already filed and readied.

What inherits is the approval, not the facts. A sub-issue still carries its own priority,
category and Ready facts (backlog workflow steps 3 and 4) and `linked-task` still checks
them, together with the parent's state as PR #56 added.

### 2. Three modes

| Gate | `manual` (default) | `inherit` | `auto` |
| --- | --- | --- | --- |
| File a top-level record | owner | owner | owner |
| Ready a top-level record | owner (`status:ready`) | owner | owner |
| Priorities, queue order | owner | owner | owner |
| File a sub-issue of an open record | owner | Planner, with the Ready facts and the native parent link | same |
| Ready a sub-issue | owner | inherited: Planner applies `status:ready` when the parent carries it and the sub-issue's Ready facts are complete | same |
| Push, open the pull request | task-finish (Implementer; not a gate) | same | same |
| Merge a sub-issue's pull request | owner | owner | task-finish enables GitHub auto-merge into the integration branch; GitHub merges when the required checks are green |
| Deploy to staging | owner | owner | CI, on merge to the integration branch, as a job named in the verification contract |
| Edit CI configuration | per record's allowed paths | same | same, in a pull request |
| Close a task | by `Closes #n` on merge | same | same |
| Close a tracking parent | owner | owner | Planner, after the last child closes |
| Promote integration branch to default branch | owner | owner | owner, one pull request per release or sprint |
| Branch protection, required checks, repository variables | owner | owner | owner |

`manual` is today's rule and the library default. `inherit` removes the per-sub-issue File
and Ready clicks and keeps the merge click. `auto` delegates everything below the top level.

No mode lets an assistant merge by hand, approve a pull request as a merge authorization,
push to a protected branch without a pull request, edit branch protection or required
checks, or run a production deploy. "Auto" means GitHub merges on green and CI deploys on
merge, not a thread. Auto-merge uses a merge commit, matching this repository's history.

### 3. The integration branch

A project records an `integration_branch`, by default its default branch.

- Set to a staging branch (projects with a runtime and a deploy): task branches target it;
  in `auto` they auto-merge on green; CI deploys the branch on merge; the owner merges one
  staging-to-default pull request per release or sprint. The staging branch carries the same
  protection as the default branch (pull request required, bypass off, `verify` and
  `linked-task` required, auto-merge allowed), so "green" means the same thing on both.
- Left at the default branch (this repository: documentation, no runtime): auto-merge in
  `auto` lands on the default branch directly, since there is nothing to promote. A staging
  deploy runs only from an integration branch; a project that wants automatic deploys names
  one.

Pushing straight to the integration branch without a pull request is not offered in any
mode: it would skip `linked-task`, so work with no Ready record could land.

### 4. Where the mode is recorded

- `PROJECT.md` facts block: `- Approval mode: manual | inherit | auto`, and
  `- Integration branch: <name>` when it differs from the default branch.
- `.conductor/adoption.json`: `facts.approval_mode` and the adapter input
  `integration_branch`, filled by the initializer from `PROJECT.md`; defaults `manual` and
  the default branch. One mode per project, not per adapter: the gates must not differ by
  runtime.
- Repository variables `CONDUCTOR_APPROVAL_MODE` and `CONDUCTOR_INTEGRATION_BRANCH`, set by
  the owner from the owner checklist and read by `pr-policy.yml`. The adapter discovery check
  compares them with the recorded facts and reports a mismatch.
- `conductor_init.py init` asks for both; `generate --approval-mode` and
  `--integration-branch` override and write back.

### 5. Enforcement

- `linked-task` is the mechanical half of inheritance: in `inherit` and `auto` a
  `status:ready` sub-issue is accepted only if its parent carries `status:ready`, and a pull
  request must target the integration branch unless it is the owner's promotion. The check
  binds every runtime, including the two with no hooks.
- `auto` requires #48 criterion 1 on the integration and default branches: "Do not allow
  bypassing" on, approvals off, `verify` and `linked-task` required. Without it auto-merge
  would land a pull request the moment it is enabled, so the initializer refuses `auto`
  until `.conductor/adoption.json` records that discovery evidence.
- CI edits are the one delegated power that could weaken the gate. The two check workflows
  are required by name in branch protection, so a pull request that removes or renames them
  cannot itself go green, and protection stays owner-only.
- Threads act as the owner on GitHub (ADR 0004 §5), so the label and the auto-merge flag are
  applied under the owner's identity. The rule that keeps this honest is structural (parent
  Ready, target branch) and enforced by the check, not by who clicked.
- `shared/WORKFLOW.md` is unchanged. Its Authority paragraph already says "respect the actual
  task authorization" and "do not reconfirm an identical bounded action already authorized";
  a recorded approval mode is such a standing authorization. No re-pin, no adopter migration.

## Alternatives considered

- Two modes, `manual` and `auto`. Rejected for now: `inherit` costs one row in a table and is
  the safe first step for a project that has not yet verified its branch protection.
- Delegate the top level too (the Planner files and readies parents). Rejected by the owner:
  the parent is where the owner's attention lands; readying it once is the whole of the
  owner's work in `auto`.
- Let threads merge or push to the integration branch directly in `auto`. Rejected: it skips
  `linked-task` and `verify`, and ADR 0004 §5 put enforcement in GitHub precisely so that no
  runtime without hooks could bypass it. GitHub auto-merge gives the same outcome under the
  checks.
- Let threads run the staging deploy themselves. Rejected: a deploy from a session is neither
  reproducible nor logged in one place; CI on merge is both, and the thread's work ends at
  the pull request as before.
- Record the mode per adapter in `adoption.json`. Rejected: the gates must not differ by
  runtime, and a project fact in `PROJECT.md` is what the initializer already reads.
- Put the modes into `shared/WORKFLOW.md`. Rejected: it would force a policy release for a
  rule the Authority paragraph already accommodates, days after the re-pin of #45.
- Squash merges for auto-merge. Rejected: this repository's history uses merge commits and
  the ledger names tested SHAs that squashing would discard.

## Consequences

- New: this record; the "Amended by: ADR 0005" line under the Status of ADR 0003.
- Changed in this record's pull request: `shared/workflows/backlog.md` (steps 2, 4 and 9 name
  the mode), `shared/workflows/roles.md` (what the Planner and Implementer may do below the
  top level in `inherit` and `auto`), `MANIFEST.json` regenerated.
- Follows, on its own records: the initializer, adoption record, Projects template, owner
  checklist, `pr-policy.yml` and task-finish changes (#60); this repository running `inherit`
  and then `auto` on `main` (#61, after #48).
- Unchanged: `shared/WORKFLOW.md` and its pinned digest, the verification contract, the owner
  gates for top-level records, deployment authority outside CI, GitHub identity.

## Rollback

Delete this record, remove the "Amended by" line from ADR 0003, restore the previous wording
of the backlog and roles workflows, and regenerate `MANIFEST.json`. A project that recorded a
mode other than `manual` sets it back by editing `PROJECT.md` and the repository variable;
`linked-task` then behaves as before PR #56's parent check plus the label requirement.

## Source

#58 and its body (design version 2) and the owner-decision comment of 2026-10-23 14:38 UTC;
#59 and its Gate Ready comment (owner's "ready #59", 14:52 UTC); the owner's messages in the
project thread "Approval modes per project" on 2026-10-23 (14:23, 14:32, 14:36 to 14:39 and
14:52 UTC); the project note "Approval modes per project — design" (version 2); the
repository at `main` d79238d.
