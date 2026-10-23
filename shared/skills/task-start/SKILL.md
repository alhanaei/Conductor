---
name: task-start
description: Claim one readied task at the start of a session - refuse without status:ready, post the claim comment, branch from main, write the local claim with the allowed paths, and print the three always-on lines
---

# Task start

Conductor speaks twice per task. This is the first time: `task-start #n` turns a readied task
record into a claimed, bounded piece of work. Between this and `task-finish` the assistant's
own practice runs. This skill grants no authority; the task record and the platform do.

Helper: `scripts/task_boundary.py` next to this file, Python 3 standard library, writes only
inside the checkout's Git metadata (`<git-dir>/conductor-local/`).

1. Read the task record #n. The helper reads it through `--record FILE` (JSON with number,
   title, body, labels that you fetched with your own GitHub access), the `gh` CLI, or a
   GitHub token in the environment, in that order. If none is available, fetch the record
   yourself and pass `--record`; do not describe the task from memory.
2. Run, from the repository root:

   ```
   python3 <skill-dir>/scripts/task_boundary.py start <n> --role <Owner|Planner|Implementer|Reviewer> \
     --runtime "<runtime, for example Claude Code project thread>" --reference "<session, thread or task URL>" \
     [--assistant <branch prefix, default claude>] [--branch <branch the runtime assigned>] [--record <file>] [--post] \
     [--base <integration branch, default main>]
   ```

   `--base` names the project's integration branch when it is not the default branch
   (ADR 0005): the task branch starts there and its pull request targets it.

   The helper refuses (exit 2) when #n is not open or lacks the `status:ready` label. The
   owner applies that label; never add it, never start without it, and tell the owner which
   Ready fact is missing instead. It also refuses (exit 3) while another task's claim is
   open: finish that one first, with `--stopped` if needed.
3. On success the helper branches from `main` as `<assistant>/<slug>-<date>` (or keeps the
   branch the runtime assigned when you pass `--branch`), writes
   `conductor-local/claim.json` with the task number, branch, base SHA, role, runtime,
   reference and the allowed paths copied from the record's "Allowed paths" section, drafts
   the claim comment at `conductor-local/claim-comment.md`, and prints the three always-on
   lines (task and allowed paths; owner gates; how to finish).
4. Post the claim comment on #n before changing anything. `--post` does it through `gh`
   when that works; otherwise post the drafted text through your own GitHub access. The
   comment records runtime, reference, time and declared role. Labels and comments are not
   locks: if the record already carries an unreleased claim by someone else, stop and ask.
5. Keep the three lines in view for the rest of the task (`task_boundary.py lines` reprints
   them). Work only inside the allowed paths; anything found outside them is proposed on
   its record and handed to `task-finish --proposal`.

Stop and ask the owner when the record has no allowed paths, when the base branch cannot be
fetched, or when the helper would need to write outside `conductor-local/`.
