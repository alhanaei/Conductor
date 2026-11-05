# Task boundaries

`task-start` is how an assistant claims one Ready task before editing. `task-finish` is how that assistant records the verification ledger and opens the pull request. The copies in this repository are the source the owner uploads as account skills. Nothing in the repository executes them.

## Sub-features

- `task-start-shape` keeps the refuse rules and the claim comment.
- `task-finish-shape` keeps the ledger, the `Closes #n` line, the milestone comment, and the stopped finish.

## How to get to it (user POV)

- At the start of a session the assistant follows `skills/task-start/SKILL.md`: refuse without `status:ready`, post the claim comment, branch from `main`.
- At the end the assistant follows `skills/task-finish/SKILL.md`: run the verification contract on the exact HEAD, open the pull request, and post the milestone comment. Stopping posts the blocker and opens no pull request.

## Driving it with conductor-verify

Preconditions:

- `conductor-verify doctor` reports `doctor: ok`.
- The worktree contains the skill files at the HEAD in `tested-sha.txt`. A clean tree keeps the proof on that SHA.

- **Claim shape.** From the repository root, run `grep -n -F '**Claim.**' skills/task-start/SKILL.md`, `grep -n -F 'status:ready' skills/task-start/SKILL.md`, `grep -n -F 'Allowed paths:' skills/task-start/SKILL.md`, and `grep -n -F 'never add it yourself' skills/task-start/SKILL.md`. Save the output to `$EVIDENCE/task-start-shape.txt`. Each grep exits 0.
- **Finish shape.** Run `grep -n -F '**Finished.**' skills/task-finish/SKILL.md`, `grep -n -F 'Closes #n' skills/task-finish/SKILL.md`, `grep -n -F 'task-finish --stopped' skills/task-finish/SKILL.md`, and `grep -n -F 'Never merge by hand' skills/task-finish/SKILL.md`. Save the output to `$EVIDENCE/task-finish-shape.txt`. Each grep exits 0.
- **Proof.** Both transcripts exist, every grep exited 0, and `tested-sha.txt` matches `git rev-parse HEAD`.

## Gotchas

- A matching file proves the skill text at that SHA. It does not prove an assistant posted a claim or a milestone. Do not post either comment as a verification side effect.
- The skills grant no authority. A claim comment is not `status:ready`, and a pull request is not a merge.
- `task-start` tells the assistant to refuse an `agent:*` label that names another assistant. Verification does not claim a record.
