# Verify contract

The `verify` check fails a pull request that adds trailing whitespace or a conflict marker in its unstaged diff, and fails a workflow file actionlint 1.7.7 rejects. On a clean checkout both CI steps print nothing and exit 0.

## Sub-features

- `verify-whitespace` runs `git diff --check` on a clean tree and expects exit 0 with no output.
- `verify-whitespace-detect` shows the same command rejecting a trailing-whitespace line.
- `verify-workflows` runs `actionlint -color` at 1.7.7 and expects exit 0 with no output.

## How to get to it (user POV)

- Open a pull request, or push to `main`. The `CI` workflow runs the `verify` job.
- On a checkout, run the same two commands the job runs, from the repository root: `git diff --check`, then actionlint 1.7.7 as `actionlint -color`.

## Driving it with conductor-verify

Preconditions:

- `conductor-verify launch` has printed `ready: actionlint 1.7.7` for this `CONDUCTOR_VERIFY_RUN_ID`.
- `conductor-verify doctor` reports `doctor: ok`, `actionlint: 1.7.7`, and `worktree: clean`.
- The HEAD in `tested-sha.txt` is the commit you are proving.

- **Whitespace, CI path.** Run `skills/verify-conductor/scripts/conductor-verify drive verify-contract`. The helper runs `git diff --check` at the repository root. `verify-whitespace.exit` is `0` and `verify-whitespace.stdout` and `verify-whitespace.stderr` are empty.
- **Workflow lint, CI path.** The same drive runs `$SCRATCH/actionlint -color` with the working directory at the repository root. `verify-workflows.exit` is `0` and both output files are empty. The helper prints `verify-contract: pass` and writes `pass` to `verify-contract.result`.
- **Detection.** The same drive adds a detached worktree at `$SCRATCH/whitespace-worktree`, appends a line with a trailing space to that worktree's `README.md`, and runs `git diff --check` there. `verify-whitespace-detect.exit` is `2` and stdout contains `trailing whitespace.`. The helper then removes the worktree.
- **Proof.** Keep `doctor.txt`, `tested-sha.txt`, the three `.exit` files, and `verify-contract.result`. The result file reads `pass` only after all three sub-features succeed.

## Gotchas

- On a clean tree `git diff --check` has an empty diff, so exit 0 does not scan committed blobs. The detection sub-feature is what shows the check can fail. Do not replace the CI command with a different `git diff` invocation.
- The detection finding's line number follows `README.md`. Match `trailing whitespace.`, not a line number.
- A conflict marker in an unstaged diff is reported as `leftover conflict marker` and exit 2. The harness detection uses trailing whitespace.
- actionlint newer or older than 1.7.7 is a doctor failure. The contract names 1.7.7.
- Installing actionlint into the repository root leaves an untracked binary, the tree is dirty, and `drive verify-contract` refuses. Use the helper.
- A dirty worktree is not a clean-HEAD proof even when `git diff --check` exits 0. Commit or stash, then drive again.
- `actionlint` exiting 0 does not prove `linked-task` or the backlog report.
