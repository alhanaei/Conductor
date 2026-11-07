# ADR 0007: Review as a check-held gate for labelled records

- Status: Accepted (owner decisions of 2026-11-07, recorded on #88 from the project thread
  "Improve review step and status labels": "Accept" at 03:39 UTC, "File and r2" at 03:42 UTC,
  "Ready r2" at 03:43 UTC)
- Date: 2026-11-07
- Deciders: repository owner
- Task record: #88 (top-level record)
- Amends: ADR 0003 (the Reviewer role and the advisory review; the `linked-task` check gains a
  second condition for labelled records)
- Roles: decision grilled by the Planner (project coordinator); this record written by the
  Implementer (a project thread)

## Context

ADR 0003 made review advisory and ADR 0005 let approval mode `auto` squash-merge a pull
request as soon as `verify` and `linked-task` are green. In this repository both checks go
green in about two minutes, so every pull request since 2026-10-23 merged before anyone other
than its author had read it. The Review line of the pull request template was free text and
nothing read it.

The obvious fix, a required GitHub approval in branch protection, does not work here. Every
session, whatever its runtime, acts through the owner's own GitHub account, GitHub ignores an
approval by the pull request's author, and the Never list forbids approving a pull request as
a merge authorization. A bot or App identity would give the review its own account, but it is
a new credential to hold and rotate, and the owner has just deleted the one Conductor had.

The owner wants two things at once: a real second pair of eyes before the records that matter
land, and the `auto` mode kept as it is, with no click from the owner on a sub-issue.

## Decision

1. A record may carry the label `review:required` (its name is the repository variable
   `CONDUCTOR_REVIEW_REQUIRED_LABEL`, default `review:required`). The Planner applies it at
   filing to every P0, P1 and `kind:security` record; the owner may add or remove it on any
   record.
2. When the task a pull request closes carries that label, the `linked-task` check fails until
   the pull request body's "## Review" section contains a line of the form
   `Reviewer: <runtime or login>, reviewed SHA: <40-hex>` whose SHA equals the pull request
   head. The check runs on every `opened`, `edited`, `synchronize` and `reopened` event, so
   filling the line turns it green and a later push turns it red again until the new head is
   reviewed. Nothing else in the merge path changes: branch protection, the required checks,
   auto-merge and the owner's gates on top-level records stay as ADR 0005 left them.
3. The Reviewer runs on a different runtime than the one the Implementer's claim comment
   names: a Codex or Gemini review of a Claude pull request, a Claude Reviewer thread of a
   Codex one. The check does not read the claim comment, because comments are descriptive,
   not locks; the rule is enforced by inspection and written on the page.
4. Records without the label keep the advisory review of ADR 0003.

## Alternatives considered

- A required GitHub approval in branch protection. Rejected: all sessions act through the
  owner's account, self-approval is ignored, and the Never list forbids approving as a merge
  authorization; the gate would be either impossible or a rule broken on every pull request.
- A bot or GitHub App identity for the Reviewer. Rejected for now: a new credential to hold,
  and the project has just removed the one it had. Can be revisited if the label gate proves
  too weak.
- A review-completion check on every pull request. Rejected: it would hold every P2 and P3
  change for a review the owner does not want to wait for; the label keeps the cost where the
  risk is.
- Reading the claim comment to verify the reviewer's runtime. Rejected: comments are
  descriptive, and a check that parses prose is brittle; the page states the rule and the
  Planner inspects.

## Consequences

- Changed: `.github/workflows/pr-policy.yml` (the new variable, the Review-line condition),
  `AGENTS.md` (the Reviewer sentence in Roles; the label sentence in Task finish),
  `.github/pull_request_template.md` (the Review line in the required format), `README.md`
  (the variable in the adoption steps), ADR 0003 (an "Amended by" line).
- New: the label `review:required` in this repository; projects created from the template
  create it with the other labels.
- Limit: the gate proves that a review of the exact head was recorded, not that it was good.
  A reviewer who copies the SHA without reading the diff turns the check green; the advisory
  findings remain the quality signal.
- Unchanged: `verify`, branch protection, the required-check list, the three owner gates and
  the two approval modes.

## Rollback

Remove the `review_problem` condition from `pr-policy.yml` and the two sentences from
`AGENTS.md`, restore the template's Review line, and delete or ignore the label. Records
already labelled keep it harmlessly.

## Source

#88 and its Gate File and Gate Ready comments; Backlog #66 lines R1 to R3; the owner's
acceptance of the review-step recommendations on 2026-11-07 in the project thread "Improve
review step and status labels".
