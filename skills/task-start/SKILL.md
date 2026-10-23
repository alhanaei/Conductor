---
name: task-start
description: Claim one readied task at the start of a session - refuse without status:ready, post the claim comment on the record, branch from the integration branch, record the baseline and keep the task's allowed paths in view
---

# Task start

Conductor speaks twice per task. This is the first time: `task-start #n` turns a readied task
record into a claimed, bounded piece of work. Between this and `task-finish` the assistant's
own practice runs. This skill grants no authority; the task record and the platform do.

1. Read the project's `AGENTS.md`, then the record #n with its comments, through your own
   GitHub access. Do not describe the task from memory.
2. Refuse when #n is not open or lacks the `status:ready` label: say which Ready fact is
   missing and stop. The owner (or, for a sub-issue in approval mode `auto`, the Planner)
   applies the label; never add it yourself. Refuse when the record carries an `agent:*`
   label naming another assistant, or an unreleased claim comment by someone else.
3. Post the claim comment on #n before changing anything:

   ```
   **Claim.** Task #n claimed by <assistant> as <Owner|Planner|Implementer|Reviewer> in
   <runtime, for example Claude Code project thread> at <UTC time>. Reference: <session,
   thread or task URL>. Branch `<branch>` from `<integration branch>` at `<base SHA>`.
   Allowed paths: <copied from the record>. The milestone is posted here by task-finish.
   ```

   Labels and comments are descriptive, not locks; an ambiguous claim pauses conflicting
   writes until the owner answers.
4. Branch from the project's integration branch (`main` unless `AGENTS.md` names another) as
   `<assistant>/<slug>-<date>`, or keep the branch the runtime assigned. Record the baseline
   in your first message: base SHA, dirty state, known failures.
5. Keep three lines in view for the rest of the task: the task and its allowed paths; the
   owner gates (never merge, push to the integration branch, rewrite history or apply
   `status:ready`); how to finish (`task-finish`). Work only inside the allowed paths;
   anything found outside them is proposed on its record and left for `task-finish`.

Stop and ask the owner when the record has no allowed paths, when the integration branch
cannot be fetched, or when the task would need a service, secret or connector you cannot
reach.
