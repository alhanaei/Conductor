# Conductor verification map

This directory is the maintained source for verifying Conductor's user-facing behavior. Read this index, then use the matching feature file. Conductor has no application UI and no server. An assistant reads `AGENTS.md` (Claude Code reads it through `CLAUDE.md`, which is `@AGENTS.md`). GitHub runs the checks.

## Baseline preconditions

- The checkout is this repository, https://github.com/alhanaei/Conductor, on the commit you mean to prove. Record it with `git rev-parse HEAD` and the policy revision with `git log -1 -- AGENTS.md`.
- Approval mode is `auto`. The integration branch is `main`. Deployment is none.
- Launch with `skills/verify-conductor/scripts/conductor-verify launch` for a fresh `CONDUCTOR_VERIFY_RUN_ID`.
- Run `skills/verify-conductor/scripts/conductor-verify doctor` and require `doctor: ok`, `actionlint: 1.7.7`, and the intended `head:`.
- A clean-HEAD `verify-contract` drive also requires `worktree: clean`.
- Never treat a dirty tree's empty `git diff --check` as the CI proof. CI checks out a clean tree.
- Do not drive GitHub features by creating issues, comments, labels, or workflow runs.

## Driving conventions

- Start every recipe from a launched, doctor-clean toolchain unless that feature's preconditions say otherwise.
- Treat every command as literal. Paths are relative to the repository root.
- The helper drives `verify-contract` only. For every other feature, run the commands in that feature file and save the transcripts into the evidence directory.
- The detection worktree is disposable. The primary checkout is not: do not append probe lines to it.
- Do not remove the evidence directory during cleanup.

## Proof and skip reporting

- Capture the command, its exit code, and the output that shows the result.
- For GitHub Actions logs, match the rendered result line. The log also prints the workflow source, and a match on that source is not a pass.
- Record the feature id, the HEAD SHA, and the entry point (local helper or the GitHub run URL).
- Report an unreachable path with the command you would have run and the unmet precondition. Do not mark it verified through a file read.

## Feature entry contract

Each feature file starts with an H1 and one paragraph, then four H2 sections in order: `Sub-features`, `How to get to it (user POV)`, `Driving it with conductor-verify`, and `Gotchas`.

## Features

- [Verify contract](./verify-contract.md) is the `verify` job: `git diff --check` and actionlint 1.7.7, plus a detection proof that the whitespace check fires.
- [Linked task](./linked-task.md) is the `linked-task` job: a pull request closes one Ready task, and in `auto` it targets `main`.
- [Task boundaries](./task-boundaries.md) are the `task-start` and `task-finish` skills an assistant follows at the edges of a task.
- [Backlog reconciliation](./backlog-reconciliation.md) is the weekly read-only report.
- [Record templates](./record-templates.md) are the task issue form and the pull request template.
