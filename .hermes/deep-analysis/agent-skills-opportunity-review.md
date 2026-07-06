# Agent Skills Opportunity Review for Conductor

- source: https://github.com/addyosmani/agent-skills
- inspected_clone: `/tmp/agent-skills`
- target: `/home/alhanaei/projects/Conductor`
- date: 2026-07-01
- mode: analysis only; implementation not authorized by this artifact

## Executive summary

`addyosmani/agent-skills` is useful for Conductor less as a skill catalog to copy, and more as a product/architecture pattern: a skill-driven lifecycle wrapped by slash-command entrypoints, with explicit anti-rationalization, verification gates, and a standing Definition of Done.

Conductor already owns the harder runtime substrate: local-first `.conductor/` state, tmux lane classification, artifact references, access lists, message bus, verification gates, operator summaries, and loop progression. The gap is that Conductor's generated plans and worker task artifacts are still generic (`clarify → design → implement → test → review`) and do not yet encode enough phase-specific engineering method.

Recommended direction: import the *discipline model*, not the whole repo.

## What the external repo contains

Evidence from `/tmp/agent-skills/README.md` and repo inventory:

- 24 skills under `skills/`.
- 8 lifecycle commands: `/spec`, `/plan`, `/build`, `/test`, `/review`, `/webperf`, `/code-simplify`, `/ship`.
- 4 specialist personas: `code-reviewer`, `test-engineer`, `security-auditor`, `web-performance-auditor`.
- Reference checklists: Definition of Done, testing, security, performance, accessibility, observability, orchestration patterns.
- Hook scripts for session start / SDD cache / simplification ignore.
- Tool-specific packaging for Claude Code, Gemini CLI, Antigravity, OpenCode, Cursor, Copilot, Windsurf, Kiro.

Design properties worth adopting:

1. Lifecycle vocabulary: Define → Plan → Build → Verify → Review → Ship.
2. Skills as executable workflows, not prose.
3. Anti-rationalization tables to counter common agent shortcuts.
4. Mandatory verification/evidence at each workflow exit.
5. A standing Definition of Done separate from task-specific acceptance criteria.
6. Parallel fan-out only when independent reports are useful; personas do not call personas.
7. `/build auto` model: approve the plan once, then run every task autonomously, stopping only on failures/risk/ambiguity.
8. Progressive disclosure: `SKILL.md` as entry point, references loaded only when needed.

## Fit with Conductor

### Strong matches

| Agent Skills idea | Conductor equivalent | Improvement opportunity |
|---|---|---|
| Slash lifecycle commands | `go`, `plan review`, `dispatch`, `loop`, `verify`, `approve merge`, `close` | Add lifecycle aliases / operator views that map Conductor commands to Define/Plan/Build/Verify/Review/Ship. |
| Skills as workflows | Conductor task artifacts | Add `method_contract` per task so workers get phase-specific workflow requirements. |
| Definition of Done | Verification gate | Add track-level `definition_of_done.md` and make verification check task acceptance + standing bar. |
| `/build auto` | `conductor loop --watch` | Add an explicit `auto` policy profile for approved tracks: continue through DAG, stop on blockers/risk. |
| Parallel `/ship` fan-out | Conductor message bus + lanes | Add review/audit/test parallel gate for finalization when multiple lanes are available. |
| Anti-rationalization | None yet in Conductor task artifacts | Add method-specific anti-shortcut clauses into generated `task.md`. |
| Skill discovery | Deterministic generic planner | Add intent-to-method mapping during planning without making Conductor call external LLM APIs. |

### Mismatches / do not copy directly

- The repo assumes an agent harness with native skills/plugins/slash commands. Conductor is harness-agnostic and should keep skills as data/artifacts, not as runtime prompt injection magic.
- The repo's commands are user-driven slash commands. Conductor's core value is deterministic outer-loop supervision; avoid replacing that with an LLM lifecycle orchestrator.
- Agent Skills expects git commits per slice. Conductor often operates outside git or degrades to `not_git_repo`; make commit policy optional and project-aware.
- Agent Skills `/ship` uses Claude subagents. Conductor should express this as lane-dispatched review tasks plus a deterministic merge artifact, not hidden subagent calls.

## Recommended Conductor roadmap from this review

### Phase A — Add a Conductor method catalog

Create a local method catalog under Conductor, for example:

```text
src/conductor/methods.py
src/conductor/method_catalog/*.md
```

Initial methods can mirror lifecycle phases without importing the full external repo:

- `spec`
- `plan`
- `build`
- `test`
- `review`
- `ship`
- `debug`
- `security`
- `observability`
- `simplify`

Each method should define:

```json
{
  "method_id": "build",
  "description": "Implement one approved slice incrementally.",
  "when_to_use": ["implementation task", "multi-file change"],
  "required_sections": ["Plan", "Actions Taken", "Evidence", "Self-Evaluation", "Open Risks", "Handoff"],
  "anti_rationalizations": ["Do not test only at the end", "Do not touch unrelated files"],
  "verification_requirements": ["targeted tests", "full relevant suite", "build/typecheck when applicable"]
}
```

