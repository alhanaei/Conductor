# Conductor

Conductor is one page of rules and two GitHub checks for projects where coding assistants
(Claude Code, Codex, Cursor, Gemini CLI, Grok) do the work and one human owner keeps three
decisions: what gets filed, what is ready to build, and what lands on the default branch.
Every assistant reads the same page, [`AGENTS.md`](AGENTS.md); GitHub enforces it through
branch protection and two required checks. Nothing is generated, pinned or copied, and there
is no application runtime: this repository is documentation, workflows, templates and skills.

It is for a solo owner or a small team who want several assistants to work the same backlog
without a merge they did not decide, a task nobody filed, or a check nobody ran.

## How it works

**Task records.** Every change starts from a GitHub issue filed from the
[task form](.github/ISSUE_TEMPLATE/task.yml) with one priority (`P0` to `P3`), one category
(`kind:*`) and the Ready facts: bounded outcome, acceptance criteria with the test for each,
non-goals, allowed paths, budget and stop conditions. A plan agreed in chat is not a record
([Task records](AGENTS.md#task-records)).

**Three owner gates.** File (an idea becomes a record), Ready (the `status:ready` label, with
a comment naming the approving message) and Merge (the pull request lands). Approval comes
only from the owner's own words; an assistant's message is evidence, not permission
([Owner gates](AGENTS.md#owner-gates), [ADR 0003](docs/adr/0003-backlog-gates-and-roles.md)).

**Two approval modes.** In `manual` every gate is the owner's. In `auto` the owner's File and
Ready on a top-level record reach its sub-issues: the Planner files and readies them, and
GitHub squash-merges a green pull request by itself. Two thresholds hold the Ready back in
`auto`: a priority cap and owner-only categories, above which the owner readies
([ADR 0005](docs/adr/0005-approval-modes.md), [ADR 0008](docs/adr/0008-thresholds-in-auto.md)).

**Four roles.** Owner (human), Planner (the project coordinator: files, grills and splits
records, never pushes), Implementer (one thread, one task, one branch, one pull request) and
Reviewer (a separate thread on a different runtime, advisory unless the record carries
`review:required`). A session holds one role at a time and declares it in its claim comment
([Roles](AGENTS.md#roles), [ADR 0007](docs/adr/0007-review-gate.md),
[ADR 0009](docs/adr/0009-grok-mode.md)).

**Two checks.** `linked-task` ([`pr-policy.yml`](.github/workflows/pr-policy.yml)) refuses a
pull request unless it closes exactly one open task that is Ready, carries one priority and
one category, and, in `auto`, was readied by the right identity; it also keeps one head to one
pull request. `verify` ([`ci.yml`](.github/workflows/ci.yml)) runs the
[verification contract](AGENTS.md#verification-contract). Both are required on the default
branch, so the rules hold even when a session ignores the page.

**Two task boundaries.** [`task-start`](skills/task-start/SKILL.md) turns a Ready record into
a claimed branch with a claim comment and a recorded baseline; [`task-finish`](skills/task-finish/SKILL.md)
runs the contract on the exact head, opens one pull request from the
[template](.github/pull_request_template.md) with the evidence ledger, arms auto-merge in
`auto`, and posts the milestone on the record ([Task start](AGENTS.md#task-start),
[Task finish](AGENTS.md#task-finish), [Never](AGENTS.md#never)).

## Try it

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
   `agent:gemini`, `agent:grok`.
6. Paste `AGENTS.md` into the assistant's project instructions where it has them, and enable
   the two skills on the account.

A policy change is one commit to `AGENTS.md`; `git log -1 -- AGENTS.md` names the revision an
assistant read.

## Status

Lifecycle Active; approval mode `auto`; latest decision ADR 0009. Conductor runs itself with
these rules: its [issues](https://github.com/alhanaei/Conductor/issues) are the task records
and the pinned Backlog issue holds the proposals. Documentation only; no application runtime.
It is deliberately small ([ADR 0006](docs/adr/0006-minimal-core.md)): the policy fits one page,
and anything that would need a generator, a runtime or a second copy of the rules is out.

## The twenty files

| Path | What it is |
| --- | --- |
| `AGENTS.md` | The whole policy: project facts, roles, owner gates, task records, task start and finish, the never-do list, the verification contract. Read natively by Codex, Cursor and Gemini CLI; Claude Code reads it through `CLAUDE.md`. |
| `CLAUDE.md` | `@AGENTS.md` |
| `README.md` | This page. |
| `.gitignore` | Keeps local secrets (`.env`) and editor, OS and Python cache files out of the repository. |
| `.github/workflows/pr-policy.yml` | The `linked-task` check: a pull request closes exactly one open task that carries one priority, one category and `status:ready`, and is neither owner-blocked nor tracking; in approval mode `auto` the task's parent is ready too; a `review:required` task holds the merge until the body records a review of the head; in `auto` a task above the assistant priority cap or in an owner-only category must have been readied by the owner; the head commit must belong to this pull request alone (one branch, one head, one pull request). |
| `.github/workflows/ci.yml` | The `verify` check: `git diff --check`, `actionlint` and the checker tests. A project with code replaces the steps with its own verification contract. |
| `tests/test_pr_policy.py` | Standard-library regression tests that run the checker embedded in `pr-policy.yml` against faked `gh` answers; no network. |
| `.github/workflows/backlog-review.yml` | Optional weekly read-only backlog report. |
| `.github/ISSUE_TEMPLATE/task.yml` | The task form with the Ready facts. |
| `.github/pull_request_template.md` | `Closes #n`, the verification ledger, merge danger, review line, "Found and left". |
| `skills/task-start/SKILL.md`, `skills/task-finish/SKILL.md` | The two task boundaries as prose steps; upload them as account skills. |
| `docs/adr/0002` to `0009` | Decision history. ADR 0006 records the shrink to this shape; ADR 0007 the review gate; ADR 0008 the thresholds in `auto`; ADR 0009 Grok as a readying and reviewing identity. |
