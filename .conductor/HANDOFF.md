# Conductor project checkpoint and handoff

Written 2026-10-18 by the Claude Code cloud session `session_01StPzUiVKVKD13w1SEzRNpu`
(planning session, kept open for planning only) for a successor implementation session.
Verify every fact below against the repository and GitHub before relying on it; this file
is a record, not authority. Private chat does not migrate; this file and the issue
comments it names are the handoff. Supersedes the 2026-10-16 checkpoint, whose cloud items
1 to 3 are done and whose Mac-only items closed with issue #11.

## Split of sessions

- Planning session (this one): grilling, phase planning, gate reviews, filing and
  prioritizing records, reviewing PRs. It does not implement.
- Implementation session (successor): takes Ready records in priority order, works them
  on branches, opens PRs naming the task, stops at the merge gate. It claims a task by
  recording its session reference and start time on the task record before writing.

## Current owner, environment and repository

- Owner at handoff: the planning session released implementation ownership of every open
  record with this commit. No task is In progress. No branch has unpushed work.
- Repository: https://github.com/alhanaei/Conductor; `main` at `3f74d51` (PR #4 merged).
- Cloud clone used so far: `/home/claude/conductor`; the Mac checkout is
  `/Users/dr.ahmedalhanaee/GitHub/Conductor`. Either works; everything is on GitHub.
- Working tree at handoff: clean on `main`.

## Policy binding

- Pinned policy: `.conductor/policy/2a14788454aab84a5c4dbba1fcefc7f21697f07f/shared/WORKFLOW.md`,
  SHA-256 `adefbfa603a3b050593035410ce07bbb42fd27ebbfa4ba0212d48fcbe7a4a0b2`; unchanged by
  every PR named here (checked by `sha256sum` before and after each).

## Done since the last checkpoint, with evidence

- PR #4 merged (`3f74d51`): `shared/workflows/lifecycle.md` (7 phases, gates G0 to G5,
  phase planning routine, seven gate questions), `shared/templates/PHASE-PLAN.md`,
  `shared/skills/gate-review`, Claude Code copy under `global/skills/gate-review`. Issue #8
  closed. CI green.
- Working rule recorded by the owner: a change meant for all assistants is made at the
  generic level first (`shared/`), then translated into the Claude adapter; never
  Claude-first. Applied in every PR below.
- Survey of mattpocock/skills at 49dd158 (MIT) recorded as source S1; five candidates
  chosen, two rejected (its triage state machine; its `.scratch/` local tracker).

## Open pull requests, all from this session, all CI-checked, awaiting the owner's review

| PR | Closes | Branch | Content | CI |
| --- | --- | --- | --- | --- |
| #27 | #26 | `claude/merge-danger-20261018` | Merge danger section in the shared and repo PR templates; G4 question reads it; S1 register entry | green |
| #28 | #25 | `claude/grilling-to-tickets-20261018` | `shared/techniques/grilling.md`, `shared/workflows/to-tickets.md`, wrappers, Claude Code copies, Codex allowlist, `lifecycle.md` steps 1 and 3 link them, Copilot and cloud-agent wording | green |
| #30 | refs #29 | `claude/adr-invocation-axis-20261018` | `docs/adr/0001-skill-invocation-axis.md` (Proposed), README structure line, S1 entry | `verify` green; `linked-task` red by design (Refs, not Closes) |
| #20 | #18 | other session | Claude Code Projects in the kit | not reviewed here |
| #22 | #19 | other session | verified background mode in the handoff workflow | not reviewed here |

All three of #27, #28 and #30 add the same S1 line to `sources/SOURCE-REGISTER.md` with
identical text; the second and third merge clean. All are two-way doors.

Owner decision pending on #30: merge over the red `linked-task` check, or switch to
`Closes #29` and open a fresh rollout record after acceptance. The check only recognizes
closing keywords, which affects every future ADR PR.

## Open task records, by priority

