---
name: to-tickets
description: Break an approved outcome, phase plan or spec into vertical-slice sub-tasks, each sized to one fresh session with declared blocking edges, confirm granularity with the owner, and file them as sub-tasks on the project's task source. Never a local scratch tracker; filing authorizes nothing.
---

# To tickets

Native Claude Code copy of the shared to-tickets workflow in `shared/workflows/to-tickets.md`.
The shared workflow remains canonical; this file only makes it discoverable.

1. Read the active project instructions (`CLAUDE.md`, the imported `AGENTS.md`, `PROJECT.md`)
   and resolve the pinned shared-practice snapshot they name. Verify its digest. Then read
   `shared/workflows/to-tickets.md`, `shared/workflows/backlog.md` and `shared/WORKFLOW.md`
   inside that snapshot and follow them as written. If the snapshot is missing or its
   digest differs, report the mismatch and stop dependent work.
2. Confirm the tracked parent (a task record, a phase plan linked from one, or an approved
   spec), its owner and the project's task source and label scale. Read the parent's full
   body and comments. A plan that lives only in chat is recorded as a task first.
3. Read the area: the code, data or documents the work touches, the project glossary and
   the ADRs for that area. Name slices in the project's vocabulary. Note prefactoring that
   would make the change easy; it becomes the first slice.
4. Draft vertical slices: each a narrow, complete path through every layer the outcome needs,
   demoable or verifiable alone, sized to one fresh session with no carried context. Give
   each its blocking edges and check every edge is a real dependency. A wide refactor
   (one mechanical change with codebase-wide blast radius) is sequenced as expand, migrate
   in blast-radius-sized batches, contract, each step its own slice.
5. Present the breakdown to the owner as one grilling round (the `grilling` skill): a
   numbered list with title, blocked by, and what each slice delivers end to end; ask about
   granularity, edges, and what to merge or split. Iterate until approved. If you are a
   delegated agent, put the breakdown in your report and file nothing.
6. File each approved slice as a sub-task of the parent on the project's task source, in
   dependency order so blockers have identifiers first (for GitHub, `gh api` or
   `gh issue create` with the project's issue form fields). Each carries its own priority,
   category and Ready facts; use native blocking relationships where the platform has them,
   otherwise a Blocked by list. Describe behaviour from the user's side; keep file paths and
   code out of the body except a prototype-encoded decision. Link the children from the
   parent; do not close or otherwise edit it.
7. Stop there. Filed slices are selectable under the backlog workflow's priority rule;
   starting one follows the common workflow's Ready to In progress gate, not this skill.
