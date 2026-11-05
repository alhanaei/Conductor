# Record templates

The task issue form asks for the Ready facts before a record exists. The pull request template asks for the closing line, the verification ledger, the merge danger, and what was found and left. GitHub shows these texts when a person opens an issue or a pull request. Nothing renders them locally.

## Sub-features

- `task-form` has one priority, one category, the parent, the bounded outcome, the acceptance criteria, the non-goals, the boundaries, and the stop conditions.
- `pr-template` has `Closes #`, the verification ledger, the merge danger, and the found-and-left list.

## How to get to it (user POV)

- In GitHub, choose New issue and the Task form (`.github/ISSUE_TEMPLATE/task.yml`).
- In GitHub, open a pull request. The body starts from `.github/pull_request_template.md`.

## Driving it with conductor-verify

Preconditions:

- `conductor-verify doctor` reports `doctor: ok`.
- The worktree is the HEAD in `tested-sha.txt`. Do not file an issue or open a pull request to see the forms.

- **Task form.** From the repository root, run `grep -n -F 'id: priority' .github/ISSUE_TEMPLATE/task.yml`, and the same for `id: category`, `id: parent`, `id: outcome`, `id: acceptance`, `id: non_goals`, `id: boundaries`, and `id: stop`. Save the output to `$EVIDENCE/task-form.txt`. Each grep exits 0.
- **Pull request template.** Run `grep -n -F 'Closes #' .github/pull_request_template.md`, `grep -n -F '## Verification against the exact head' .github/pull_request_template.md`, `grep -n -F '## Merge danger' .github/pull_request_template.md`, and `grep -n -F '## Found and left' .github/pull_request_template.md`. Save the output to `$EVIDENCE/pr-template.txt`. Each grep exits 0.
- **Proof.** Both transcripts exist and every grep exited 0.

## Gotchas

- Data classification, environment, and budget are described on the `boundaries` field. They are not separate ids. A missing `id: budget` is the form as written, not a failed check.
- The assistant dropdown (`id: assistant`) is optional. The Ready gate does not require it.
- Grep proves the template bytes at this SHA. It does not prove GitHub's form renderer. Do not file a task to watch the form render.
