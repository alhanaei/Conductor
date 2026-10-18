---
name: independent-review
description: Review an exact head SHA independently against the task's acceptance under the project's pinned Conductor review workflow, returning an advisory status with evidence and never editing the implementation, approving your own work or authorizing a merge.
---

# Independent review

1. Read the active project instructions (`CLAUDE.md`, the imported `AGENTS.md`, `PROJECT.md`)
   and resolve the pinned shared-practice snapshot they name. Verify its digest. Then read
   `shared/workflows/review.md` and `shared/WORKFLOW.md` inside that snapshot and follow them
   as written; this skill does not restate them. If the snapshot is missing or its digest
   differs, report the mismatch and stop dependent work.
2. Work in a separate session from the implementer, against the stated head SHA and base SHA.
   Read the task record, its acceptance criteria and the project standards. If the branch
   has moved, say that the review covers the old head only until you review the new diff.
3. Verify the diff against acceptance. Inspect correctness, edge cases, regression risk,
   security and privacy boundaries, concurrency, performance and maintainability as relevant.
   Prioritize material findings over cosmetic preferences.
4. Inspect the tests critically and run the focused checks the project's verification
   contract defines, from their recorded working directories. For analytics, recompute key
   results from the recorded input snapshot. Do not equate static reading with runtime proof.
5. Report each finding with severity, exact location, failure mechanism, impact, evidence and
   a recommended correction. Label uncertain concerns as hypotheses. No findings is a valid
   result when its limits are stated.
6. Return exactly one status: changes requested; no blocking findings within reviewed scope;
   or unable to complete review. Include reviewed base and head SHAs, commands actually run,
   remaining risks and coverage limits. The status is advisory and never authorizes a merge,
   release or deployment.
7. Do not edit implementation files, resolve the implementer's threads for them, or
   re-review your own implementation. After fixes, review the new head and re-run the checks.
