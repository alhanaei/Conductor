# Linked task

`linked-task` rejects a pull request whose body does not close a Ready task, and in approval mode `auto` it also rejects a pull request whose base is not `main`. A Ready task has exactly one priority (`P0`, `P1`, `P2`, or `P3`, or `blocked:owner` instead of a priority), exactly one `kind:` label, and `status:ready`. A sub-issue's parent must be a workable open record; in `auto` the parent needs `status:ready` too.

## Sub-features

- `linked-task-base` accepts base `main` in approval mode `auto`.
- `linked-task-ready` accepts a body that closes one task with one priority, one `kind:` label, and `status:ready`.
- `linked-task-parent` checks an open parent, and in `auto` requires the parent's `status:ready`.
- `linked-task-record-only` allows `Refs #n` only when every changed file is under a record path.

## How to get to it (user POV)

- Open, edit, synchronize, or reopen a pull request. The `PR policy` workflow runs the `linked-task` job.
- The pull request body closes the task (`Closes #n`, or another closing keyword GitHub understands). A pull request that only changes record paths may say `Refs #n` instead.

## Driving it with conductor-verify

Preconditions:

- `conductor-verify doctor` reports `doctor: ok` for this run.
- `CONDUCTOR_VERIFY_PR` is the number of a pull request that already exists. Do not open a pull request, file a task, or add `status:ready` as part of verification.
- `gh auth status` succeeds for a principal that can read this repository's Actions logs.
- The `linked-task` row on that pull request has already finished.

- **Check row.** From the repository root, run `gh pr checks "$CONDUCTOR_VERIFY_PR"` and save it to `$EVIDENCE/linked-task.checks.txt`. The `linked-task` row's conclusion is `pass`. Copy the run id from that row's URL (`/actions/runs/<id>/`).
- **Base and Ready task.** Run `gh run view <id> --log` and save the matching lines to `$EVIDENCE/linked-task.summary.txt`. The log contains the rendered line `Approval mode auto: base 'main' accepted.` and a rendered line matching `Task #[0-9]+ is ready: labels `. The labels on that line include `status:ready`, one priority (or `blocked:owner` when that is the marker in use), and one `kind:` label.
- **Parent, when the task has one.** The same log contains `Parent #[0-9]+ of task #[0-9]+ is open: labels ` when the closed task has a parent. No such line means the task had no parent. A line `is not a workable record` is a failure.
- **Record-only, when the body uses Refs.** The log contains `Record-only pull request (` and `accepting the referenced task(s).` That path is not available to a change outside the record paths.
- **Proof.** `linked-task.checks.txt` shows `pass` and `linked-task.summary.txt` has the rendered Ready line. A checks table without the rendered line is not a pass.

## Gotchas

- The job log prints the Python source before the result. The source contains `Task #{number} is ready` and `base '{base_ref}' accepted`. Those are not results. Require `Task #[0-9]+ is ready: labels ` and `Approval mode auto: base 'main' accepted.`
- This repository's approval mode is `auto` and the integration branch is `main`. A log that does not contain the auto line did not see `CONDUCTOR_APPROVAL_MODE=auto`.
- Record paths default to `docs/adr/` and `.conductor/HANDOFF.md`. There is no `.conductor/HANDOFF.md` in the tree; the prefix is the variable default. A change under `skills/` cannot use `Refs #n`.
- Default labels, when the repository variables are unset, are `P0,P1,P2,P3`, `blocked:owner`, prefix `kind:`, tracking label `kind:tracking`, and ready label `status:ready`.
- If `CONDUCTOR_VERIFY_PR` is unset or the check has not finished, the journey fails. Say which precondition is missing. Do not mark the feature passed because `actionlint` accepted `pr-policy.yml`.
