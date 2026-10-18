---
name: grilling
description: Interview the owner in rounds of numbered questions with recommended answers until a task record has every Ready fact, or a phase plan has every gate criterion, answered and confirmed. Look up facts yourself; put only decisions to the owner; write the result to the record, not to chat.
---

# Grilling

Native Claude Code copy of the shared grilling technique in `shared/techniques/grilling.md`.
The shared technique remains canonical; this file only makes it discoverable.

1. Read the active project instructions (`CLAUDE.md`, the imported `AGENTS.md`, `PROJECT.md`)
   and resolve the pinned shared-practice snapshot they name. Verify its digest. Then read
   `shared/techniques/grilling.md`, `shared/workflows/backlog.md` and `shared/WORKFLOW.md`
   inside that snapshot and follow them as written. If the snapshot is missing or its
   digest differs, report the mismatch and stop dependent work.
2. Confirm what is being readied: a task record moving from Backlog to Ready, or a phase plan
   being planned backwards from its gate. Confirm its owner. Read the record, its comments
   and any linked plan or spec before asking anything.
3. Map the outcome as a design tree. The frontier is every decision whose prerequisites are
   settled. Ask the whole frontier in one round: number each question, give one recommended
   answer, and word the question so "yes" accepts it. Plain text only; do not route the
   round through AskUserQuestion or another widget, so the owner's answers land in the
   record as written. A question that depends on another still open this round waits.
4. Facts are yours to find. When a question needs a fact from the environment (a file, a
   command's output, a documented limit, an existing record), look it up with Read, Grep,
   Bash or a bounded sub-agent; never ask the owner for it. A running lookup blocks only the
   questions downstream of it; ask the rest now.
5. After each round, recompute the frontier from the owner's answers and ask the next.
   For a task record, stop when every Ready fact has an owner-given or owner-accepted answer:
   bounded outcome, acceptance with its test, non-goals, dependencies, allowed paths and
   actions, data classification, environment, budget, stop conditions, one priority, one
   category. For a phase plan, stop when each gate criterion is project-specific and at most
   three risks each have an owner and a fallback. No cap on rounds; a tree that keeps
   growing means the outcome is too large for one record, which is a question for the owner.
6. Ask the owner to confirm the shared understanding. Then write the answers to the task
   record or phase plan through supported authorized writes (for GitHub, `gh` against the
   record), or return them as a standard update for an authorized recorder.
7. Stop there. Grilling readies a record; it does not select or start the work. Selection
   follows `shared/workflows/backlog.md`; starting follows the common workflow's gates.
