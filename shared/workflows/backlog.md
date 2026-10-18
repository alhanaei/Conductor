# Backlog and selection workflow

The project's task records (GitHub issues or the project's equivalent) are the only
backlog. This procedure governs how work enters that backlog, how it is ordered, and how
it leaves. Label names, priority definitions and the tie-break document are project facts
recorded in the project's own instructions; this file defines the dimensions and the rules.

## Entry

1. Every change starts from a tracked task: feature, fix, documentation, chore or spike.
   A plan agreed in chat is not a backlog until it is recorded. The pull request or
   deliverable names the task it closes.
2. Propose before filing. State the title, the problem in one or two sentences, and why it
   needs its own record rather than a comment on an existing one, then wait for the
   owner's approval. Delegated agents and workflows propose records in their reports and
   never create them. Comments on existing records (findings, audit notes, verification
   results) need no approval.
3. A part of tracked work is a sub-task of that parent, not a sibling: a phase, one
   surface of a sweep, a checklist row. It is a separate task when it stands alone:
   workable without reading the parent, touching different files, or the parent is
   already closed. A sub-task carries its own priority and category because it is worked
   independently. A parent that exists only to hold children is a tracking record and
   needs no priority.

## Readiness

4. A task is Ready, in the sense of the common workflow's gates, only when it carries
   exactly one priority and exactly one category together with the Ready facts: bounded
   outcome, acceptance, non-goals, dependencies, allowed paths, services and actions, data
   classification, environment, budget and stop conditions. A record with no priority and
   no owner-blocked marker is not ready to be worked: propose a priority and wait, as in
   step 2. Tracking records are exempt from priority.
5. Priority is a project-defined ordered scale with written definitions, for example P0
   (live risk or blocker: drop other work and say so) down to P3 (only when already in that
   code). An owner-blocked marker records work no pull request can close: deployments,
   vendor terms, external parties, staging passes. It takes the task out of the queue and
   may sit beside a priority that says what the task will be when it returns. It maps to
   execution state Blocked or Needs approval.

## Selection

6. Take the highest open priority, not the most recent discovery. Within a priority the
   project's tie-break document decides; without one, the oldest Ready task. Record the
   selection on the task before starting, with owner, session reference and time, as the
   common workflow requires.
7. Anything found mid-task is proposed and left: state it with a suggested priority, or add
   it as a comment on the record it belongs to, then finish the current task. A genuine
   top-priority finding is reported at once and work pauses for the owner's call.
8. A side task needs the owner to ask for it. Scope widens or narrows only on the owner's
   word; "while I was in there" is how the queue inverts.

## Completion

9. Done follows the common workflow's gate: the exact delivered identity, verification
   recorded against it, the required review (advisory, never a merge authorization), and
   the merge or artifact identity when acceptance requires it. Closing the task record is
   the last step, not the first.

## Reconciliation

10. Review the backlog on a fixed cadence, weekly by default, as a reconciliation rather
    than a status dump, and record it in the project's review document in a fixed format:
    tasks without a priority or category; priorities untouched since the last review; the
    highest open priority against what was actually worked; owner-blocked tasks and whether
    the blocker still holds; tracking parents with no open children; ownership claims with
    no update. The review is a read-and-report observation under the common workflow; the
    changes it proposes follow steps 2 and 4.

Project templates for GitHub live in [shared/templates/github/](../templates/github/): an
issue form carrying the readiness fields, a pull request template with the verification
ledger, a pull request check for the linked task's labels, and a scheduled reconciliation
report. Copy them into the project's `.github/` and adjust the label names there. The check
accepts `Refs #n` in place of a closing keyword only when every changed file is a record (by
default `docs/adr/` and the checkpoint), because a decision record or a checkpoint documents
a task without closing it; it still requires the referenced task's priority and category.
