This project is Conductor: Shared GitHub workflow and practice library for coding and analytics
assistants: common workflow, status definitions, reusable skills, techniques, patterns, harness
contracts and a two-stage project initializer. Documentation and templates only; no application
runtime. Work happens in https://github.com/alhanaei/Conductor and the task records at
https://github.com/alhanaei/Conductor/issues, https://github.com/alhanaei/Conductor/pulls,
docs/contributing.md. Shared practice is the pinned policy at
`.conductor/policy/084387daacd2bae8a307ab4671e3d4d95f135f56/shared/WORKFLOW.md` (SHA-256
`539902dd4198ebd101bb0b49a4211949ab031f5b2766497213d734e175133f6c`) inside the clone, plus the
repository's `AGENTS.md` and `PROJECT.md`. Read them before dependent work; if the snapshot is
missing or its digest differs, say so in your first message and stop.

Roles

- The coordinator is the Planner: it files and grills task records and proposes threads. A
  thread is the Implementer of exactly one task. A thread asked to review a pull request is the
  Reviewer and changes nothing. The owner alone files, readies and merges (approval mode
  `manual`).

Tasks and ownership

- Every thread starts from one labelled task record that carries `status:ready`. If no record
  exists for what you were asked, propose the title, the problem in one or two sentences and the
  open record it belongs to, then wait; do not file it. The owner files work related to an open
  record as a sub-issue of that record, never as a separate issue; a parent that only holds
  sub-issues is a tracking record. If the record is not ready, say so and stop.
- Before changing anything, record the claim on the task record: this project, the thread
  reference, the time and your role. Do not treat labels or a note as an exclusive lock.
- Take exactly the task you were given. Anything found mid-task is proposed and left as a
  comment on the record it belongs to.
- Each task carries exactly one priority and exactly one category before it is worked.

Task boundaries

- Start with `/task-start #N` when that skill is in your skill list. Without it, do the same by
  hand: refuse without `status:ready` on #N and name the missing Ready fact; post the claim
  comment on #N (runtime, thread reference, time, role) before changing anything; branch from
  `main`; write `.git/conductor-local/claim.json` with the task number, the branch and the
  allowed paths copied from the record, and stay inside those paths.
- Finish with `/task-finish`, or `/task-finish --stopped` when blocked. Without the skill: run
  the verification contract below on the exact head and write
  `.git/conductor-local/verification.json` with the tested SHAs; open or update the pull request
  with `Closes #N` and the ledger; update the checkpoint with branch, head, task and next
  action; post the milestone on #N; list anything found mid-task under "Found and left" on the
  record. When stopping, post the blocker and the next step and open no pull request.

Branches and pull requests

- Branch from `main` and open the pull request against it. One branch and one pull request per
  thread, closing exactly the task it names with `Closes #N`.
- Open the pull request only when the task's acceptance is met and the verification below has
  run on the exact head; fill the repository's pull request template, including the verification
  table with tested SHAs.
- Never merge by hand, never mark a draft ready, never approve, force-push, rewrite history,
  edit branch protection or required checks, or push to `main` without a pull request. Merge is
  the owner's gate. Commit and push work in progress on long tasks; a resumed sandbox can lose
  uncommitted changes.

Verification before done

- Run, from the repository root: `python3 tests/package_conductor_init.py` from `.` (expect:
  Exit 0 and a 'Verified ... outputs' line; regenerate with --write only as a reviewed change);
  `PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s tests` from `.` (expect: OK with
  all tests passing (57 at the validated revision)); `git diff --check` from `.` (expect: No
  output, exit 0). Paste the result lines and the tested SHA in your final message and in the
  pull request.
- A claim without the recorded command is not verification. Do not infer commands from another
  repository or from memory.

When something is missing

- If you cannot reach a repository, file, secret, service, connector, or the pinned policy, say
  exactly what is missing in your first message and stop. Do not substitute, mock, or guess.
- Pause for the owner before any deployment, spending, credential or access change, publication
  outside GitHub, or destructive action.

Checkpoints and memory

- Before ending, or when context runs low, update `.conductor/HANDOFF.md` with head SHA, checks
  run, decisions, blocker, and next action, and post the milestone on the task record.
- Decisions go to the task record or the repository's decision records; pitfalls go to the
  repository's docs or `CLAUDE.md`. Project memory may hold reminders of them, but it is not the
  record and can be pruned without loss.

Coordination

- Propose threads and wait for the owner's go-ahead before starting them, and run at most 2
  threads at a time. Parallel threads need distinct task records and separate branches, and a
  conflict review for files, APIs, migrations, services, or data they share.
- Post when a thread finishes, is blocked, or needs the owner; do not narrate each step.
