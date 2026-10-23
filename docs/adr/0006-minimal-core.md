# ADR 0006: Minimal core

- Status: Accepted (owner decision of 2026-10-23, recorded on #68 from the project thread
  "Minimal core shrink")
- Date: 2026-10-23
- Deciders: repository owner
- Task record: #68 (top-level record; this file lands with its first sub-issue)
- Supersedes: the distribution and generation parts of ADR 0002 (the kit), ADR 0004 (the
  generator, the four adapter profiles, the policy pin and digest, the checkpoint file) and
  ADR 0005 §4 (where the mode is recorded). The gates, roles, task boundaries, sub-issue rule
  and the two approval modes those records define stand.
- Roles: decision grilled by the Planner (project coordinator); this record written by the
  Implementer (a project thread)

## Context

At `main` ab67b35 Conductor was 259 files and about 30,100 lines. Of those, the text an
assistant or GitHub actually reads at run time was about 1,300 lines: the pinned policy,
the roles page, the pasted project instructions, `PROJECT.md`, the two check workflows,
the templates and the two boundary skills. The other 28,800 lines existed to copy, pin,
generate or test that text: an initializer with golden-output tests, an embedded copy of
the repository inside a native skill, a digest-verified policy snapshot, generated adapter
text, a checkpoint file, ten workflow pages, prompts, a harness schema, a guide and its Word
export. The embedded copy was already stale (`Unknown adapter input: integration_branch`),
and project threads, the one runtime in use, load none of it: they read `CLAUDE.md`, the
pasted project instructions and the two account skills.

On 2026-10-23 at 16:20 UTC the owner said Conductor "is too complicated" and asked for
alternatives. After a comparison with GitHub-native and third-party options, the owner
chose at 16:58 UTC to shrink Conductor to a minimal core and approved the plan at 17:11 UTC
("Conductor minimal core plan") with three additions: an optional assistant label on
records, a Planner handoff report when a parent closes, and the three-level record
hierarchy made explicit.

## Decision

Conductor is one page of rules plus the GitHub pieces that enforce them, and nothing else.

1. **One page.** `AGENTS.md` holds the whole policy: project facts, roles, owner gates,
   task records and hierarchy, grilling and splitting, task start, task finish, the
   never-do list, the verification contract and the missing-input rule. It is read natively
   by Codex, Cursor and Gemini CLI, through `@AGENTS.md` by Claude Code, and it is the text
   the owner pastes into the claude.ai project instructions, so the two cannot drift
   without a visible diff. `CLAUDE.md` is the single line `@AGENTS.md`.
2. **No pin, no generator.** Git history is the pin: `git log -1 -- AGENTS.md` names the
   revision an assistant read. Nothing is generated, copied, digested or snapshotted. A
   policy change is one commit in one file.
3. **Enforcement stays in GitHub**, as ADR 0004 §5 put it: branch protection on `main`
   with no bypass and the required checks `verify` and `linked-task`; `pr-policy.yml`
   unchanged; "Allow auto-merge" on; the repository variable `CONDUCTOR_APPROVAL_MODE`.
   `verify` runs `git diff --check` and `actionlint` only; there are no Python tests left
   to run.
4. **Two prose skills.** `skills/task-start/SKILL.md` and `skills/task-finish/SKILL.md`
   describe the two boundaries as steps, without a helper script. The claim comment on the
   issue and the ledger in the pull request were always the record; the local claim and
   evidence files under `.git/conductor-local/` were a convenience and go with the script.
   The owner uploads the two files as account skills.
5. **Records.** Three levels and no more: a top-level record (filed and readied by the
   owner), its sub-issues (filed and readied by the Planner in `auto`), and a tracking
   parent when a record only holds sub-issues. An optional `agent:claude`, `agent:codex` or
   `agent:gemini` label says which assistant may claim a record; no label means any. When
   the last child of a tracking or top-level parent closes, the Planner posts a handoff
   report as the parent's closing comment: every child with its pull request and merge SHA,
   the verification evidence, decisions taken, anything found and left, and the next record
   to open.
6. **Adoption** is GitHub's "Use this template" plus two repository variables and the
   branch protection the owner sets; `AGENTS.md`'s first section is edited to the new
   project's facts. Nothing is initialized.

What stays, sixteen files: `AGENTS.md`, `CLAUDE.md`, `README.md`, the three workflows, the
issue form, the pull request template, the two skills, and ADR 0002 to 0006. What goes is
listed in the plan and deleted in one pull request, one commit per group, after the page
and the new `verify` are on `main`. The full tree stays readable at ab67b35.

## Alternatives considered

- Keep the generator and add a fourth adapter per the ADR 0004 plan. Rejected by the owner:
  every runtime in use reads one instructions file; generating four copies of it is the
  complexity being removed.
- Replace Conductor with a third-party orchestrator (Agent HQ, Symphony, Mergify, Devin,
  OpenHands, CodeRabbit). Rejected: each adds a subscription, a bot identity or a hosted
  queue, and none provides the owner gates on records that the two workflows already do.
- Keep the digest-verified pin with a smaller snapshot. Rejected: the project instructions
  carry the same text as `AGENTS.md`, so a drift shows up as a diff, and git names the
  revision without a hash.
- Keep the Python helper behind the skills. Rejected: the skills are read by assistants
  that can run the steps directly; the helper's only durable outputs were the comment and
  the pull request body.

## Consequences

- New: this record; `verify` rewritten; `README.md` rewritten to the template story;
  `AGENTS.md` rewritten; `CLAUDE.md` trimmed; `skills/` added; `agent:*` labels; an
  optional Assistant field on the issue form.
- Deleted, after the above are on `main`: `.claude/`, `.conductor/`, `assistants/`,
  `shared/`, `tests/`, `sources/`, `GUIDE.md`, `MANIFEST.json`, `PROJECT.md`, the non-ADR
  pages under `docs/` and the Word export.
- Superseded in the earlier records: ADR 0002's kit and manifest, ADR 0004 §2 "Policy
  pin", §3 "The adapter contract", §4 "Four profiles" and §6 where it describes generated
  output, ADR 0005 §4 "Where the mode is recorded" (now: the `Approval mode` line of
  `AGENTS.md` and the repository variable). The gates, roles, boundaries, sub-issue rule
  and the two modes stand unchanged.
- Given up on purpose: the two-stage initializer, the four-profile adapter plan, the
  checkpoint file, the harness schema and the analytics workflow pages. A project that
  needs one of them back opens a new record with its own reason, not a revert.
- Owner steps, once: re-paste `AGENTS.md` as the project instructions, replace the two
  account skills, optionally mark the repository as a template. GitHub settings and
  variables stay as they are.

## Rollback

Revert the deletion pull request (one commit per group, so a single group can come back
alone), then revert the page and foundation pull requests. The tree at ab67b35 is the
reference.

## Source

#68 and its Gate File comment; the owner's messages in the project thread "Off-the-shelf
alternatives to Conductor" on 2026-10-23 (16:20, 16:58 and 17:11 UTC); the plan "Conductor
minimal core plan" (Claude Doc, 2026-10-23); the repository at `main` ab67b35.
