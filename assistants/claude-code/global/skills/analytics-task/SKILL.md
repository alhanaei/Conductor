---
name: analytics-task
description: Answer an approved analytical question reproducibly under the project's pinned Conductor analytics workflow, with recorded provenance, reconciliation and limitations, and no publication or production data write on your own authority.
---

# Analytics task

1. Read the active project instructions (`CLAUDE.md`, the imported `AGENTS.md`, `PROJECT.md`)
   and resolve the pinned shared-practice snapshot they name. Verify its digest. Then read
   `shared/workflows/analytics.md` and `shared/WORKFLOW.md` inside that snapshot and follow
   them as written; this skill does not restate them. If the snapshot is missing or its
   digest differs, report the mismatch and stop dependent work.
2. Confirm the task record: the decision it supports, the question, the measurable outputs,
   the authorized data sources and privacy boundaries, and your recorded ownership. Record
   the selection on the task record before any data access.
3. Record input provenance before calculating: source, extraction time, snapshot or version,
   schema, units, grain, identifiers and row counts. Preserve originals; never modify a
   source system. Document every access gap instead of working around it.
4. Define each metric before computing it and build a reproducible script, query or notebook
   with recorded dependencies and seeds. Keep raw sensitive data out of the repository; use
   only the storage the project record allows.
5. Reconcile key totals against the source or an independent calculation, test with small
   known cases, and record tolerances and discrepancies. Follow the reproduction and
   reconciliation row of the project's verification contract; use the
   `project-verification` skill when installed.
6. Deliver labeled outputs with dates, units, sample sizes, definitions, assumptions and
   limitations, plus the reproducibility instructions and artifact locations. Checkpoint at
   the project's destination.
7. Hand the recorded input snapshot and exact code revision to an independent reviewer when
   the workflow calls for it. Publication, sharing, production writes and paid compute need
   explicit authorization; a private draft is not a published result.
