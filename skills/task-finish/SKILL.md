---
name: task-finish
description: Close a claimed task - run the verification contract on the exact head, open the pull request with Closes #n and the ledger, arm squash auto-merge in approval mode auto, post the milestone on the record, list what was found and left, and hand off on the record before the session ends; --stopped records a blocker instead
---

# Task finish

The second and last time Conductor speaks in a task. `task-finish` turns the claimed branch
into a reviewable pull request with evidence, or records an honest stop. A finish without
evidence that matches the exact head is a stopped finish, never a done one.

1. Commit everything that belongs to the task. Evidence must name the SHA it ran on, so
   nothing may be uncommitted.
2. Run every applicable row of the verification contract in the project's `AGENTS.md` from
   its stated cwd on the exact head. Do not infer commands from another repository or from
   memory. Record for each row: command, cwd, passed or failed, output lines that matter,
   tested SHA. If a row fails, fix, commit and run again; never skip, disable or quarantine
   a check to get green.
3. Push the branch and open the pull request against the integration branch from the
   repository's template: `Closes #n`; what changed and why; the verification ledger with
   tested SHAs; merge danger (two-way or one-way door, blast radius); review line; a "Found
   and left" block with every finding outside the task's scope, one line each with a
   suggested priority. Nothing found mid-task is done here.
4. When the project's approval mode is `auto` and the task is a sub-issue of a readied
   parent, enable GitHub auto-merge with squash on the pull request; GitHub merges it when
   `verify` and `linked-task` are green. Never merge by hand; in `manual` the owner merges.
5. Post the milestone comment on #n:

   ```
   **Finished.** Task #n by <assistant> (<role>, <runtime>, <reference>) on branch
   `<branch>` at `<head SHA>`, <UTC time>. Checks: <row: passed|failed>; ... Pull request:
   #<pr> (<auto-merge armed | owner merges>). Found and left: <one line each>.
   ```

6. Stopping instead (`task-finish --stopped`): post on #n the blocker, the next executable
   step, the head SHA and whatever evidence was gathered, and open no pull request. Use it
   when context, quota, access or the owner's decision runs out.
7. Drive the pull request to green: on a red check or a review finding, fix on the same
   branch and push; the ledger is updated to the new head. A pull request that waits on the
   owner says so in one comment.
8. Hand off on the record as the last step of the session, in every role and on the stopped
   path too. Gather every fact from GitHub and `git` (the record, its pull requests, `git
   log`, `git status`), never from memory or chat; write `unknown` for what is not known.
   Post one comment on #n and release the claim with it:

   ```
   **Handoff.** <role> on <runtime>, <reference>, <UTC time>. Branch `<branch>` at
   `<head SHA>`. Merged: <pull request and merge SHA | none>. Pushed, unmerged: <pull
   request or branch and head | none>. Decisions: <one line each | none>. Blockers: <open
   blockers | none>. Found and left: <one line each | none>. Next step: <one sentence a
   fresh session can execute>. Claim released.
   ```

9. When #n is a tracking or top-level parent, the handoff is its closing report and lists
   every child as `#<child>: pull request #<pr>, merge SHA <sha>`, with the verification
   evidence, decisions, found and left, and the next record to open. Refuse to post it, and
   name the child, while any child is open or a child's pull request is unmerged. In
   approval mode `auto` close the parent with the report; in `manual` leave it to the owner.

Stop and ask the owner when the pull request would close a task other than the claimed one,
or when a verification row needs a tool the session cannot install.