| Record | Priority | Phase | State | What the implementation session does |
| --- | --- | --- | --- | --- |
| #3 Define phase, orchestrator MVP | P1 | Define, toward G1 | Backlog; dependency on #4 cleared | Nothing yet. The planning session runs grilling on it first; it becomes Ready when the Ready facts and G1 criteria are answered on the record. Then `to-tickets` files the Define outputs as sub-tasks; those are what the implementation session takes. |
| #18 Claude Code Projects in the kit | P2 | library | PR #20 open | Review only |
| #25 grilling and to-tickets | P2 | library | PR #28 open | Nothing; await merge. After merge, the Codex copies remain requested on #25 (Codex session) |
| #26 Merge danger | P2 | library | PR #27 open | Nothing; await merge |
| #19 verified background mode | P3 | library | PR #22 open | Review only |
| #29 invocation axis rollout | P3 | library | Backlog; depends on ADR acceptance (PR #30) and PR #28 | After acceptance: (a) `invocation:` field in every `shared/skills/*/SKILL.md` plus packaging rule and tests; (b) Claude Code kit mechanics; (c) Codex kit mechanics by a Codex session; (d) other kits note the axis. Each is a sub-task of #29. |
| #31 retro step in the handoff workflow | P3 | library | Backlog; depends on PR #28 | `shared/workflows/handoff.md` closing step or `shared/techniques/retro.md`, wrapper, Claude copy, Codex allowlist; output is proposals on the record, never edits |

Codex-maintainer requests on record (not for a Claude session): `codex/` copies of
`gate-review` (#3 comment), `grilling` and `to-tickets` (#25); Copilot folder note (#25).

## Verification at `main` 3f74d51 and at every open branch head

- `python3 tests/package_conductor_init.py`, cwd `.`: verified (96 root digests at main;
  97 on #30; 102 on #28).
- `PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s tests`, cwd `.`: 72 OK.
- `git diff --check`: clean.
- `sha256sum shared/WORKFLOW.md`: `adefbfa6…` everywhere.
- Note for cloud clones: the suite needs commit `9d7743620ee23c6e2219878fea314ea47b1941b1`
  reachable; a shallow clone fails `setUpClass` until `git fetch --depth=200 origin main`.

## Next executable step for the implementation session

1. Read `PROJECT.md`, this file, and `shared/workflows/backlog.md` at the pinned policy.
2. Check whether the owner merged #27, #28, #30; sync `main`.
3. Take the highest open Ready record. At handoff none is Ready for implementation: #3
   becomes Ready only after the planning session's grilling; #29 and #31 wait on merges.
   If nothing is Ready, stop and report; do not invent work.
4. When #3's sub-tasks appear (filed by the planning session via `to-tickets`), claim one by
   commenting session reference and start time, branch `claude/<slug>-<date>`, work it under
   `shared/workflows/coding.md`, open the PR with `Closes #<n>` and the Merge danger section,
   stop at the merge gate.

## Rules the successor must keep

- Every change starts from a labelled issue; propose before filing; the PR names it.
- Highest open priority first; anything found mid-task is proposed on its record and left.
- Merge is the owner's gate; do not merge, even with green CI, unless the owner says so.
- `shared/` is canonical and generic first; Claude edits only `assistants/claude-code/`
  and the root shared files; generated copies and `MANIFEST.json` come from
  `tests/package_conductor_init.py --write`; `codex/` and `assistants/copilot/` are
  requests on the record, never edits.
- Git attribution: commits end with the session's Co-Authored-By and Claude-Session lines;
  PR bodies end with the generated-with footer.
- Cloud sessions see pushed branches only; the git proxy blocks GraphQL, so use
  `gh api repos/...` (REST), not `gh issue create` or `gh pr create`.

## Blockers and publication state

- No blockers. Nothing unpushed. No deployment, schedule, credential or cloud configuration
  changed. No background jobs running.