Why this matters: Conductor can stay deterministic while producing better worker instructions.

### Phase B — Replace fixed generic DAG with method-tagged DAG

Current `src/conductor/planner.py` uses a fixed scaffold:

```text
clarify → design → implement → test → review
```

Keep that as the fallback, but add method metadata:

```text
clarify/spec -> plan/design -> build/implement -> test/verify -> review/ship
```

Task metadata should include:

- `method_id`
- `acceptance_criteria`
- `definition_of_done_refs`
- `verification_commands`
- `risk_class`
- `autonomy_policy` (`auto_ok`, `stop_on_ambiguity`, `requires_operator`)

### Phase C — Improve task artifacts

Current `render_task_artifact()` gives objective, access, source refs, outputs, and placeholder verification. Extend it to include method-specific workflow contracts:

```markdown
## Method Contract
- method: build
- workflow: RED → GREEN → regression → evidence → handoff

## Anti-Rationalization Guardrails
- Do not implement the whole feature in one pass.
- Do not change files outside the task scope.
- Do not claim completion without command evidence.

## Definition of Done
- Task acceptance criteria met.
- Standing quality bar met.
- Evidence listed below.
```

This is the highest-return improvement.

### Phase D — Add a track-level Definition of Done

Add generated artifacts:

```text
.conductor/tracks/<track>/definition_of_done.md
.conductor/tracks/<track>/quality_gates.json
```

The external repo's `references/definition-of-done.md` gives a useful shape:

- Correctness
- Quality
- Integration
- Documentation
- Ship-readiness

Conductor-specific additions:

- Result artifact is present and non-empty.
- Verification artifact exists and is passed.
- No schema enum violations in worker-written status files.
- No active `blocked_prompt` lanes.
- Operator summary does not recommend final merge/close with unfinalized DAG tasks.

### Phase E — Add `/build auto` equivalent as explicit Conductor policy

Conductor already has `loop --watch`; make the autonomy contract explicit:

```bash
conductor loop --track <id> --watch --policy auto-approved-slices --stop-on-blocked-prompt --json
```

Policy behavior:

- plan must be approved
- proceed through dependency-ordered tasks
- auto-advance verified task slices
- stop on failed verification
- stop on blocked prompt
- stop on ambiguity/risk marker in result.md
- final merge/close only when all planned tasks are finalizable and project policy allows it

### Phase F — Add a final review fan-out gate

Borrow `/ship`'s parallel fan-out idea, but implement it in Conductor terms:

```bash
conductor review fanout --track <id> --json
```

It should create independent review tasks, likely:

- code quality review
- security review
- test coverage review

Then merge them into:

```text
.conductor/tracks/<track>/review/final-verdict.md
.conductor/tracks/<track>/review/final-verdict.json
```

Keep the external repo's rule: personas/reviewers do not invoke each other; the Conductor operator layer merges reports.

## Priority recommendation

Do not start with importing all 24 skills. Start with a narrow Conductor-native adaptation:

1. Add `method_id` to generated tasks and dispatch records.
2. Add a small built-in method catalog for `spec`, `plan`, `build`, `test`, `review`, `ship`.
3. Extend `task.md` rendering with method contract + anti-rationalization + verification requirements.
4. Generate track-level `definition_of_done.md`.
5. Update verification/reconcile to report whether DoD evidence exists.

This gives Conductor most of the value from Agent Skills while preserving its local-first, deterministic, artifact-driven design.

## Suggested first implementation slice

Title: `Add method contracts and Definition of Done artifacts to Conductor task generation`

Likely files:

```text
src/conductor/models.py
src/conductor/planner.py
src/conductor/dispatch.py
src/conductor/store.py
src/conductor/completion.py
tests/test_planner.py
tests/test_dispatch.py
tests/test_completion.py
```

Acceptance criteria:

- `go --plan-only` assigns a `method_id` or equivalent metadata to every task.
- `plan.md` renders method labels for each task.
- `dispatch` renders `task.md` with a method contract and anti-rationalization section.
- Track generation writes `definition_of_done.md`.
- `verify` or `reconcile` surfaces missing DoD/evidence as warnings or issues.
- Existing tests pass; new tests cover method metadata and rendered artifacts.

Verification commands:

```bash
cd /home/alhanaei/projects/Conductor
python -m pytest tests/test_planner.py tests/test_dispatch.py tests/test_completion.py -q
python -m pytest -q
```

## Bottom line

Agent Skills should improve Conductor's *task quality layer*, not replace Conductor's orchestration layer.

Best immediate use: make Conductor-generated tasks carry the same senior-engineering guardrails that Agent Skills encodes manually: explicit phase method, anti-shortcut clauses, evidence requirements, and a reusable Definition of Done.
