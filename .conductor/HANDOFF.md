# Conductor project checkpoint and cloud handoff

Written 2026-10-16 by the Claude Code desktop session on the owner's Mac, for a successor
cloud session. Verify every fact below against the repository before relying on it; this
file is a record, not authority. Private chat does not migrate; this is the handoff.

## Objective and acceptance

Objective: finish applying Conductor's own practice to this repository and to Claude Code,
after the backlog workflow (PR #5), the GitHub checks (PR #7) and the migration operation
(PR #10) landed on `main`.

Acceptance for the open task (issue #11): project adoption pinned to the PR #10 merge
commit (done, below); the Claude Code personal adapters moved to the same source and
re-verified (Mac only, not done); a fresh-session discovery check after that.

## Current owner, environment and repository

- Owner: the Claude Code desktop session on the owner's Mac held the project-side work;
  it releases ownership with this commit. A successor claims ownership by recording its
  session reference and start time in the task record (issue #11 or the next task's issue).
- Repository: https://github.com/alhanaei/Conductor; branch `main`; this handoff is committed
  on a branch and lands with its PR.
- Working tree at handoff: clean apart from `.agents/`, the Codex local adapter, which stays
  untracked and belongs to Codex.

## Policy binding

- Pinned policy: `.conductor/policy/2a14788454aab84a5c4dbba1fcefc7f21697f07f/shared/WORKFLOW.md`,
  SHA-256 `adefbfa603a3b050593035410ce07bbb42fd27ebbfa4ba0212d48fcbe7a4a0b2`.
- Recorded in the managed section of `AGENTS.md` and in `.conductor/adoption.json`
  (`assistant_pins`: claude-code at 2a14788; `migrations`: aa235f8 to 2a14788 by claude-code).
- The generated skill `.claude/skills/conductor-project-init/` is at the same pin; both
  `migrate` and `onboard` rerun as `unchanged`.

## Completed work, with evidence

- Backlog workflow, priority and category gates, GitHub templates: PR #5, issue #6, PR #7;
  `.github/workflows/` has CI, PR policy and weekly reconciliation; first reconciliation run
  flagged #3, since labelled P1 kind:feature.
- Folder ownership rule: PR #2; `docs/contributing.md`.
- Claude Code kit and initializer mapping: PR #1; `assistants/claude-code/`.
- Policy migration workflow and `migrate` operation: PR #10, issue #9;
  `shared/workflows/migration.md`, 66 tests.
- Project-side migration of this repository: transaction
  `.conductor/backups/0fce5b0002254089ab1322cb153495fb/transaction.json`; 24 updates,
  95 creates, 81 removes, no blockers.
- Issue #8 filed for PR #4 (project-lifecycle workflow, other Claude session); PR #4 is
  up to date with `main` and passes both checks.

## Verification

- `python3 tests/package_conductor_init.py`: verified (87 root digests) at 2a14788.
- `PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s tests`: 66 OK at 2a14788.
- `git diff --check`: clean. CI runs both on every PR and on `main`.
- Not run here: nothing beyond the contract in `PROJECT.md`.

## Remaining work and where it can run

Cloud-capable (everything lives in the repository or on GitHub):

1. Review and merge PR #4 (issue #8); then issue #3's Define phase can start.
2. Translate the shared wrappers that have no native copy, `coding-task`, `analytics-task`
   and `independent-review`, into `assistants/claude-code/`; add a backlog wrapper to
   `shared/skills/` first and translate it too. Propose an issue before filing (rule 2).
3. Extend `tests/package_conductor_init.py` to require a same-named copy of every shared
   wrapper in each kit, so drift fails the package check.
4. Review the weekly reconciliation output and keep open tasks labelled.

Mac only (home files a cloud clone cannot see): the personal half of issue #11, in the
order given by `shared/workflows/migration.md`: new home snapshot of 2a14788 already exists
at `~/.claude/conductor/snapshots/`; update `~/.claude/CLAUDE.md` and the repository
`CLAUDE.md` bindings from snapshot 4f849af to 2a14788; refresh `~/.claude/skills/conductor-init`
from the new source and verify against the kit checksums; regenerate the installation
record and relax the Codex-digest assertion in `claude_verify_installation.py`; fresh
session `/skills` and `/context`.

## Rules the successor must keep

- Every change starts from a labelled issue; propose before filing; the PR names it.
- Take the highest open priority; found mid-task is proposed and left.
- Merge is the owner's gate; the assistant's merges and self-approvals may be refused.
- `shared/` is canonical; Claude edits only `assistants/claude-code/`; generated copies and
  `MANIFEST.json` come from `tests/package_conductor_init.py --write`.
- Cloud sessions see the pushed branch only; push before expecting the cloud to see it.
  The personal `conductor-init` skill is not available there; run the helper from
  `shared/skills/conductor-init/scripts/conductor_init.py` in the checkout instead.

## Blockers and publication state

- No blockers. Nothing unpushed once this handoff's PR is open.
- No deployment, no schedule, no credential or cloud configuration changed by any of this.
