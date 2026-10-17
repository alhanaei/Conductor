# Project instructions template for Claude Code Projects

Source template for the **Project settings > Memory > Project instructions** field of a Claude
Code project (beta). Fill every `{{PLACEHOLDER}}`, delete this heading block, and paste the rest
into the field. The field accepts up to 16,000 characters; this brief is well under that. The
field is not in Git: record the filled text, or a digest of it, in the project's installation
record so a later session can tell whether it changed. Repository rules stay in that repository's
`CLAUDE.md`; shared policy stays the pinned snapshot named below. Project memory is notes Claude
writes for itself, never policy.

---

This project is {{PROJECT_NAME}}: {{ONE_LINE_GOAL}}. Work happens in {{REPOSITORY}} and the task
records at {{TASK_RECORDS_URL}}. Shared practice is the pinned policy at
`{{POLICY_SNAPSHOT_PATH}}` (SHA-256 `{{POLICY_SHA256}}`) inside the clone, plus the repository's
`AGENTS.md` and `PROJECT.md`. Read them before dependent work; if the snapshot is missing or its
digest differs, say so in your first message and stop.

Tasks and ownership

- Every thread starts from one labelled task record. If no record exists for what you were
  asked, propose the title and the problem in one or two sentences and wait; do not file it.
- Before changing anything, record the selection on the task record: this project, the thread
  reference, and the time. Do not treat labels or a note as an exclusive lock.
- Take exactly the task you were given. Anything found mid-task is proposed and left as a
  comment on the record it belongs to.
- Each task carries exactly one priority and exactly one category before it is worked.

Branches and pull requests

- Branch from `{{DEFAULT_BRANCH}}`. One branch and one pull request per thread, closing exactly
  the task it names with `Closes #N`.
- Open the pull request only when the task's acceptance is met and the verification below has
  run on the exact head; fill the repository's pull request template, including the
  verification table with tested SHAs.
- Never merge, force-push, rewrite history, change CI configuration, or push to
  `{{DEFAULT_BRANCH}}`. Merge is the owner's gate. Commit and push work in progress on long
  tasks; a resumed sandbox can lose uncommitted changes.

Verification before done

- Run, from the repository root: {{VERIFICATION_COMMANDS}}. Paste the result lines and the
  tested SHA in your final message and in the pull request.
- A claim without the recorded command is not verification. Do not infer commands from another
  repository or from memory.

When something is missing

- If you cannot reach a repository, file, secret, service, connector, or the pinned policy, say
  exactly what is missing in your first message and stop. Do not substitute, mock, or guess.
- Pause for the owner before any deployment, spending, credential or access change,
  publication outside GitHub, or destructive action.

Checkpoints and memory

- Before ending, or when context runs low, update `{{CHECKPOINT_PATH}}` with head SHA, checks
  run, decisions, blocker, and next action, and post the milestone on the task record.
- Decisions go to the task record or the repository's decision records; pitfalls go to the
  repository's docs or `CLAUDE.md`. Project memory may hold reminders of them, but it is not
  the record and can be pruned without loss.

Coordination

- Propose threads and wait for the owner's go-ahead before starting them, and run at most
  {{MAX_PARALLEL_THREADS}} threads at a time. Parallel threads need distinct task records and
  separate branches, and a conflict review for files, APIs, migrations, services, or data they
  share.
- Post when a thread finishes, is blocked, or needs the owner; do not narrate each step.
