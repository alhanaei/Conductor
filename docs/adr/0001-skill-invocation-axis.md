# ADR 0001: One invocation axis for shared skill wrappers

- Status: Proposed
- Date: 2026-10-18
- Deciders: repository owner; each assistant folder's maintainer for its own copies
- Task record: #29

## Context

Conductor ships shared skill wrappers (`shared/skills/*/SKILL.md`) and native copies per
assistant kit. Nothing today says who may fire a given skill. Claude Code and Codex both
default to letting the model invoke any discoverable skill when its description matches,
so an orchestrating wrapper such as `conductor-init` or `backlog-task` can be reached by
the model mid-task, and a wrapper can reach another wrapper by naming it. The common
workflow's authority rule ("an instruction or skill does not grant permission") holds, but
discoverability still shapes what the model attempts.

mattpocock/skills (source S1 in `sources/SOURCE-REGISTER.md`) resolves this with one
axis, invocation, declared per skill in both harnesses and kept in sync:

- user-invoked: only a human typing its name can fire it; it may call model-invoked skills
  but never another user-invoked one; its description is written for a person browsing
  commands;
- model-invoked: model or human may fire it; its description keeps trigger phrasing so
  auto-invocation works; the test is whether the model could usefully reach for it alone.

The platform mechanics differ: Claude Code reads `disable-model-invocation: true` in
`SKILL.md` frontmatter; Codex reads `policy.allow_implicit_invocation: false` in the
sibling `agents/openai.yaml`. Other kits under `assistants/` have their own or none.

## Decision

Adopt the invocation axis for every shared wrapper and native copy.

1. Each `shared/skills/<name>/SKILL.md` declares `invocation: user` or `invocation: model`
   in its frontmatter. This is the canonical, vendor-neutral declaration; the packaging
   script derives the per-kit fields from it and fails when a native copy disagrees.
2. Classification of the current wrappers:

   | Wrapper | Invocation | Reason |
   | --- | --- | --- |
   | `conductor-init` | user | Onboards a project; irreversible-feeling setup a human starts |
   | `backlog-task` | user | Proposes, readies and selects records on the human's word |
   | `to-tickets` | user | Files sub-tasks; the owner approves the breakdown first |
   | `gate-review` | user | A gate is a decision the owner convenes |
   | `checkpoint-handoff` | model | The model should checkpoint on its own before limits |
   | `coding-task` | model | The discipline for any approved coding task |
   | `analytics-task` | model | The discipline for any approved analytics task |
   | `independent-review` | model | A reviewer session reaches for it unprompted |
   | `grilling` | model | Called by `to-tickets` and by phase planning; useful alone |
   | `project-verification` (kit-only) | model | Verification runs whenever a claim needs evidence |

3. Dependencies between wrappers are operative instructions to call the named
   model-invoked skill, one per call. A user-invoked wrapper is never named as a
   dependency; a step that needs one tells the human to run it.
4. Descriptions follow the axis: user-invoked wrappers get a one-line human-facing
   description; model-invoked wrappers keep trigger phrasing.
5. Mechanics per kit, applied by that kit's maintainer: Claude Code adds
   `disable-model-invocation: true` to user-invoked copies; Codex adds
   `policy.allow_implicit_invocation: false` to the sibling `agents/openai.yaml`. Kits whose
   platform has no such field record the axis in their README and rely on the description.
6. Authority is unchanged. The axis limits discoverability; it never grants permission.
   Every wrapper still defers to the common workflow's authorization rules.

## Alternatives considered

- No declaration (status quo): orchestrators remain model-reachable; rejected because it
  lets the model start onboarding, filing or gating on its own initiative.
- Declare only in native copies, not in `shared/`: rejected because the two harnesses then
  drift and no check can compare them; the shared field is what the packaging script reads.
- A finer taxonomy (user / model / subagent-only): rejected for now; one axis covers the
  observed need and matches the source. Revisit if a wrapper must be reachable by
  subagents but not the parent model.

## Consequences

- Shared change under `docs/contributing.md`: the frontmatter field, the classification
  table, and a packaging-script rule that native copies agree with the shared field.
- Each kit maintainer applies the mechanics in its own folder; Codex copies are requested on
  the rollout record, never hand-edited here.
- `tests/test_conductor_init*.py` gains a case per kit that a user-invoked wrapper carries the
  platform field and a model-invoked one does not.
- Existing adopters see no behaviour change until they regenerate kits; the field is
  additive and ignored by harnesses that do not read it.

## Rollback

Remove the `invocation:` field and the packaging rule in one change; native fields can stay
or go per kit. Nothing downstream depends on the field's presence.

## Source

mattpocock/skills at 49dd158: `.agents/invocation.md` and the `agents/openai.yaml` files
beside user-invoked skills (register entry S1).
