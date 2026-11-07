# ADR 0008: Thresholds in auto: a priority cap and owner-only categories

- Status: Accepted (owner decision of 2026-11-03, "Yes, auto capped at P2", decision card in
  the project thread "Design permission role sets", 18:22 UTC; record filed and readied on
  the owner's "File and ready the record." on 2026-11-07 15:08 UTC, recorded on #97)
- Date: 2026-11-07
- Deciders: repository owner
- Task record: #97 (top-level record); this file lands with its sub-issue #98
- Amends: ADR 0005 (approval mode `auto` gains two thresholds above which the Ready gate on a
  sub-issue returns to the owner; everything else in the mode stands)
- Amended by: ADR 0009 (2026-11-07): the identity §5 leaves open is Grok, acting as
  `grok-conductor[bot]` through an installation token, as Planner and Reviewer within the
  thresholds; the actor test is no longer a no-op for records Grok readies
- Roles: decision grilled by the Planner (project coordinator); this record written by the
  Implementer (a project thread)

## Context

ADR 0005 §2 delegates everything below a readied top-level record: in `auto` the Planner
files and readies the sub-issues, and GitHub squash-merges a green pull request. The owner's
attention lands once, on the parent. The inventory of 2026-11-01 ("Conductor permissions
and role sets", a Claude Doc) listed about forty-five actions a session can take; four are
enforced by GitHub, the rest by the text of `AGENTS.md`. It also found that every session,
whatever its runtime, acts through the owner's own GitHub login, so every `labeled` event on
every issue names the owner and a label-based gate is auditable only in principle.

The owner asked for thresholds rather than a permission matrix: "ready up to P2". A P0 or
P1 sub-issue, or a security change, is where a wrong Ready costs most and where the owner
wants to be the one who readies. A third approval mode was rejected in ADR 0005 and is not
reopened; the thresholds refine `auto` without adding a mode.

## Decision

1. Approval mode `auto` has two thresholds, recorded as repository variables and mirrored as
   project facts in the first section of `AGENTS.md`:
   - `CONDUCTOR_ASSISTANT_PRIORITY_CAP`, the highest priority the Planner may ready. Default
     unset: no cap, which is ADR 0005 as it stands. Conductor sets `P2`.
   - `CONDUCTOR_OWNER_CATEGORIES`, a comma-separated list of category labels the Planner may
     not ready. Default unset: empty. Conductor sets `kind:security`.
2. A sub-issue above the cap (a priority earlier in `CONDUCTOR_PRIORITY_LABELS` than the cap)
   or carrying a listed category is filed by the Planner with its Ready facts and the native
   parent link, as before, but readied by the owner: `status:ready` is the owner's own label
   on it, applied with a comment naming the approving message, as on a top-level record.
3. `linked-task` enforces the thresholds in `auto` (#99). For the task a pull request closes,
   when the task is above the cap or in the list, the check reads
   `GET repos/{repo}/issues/{n}/timeline`, takes the last `labeled` event for the readiness
   label, and fails when that event's actor is not the owner login
   (`CONDUCTOR_OWNER_LOGIN`, default the repository owner). With both variables unset the
   check behaves exactly as before. A failed timeline lookup, or a timeline with no such
   event, fails the check; it never passes by default.
4. The merge stays automatic on green. The owner's Ready is the attention point; no click is
   added at the pull request. The `review:required` gate of ADR 0007 is independent and
   unchanged; a P0 or P1 record carries both.
5. The actor test is a no-op while every assistant acts under the owner's login: the
   `labeled` event then always names the owner and the check passes. The threshold is still
   written on the page and still binds every session by text, and the check is in place for
   the day the labels are applied by a distinct identity. That identity, an `issues.labeled`
   trigger running the assistant as a GitHub App, or a machine account with Write and not
   Admin, is a separate record, proposed as a line on Backlog #66 (#100). Until it exists
   the enforcement half of this decision is dormant by design, not broken.

## Alternatives considered

- A permission matrix of every action by role and mode. Rejected by the owner (2026-11-01):
  not worth the maintenance; two thresholds cover the risk.
- A third approval mode between `manual` and `auto`. Rejected in ADR 0005 and not reopened:
  a cap on `auto` gives the owner the same control with one fewer setting.
- Holding the merge instead of the Ready (an owner click on the pull request of a capped
  task). Rejected: the owner's attention is better spent before the work starts than after
  it is green, and a click at the pull request would reintroduce the `manual` merge gate for
  a subset of records.
- Reading the claim comment or the Gate comment to find who readied the record. Rejected:
  comments are descriptive, not locks; the `labeled` event actor is the platform's own record
  of who applied the label.
- Waiting for the assistant identity before adding the thresholds. Rejected: the page rule
  and the check are cheap now and the identity record can follow; the owner can set the
  variables today.

## Consequences

- New: this record; the two variables with their defaults in `pr-policy.yml` and its header
  comment (#99); the two facts in `AGENTS.md`; the README adoption step (#100); a Backlog
  line proposing the identity record (#100).
- Changed: ADR 0005 (an "Amended by" line); `AGENTS.md` "Owner gates" and "Task start"
  (what the cap means for Ready); `.github/workflows/pr-policy.yml` and
  `tests/test_pr_policy.py` (#99).
- Owner steps after the check merges: set `CONDUCTOR_ASSISTANT_PRIORITY_CAP=P2` and
  `CONDUCTOR_OWNER_CATEGORIES=kind:security` in the repository variables. Until then the
  defaults apply and the check behaves as ADR 0005 left it.
- Limit: with every session on the owner's login the actor test cannot fail; the page rule
  is the whole of the enforcement until the identity record lands.
- Unchanged: the two modes, the merge on green, the `review:required` gate, branch
  protection, the required-check list, the three owner gates on top-level records.

## Rollback

Unset the two repository variables (the check then behaves as before), remove the threshold
condition from `pr-policy.yml` and its tests, remove the two facts and the sentences from
`AGENTS.md`, delete this record and remove the "Amended by" line from ADR 0005.

## Source

#97 and its Gate comment; the Claude Doc "Conductor permissions and role sets" (2026-11-01);
the owner's decision "Yes, auto capped at P2" (2026-11-03 18:22 UTC) and "File and ready the
record." (2026-11-07 15:08 UTC) in the project thread "Design permission role sets".
