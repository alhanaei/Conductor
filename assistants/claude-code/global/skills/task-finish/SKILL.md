---
name: task-finish
description: Close a claimed task - run the verification contract on the exact head into evidence with its SHA, draft or open the pull request with Closes #n and the ledger, update the checkpoint pointer, post the milestone, and record proposals; --stopped records a blocker instead
---

# Task finish

The second and last time Conductor speaks in a task. `task-finish` turns the claimed branch
into a reviewable pull request with evidence, or records an honest stop. A finish without
evidence that matches the exact head is a stopped finish, never a done one.

Helper: `scripts/task_boundary.py` next to this file, Python 3 standard library, writes only
inside the checkout's Git metadata (`<git-dir>/conductor-local/`).

1. Commit everything that belongs to the task. The helper stops (exit 4) on uncommitted
   changes, because evidence must name the SHA it ran on.
2. Copy each applicable row of the project's verification contract (in `PROJECT.md` or
   `AGENTS.md`) into one `--check NAME=COMMAND` each. Do not infer commands from another
   repository; a row marked not applicable is left out. Run, from the repository root:

   ```
   python3 <skill-dir>/scripts/task_boundary.py finish \
     --check "Package integrity=python3 tests/package_conductor_init.py" \
     --check "Tests=PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s tests" \
     --summary "<what changed and why>" [--proposal "<finding left for the owner>"]... \
     [--title "<pull request title>"] [--open] [--post]
   ```

   The helper runs every check, writes `conductor-local/verification.json` with the head
   SHA, branch, time and each result, and then:
   - drafts `conductor-local/pr-body.md` in the project's pull request template shape with
     `Closes #n`, the verification ledger with tested SHAs, and a "Found and left" block
     holding every `--proposal`;
   - writes the checkpoint pointer `conductor-local/checkpoint.md` (task, branch, head,
     evidence, pull request, blocker, next action);
   - drafts the milestone comment at `conductor-local/milestone-comment.md`.
   With `--open` it pushes the branch and opens the pull request through `gh`; with
   `--post` it posts the milestone. Without them, or when `gh` is unavailable, open the pull
   request and post the comment through your own GitHub access from the drafted files,
   keeping `Closes #n` and the ledger intact. The pull request's base is the claim's base;
   the owner merges.
3. If a check fails, the helper records the failure as a blocker, writes no pull request body
   and exits 4. Fix, commit and run it again. Never skip, disable or quarantine a check to
   get green.
4. Stopping instead: `task_boundary.py finish --stopped --blocker "<what blocks>" --next
   "<next executable step>" [--check ...]` records the blocker and next action in the
   checkpoint and the milestone comment, with whatever evidence was gathered, and opens no
   pull request. Use it when context, quota, access or the owner's decision runs out.
5. Proposals are the retro step: every finding outside the task's scope goes in as a
   `--proposal` line and lands in the pull request's "Found and left" block and the
   milestone comment, for the owner to file. Nothing found mid-task is done here.
6. `task_boundary.py verify-evidence` exits 0 only when the evidence SHA equals HEAD and every
   check passed; use it before reporting completion, and let hooks or CI call it later.

Stop and ask the owner when `task-finish` would open a pull request for a task other than
the claimed one, or when the helper would need to write outside `conductor-local/`.
