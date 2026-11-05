# Backlog reconciliation

The backlog workflow prints a read-only report of open tasks: the highest open priority, tasks missing a priority or category, tasks untouched past the stale window, owner-blocked tasks, tracking records, and assignees who have been silent. It does not create issues or change labels. It comments on an issue only when `CONDUCTOR_BACKLOG_REVIEW_ISSUE` is set.

## Sub-features

- `backlog-report` prints the reconciliation sections in the job log.
- `backlog-no-write` leaves labels and issues alone. A comment happens only when the review-issue variable is set.

## How to get to it (user POV)

- The `Backlog reconciliation` workflow runs on the Monday 06:00 UTC schedule.
- A person can run it with `workflow_dispatch`. Verification does not.

## Driving it with conductor-verify

Preconditions:

- `conductor-verify doctor` reports `doctor: ok`.
- `gh auth status` can read Actions logs for this repository.
- At least one successful `schedule` run of `Backlog reconciliation` exists. If none does, stop and report that precondition. Do not dispatch a run.

- **Select a run.** From the repository root, run `gh run list --workflow "Backlog reconciliation" --limit 5 --json databaseId,event,conclusion,createdAt,url` and save it to `$EVIDENCE/backlog-runs.json`. Choose the newest entry whose `event` is `schedule` and whose `conclusion` is `success`.
- **Report text.** Run `gh run view <id> --log` and save the rendered report lines to `$EVIDENCE/backlog-report.txt`. The log contains `# Backlog reconciliation 20`, a line matching `Open tasks: [0-9]+`, `## Highest open priority, oldest first`, `## Without a priority or category (not ready)`, `## Owner-blocked: confirm the blocker still holds`, `## Tracking records: confirm open children remain`, and a line ending with `Proposals arising from this report follow the backlog workflow: propose, wait for approval, then file.` Use `file.$` so the match is the rendered line.
- **Proof.** `backlog-runs.json` names the schedule run and `backlog-report.txt` has those rendered lines. Record the run URL.

## Gotchas

- Do not `workflow_dispatch` this workflow for verification. When `CONDUCTOR_BACKLOG_REVIEW_ISSUE` is set, the job comments on that issue.
- The log echoes the Python source. Source contains `# Backlog reconciliation {now.date()}` and `section("Highest open priority, oldest first"`. Require `# Backlog reconciliation 20` and the `## ` headings, which the source does not contain.
- `Open tasks:` appears inside the source string. Require `Open tasks: [0-9]+`.
- The proposals sentence also appears in full inside `lines.append("...")`. Require that sentence at the end of a log line (`file.$`). The source line ends with `file.")`.
- actionlint accepting `backlog-review.yml` is the `verify-workflows` result. It is not this feature's pass.
- A run that comments is still a report. Verification does not delete that comment and does not post another.
