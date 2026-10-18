# ADR 0002: Conductor ships one assistant kit, for Claude Code

- Status: Accepted (owner decision of 2026-10-18, recorded on #36)
- Date: 2026-10-18
- Deciders: repository owner
- Task record: #36
- Roles: decision grilled by the Planner session; this record written by the Implementer session

## Context

Conductor is a shared practice library: `shared/` holds the common workflow, status
definitions, skill wrappers, techniques and templates, written vendor-neutral. Around it
the repository has grown a distribution layer for several assistant products:

- two full kits, `codex/` and `assistants/claude-code/`, each with native copies of the
  shared skill wrappers, a checksum file and an installer profile;
- six one-page notes under `assistants/` for other products (chatgpt, codex, copilot,
  google, grok-build, kilo-code);
- per-kit profiles and pins in the initializer (`shared/skills/conductor-init/`) and its
  tests, with a migration path that blocks until every pinned assistant has migrated;
- a folder-ownership rule in `docs/contributing.md`, because two kits were maintained by
  two assistants;
- a wrapper drift check in `tests/package_conductor_init.py` whose allowlist records
  seven Codex copies owed on #3, #15 and #25, none of them supplied.

`.conductor/adoption.json` for this repository already lists only `claude-code`. The Codex
section of the root `AGENTS.md` still binds the superseded `9d77436` policy. The owner
wants a lightweight library built around one main assistant, with planning and
implementation as roles of sessions rather than as separate products (#37).

## Decision

Conductor ships one kit, for Claude Code. The shared practice stays vendor-neutral.

1. Tag the last multi-kit commit, then delete `codex/` and the six assistant notes under
   `assistants/`. They remain recoverable from the tag and from Git history.
2. Remove the Codex profile from the initializer and from the tests. The initializer keeps
   reading adoption records that name other assistants, as data, so an older adoption can
   still be migrated.
3. Retire the folder-ownership rule in `docs/contributing.md`; one review path covers
   `shared/` and the kit alike.
4. Close the owed Codex copies as not planned: the allowlist entries that name #3, #15 and
   #25, and the matching request comments on those records.
5. Keep `shared/` vendor-neutral in wording, so any assistant can read it as plain
   documentation; nothing in `shared/` names a product.

"One kit" is a statement about what Conductor distributes, not about which assistants a
project may use. A project may still run other assistants against `shared/` as reading.

## Sequencing

- One re-pin. The restructuring lands together with the roles and backlog model of #37, so
  `shared/WORKFLOW.md` changes once, this repository's adoption migrates once, and there
  is no interim policy release.
- The scope of ADR 0001 (#29, PR #30) is settled after this decision: Claude Code
  mechanics only; `backlog-task` and `to-tickets` stay user-invoked because both end at a
  human gate.
- This record closes when this ADR merges. The restructuring work is proposed and filed as
  sub-tasks by the Planner, each passing Gate File and Gate Ready, and implemented by the
  Implementer.

## Alternatives considered

- Keep both kits but freeze Codex: the drift allowlist grows with every new wrapper and
  the ownership rule stays for a kit nobody maintains. Rejected.
- Keep both kits as they are: every new wrapper needs a copy from a Codex session, which
  has not happened for any of the seven owed. Rejected.
- Park the Codex kit in a side folder: keeps the files in the tree with none of the
  maintenance. Rejected in favour of the tag, which recovers them just as well.

## Consequences

- Deleted: `codex/`, `assistants/chatgpt/`, `assistants/codex/`, `assistants/copilot/`,
  `assistants/google/`, `assistants/grok-build/`, `assistants/kilo-code/`, the Codex
  entries in `tests/package_conductor_init.py` (profile table, checksums, allowlist) and
  the Codex profile in the initializer.
- Simplified: the wrapper drift check compares `shared/skills/` with one kit and needs no
  allowlist once the last Claude Code copy lands; `MANIFEST.json` shrinks accordingly.
- Rewritten: `README.md` structure and ownership text; `docs/contributing.md`; the root
  `AGENTS.md` and `CLAUDE.md`, which collapse to one adapter entry for this repository.
- Unchanged: the pinned-policy mechanism, the migrate operation, the verification
  contract, the backlog and lifecycle workflows.

## Follow-up decisions carried on #36 (round 2)

Not settled by this ADR; the Planner grills them and the owner decides on the record.

1. `GUIDE.md`: what happens to its multi-vendor sections and the generated Word export.
   Implementer's proposal: one paragraph saying `shared/` is readable by any assistant;
   regenerate or drop the export in the same pull request.
2. The Codex local-adapter section and the Mac-path bindings in the root `AGENTS.md` and
   `CLAUDE.md`. Proposal: one short vendor-neutral `AGENTS.md` pointing at `CLAUDE.md` and
   the pinned snapshot; the Codex binding and the Mac paths go.
3. Whether old Codex-only adoption records stay readable for migration. Proposal: yes,
   read as data; the cost is small and it strands nobody.
4. Whether a generated Claude Code plugin replaces the copied kit. Proposal: yes, as its
   own record after the restructuring lands.

## Rollback

Check out the tag or restore the deleted folders from it, re-add the Codex profile and
allowlist entries, and revert the contributing and README text. No adopted project depends
on the deleted folders; this repository's adoption names only `claude-code`.

## Source

#36 and its Gate File and Gate Ready comments; the owner's answers to the Planner's
grilling round 1 (Q1) on 2026-10-18; the repository state at `main` ec6d1b0.
