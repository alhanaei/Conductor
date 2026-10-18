---
name: coding-task
description: Execute an approved, bounded coding task under the project's pinned Conductor coding workflow, with verification evidence recorded against the exact head and no merge, release or deployment on your own authority.
---

# Coding task

1. Read the active project instructions (`CLAUDE.md`, the imported `AGENTS.md`, `PROJECT.md`)
   and resolve the pinned shared-practice snapshot they name. Verify its digest. Then read
   `shared/workflows/coding.md` and `shared/WORKFLOW.md` inside that snapshot and follow them
   as written; this skill does not restate them. If the snapshot is missing or its digest
   differs, report the mismatch and stop dependent work.
2. Confirm the task record, its acceptance and non-goals, your recorded ownership and the
   authorization you actually hold. Record the selection on the task record before writing,
   as the common workflow requires. No record or no priority means propose and wait.
3. Inspect the real repository state: identity, branch, base and head, uncommitted changes,
   existing tests and the implementation paths the task touches. Capture the baseline,
   including pre-existing failures, before changing anything.
4. Implement the smallest coherent change in reviewable increments with tests for behavior,
   boundaries and regressions. Keep to the repository's conventions and the task's allowed
   paths. Anything found mid-task is proposed on the record it belongs to and left.
5. Run the checks named in the project's verification contract from their recorded working
   directories; use the `project-verification` skill when installed. Record command, cwd,
   result and tested SHA. Do not infer commands from another repository.
6. Checkpoint at the project's destination with head, checks, decisions, blocker and next
   action. Push or open a pull request only within the task's recorded authorization, to the
   named repository and branch, with the pull request naming the task it closes.
7. Stop at the task's completion gate. Submit to independent review when the workflow calls
   for it; never merge, release or deploy because the change looks right or CI is green.
