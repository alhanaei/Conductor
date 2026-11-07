# Conductor

Conductor is one page of rules and the GitHub pieces that enforce them, for projects where
coding assistants do the work and one owner keeps three decisions: what gets filed, what is
ready to build, and what lands on the default branch. Everything an assistant or GitHub reads
at run time is in this repository; nothing is generated, pinned or copied.

## The eighteen files

| Path | What it is |
| --- | --- |
| `AGENTS.md` | The whole policy: project facts, roles, owner gates, task records, task start and finish, the never-do list, the verification contract. Read natively by Codex, Cursor and Gemini CLI; Claude Code reads it through `CLAUDE.md`. |
| `CLAUDE.md` | `@AGENTS.md` |
| `README.md` | This page: the file list and the adoption steps. |
| `.gitignore` | Keeps local secrets (`.env`) and editor, OS and Python cache files out of the repository. |
| `.github/workflows/pr-policy.yml` | The `linked-task` check: a pull request closes exactly one open task that carries one priority, one category and `status:ready`, and is neither owner-blocked nor tracking; in approval mode `auto` the task's parent is ready too; a `review:required` task holds the merge until the body records a review of the head; in `auto` a task above the assistant priority cap or in an owner-only category must have been readied by the owner; the head commit must belong to this pull request alone (one branch, one head, one pull request). |
| `.github/workflows/ci.yml` | The `verify` check: `git diff --check`, `actionlint` and the checker tests. A project with code replaces the steps with its own verification contract. |
| `tests/test_pr_policy.py` | Standard-library regression tests that run the checker embedded in `pr-policy.yml` against faked `gh` answers; no network. |
| `.github/workflows/backlog-review.yml` | Optional weekly read-only backlog report. |
| `.github/ISSUE_TEMPLATE/task.yml` | The task form with the Ready facts. |
| `.github/pull_request_template.md` | `Closes #n` and the verification ledger. |
| `skills/task-start/SKILL.md`, `skills/task-finish/SKILL.md` | The two task boundaries as prose steps; upload them as account skills. |
| `docs/adr/0002` to `0007` | Decision history. ADR 0006 records the shrink to this shape; ADR 0007 the review gate. |

## Adopting Conductor in a new project

1. Create the repository from this one with GitHub's **Use this template**.
2. Edit the first section of `AGENTS.md` to the project's facts, and its verification
   contract to the project's own commands.
3. In GitHub, repository Settings, Secrets and variables, Actions, Variables: set
   `CONDUCTOR_APPROVAL_MODE` to `manual` or `auto`, and `CONDUCTOR_BACKLOG_REVIEW_ISSUE` to
   the pinned backlog issue if you use the weekly report. `CONDUCTOR_REVIEW_REQUIRED_LABEL`
   renames the label that holds a merge until the pull request records an independent
   review of its head (default `review:required`, ADR 0007); leave it unset to keep the default.
   In `auto`, `CONDUCTOR_ASSISTANT_PRIORITY_CAP` (default unset: no cap) is the highest
   priority an assistant may ready, `CONDUCTOR_OWNER_CATEGORIES` (default unset: none) lists
   the categories only the owner readies, and `CONDUCTOR_OWNER_LOGIN` (default the repository
   owner) is the login whose `status:ready` counts as the owner's; `linked-task` then holds a
   pull request whose task is above the cap or in the list until the owner has readied it
   (ADR 0008). Conductor itself sets `P2` and `kind:security`.
4. In GitHub, repository Settings, Branches: protect the default branch with a required
   pull request, "Do not allow bypassing" on, approvals off, required checks `verify` and
   `linked-task`. In Settings, General, Pull Requests: tick **Allow auto-merge** for `auto`.
5. Create the labels the policy uses: priorities `P0` to `P3`, `blocked:owner`, categories
   `kind:*`, `kind:tracking`, `status:ready`, and optionally `agent:claude`, `agent:codex`,
   `agent:gemini`.
6. Paste `AGENTS.md` into the assistant's project instructions where it has them, and enable
   the two skills on the account.

A policy change is one commit to `AGENTS.md`; `git log -1 -- AGENTS.md` names the revision an
assistant read.
