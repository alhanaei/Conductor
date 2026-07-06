# Conductor

Conductor is a dispatcher-style agent control plane for coordinating multiple tmux-backed AI agent lanes across multiple tasks through a unified messaging and state layer.

## Current Status

- Project stage: Phase 6 implemented (Hermes/Telegram operator surface) — all 6 planned phases complete
- Implementation authorization: granted (Phases 1–6)
- Primary runtime target: tmux-backed local agent lanes
- Core concept: one top-level conductor manages task decomposition, routing, worker coordination, messaging, monitoring, and verification.

## Phase 6 Operator Surface (implemented)

Operate Conductor from Hermes/Telegram-style chat through safe, artifact-grounded
outputs — a pure projection layer (no Telegram API, no daemon, no network).

```bash
python -m conductor operator summary    [--track <id>] [--format json|text|telegram]
python -m conductor operator notify      --track <id> --json   # signal/severity/dedupe_key/next_command
python -m conductor operator heartbeat   --track <id> [--now <iso>] --json   # deterministic 5-min cadence
python -m conductor operator approval    --track <id> --kind plan|merge --json
python -m conductor operator verify-hook --track <id> --json   # commands Hermes should run next
python -m conductor operator artifacts   --track <id> --json
```

Summaries are bounded/Telegram-safe; every claim links back to an existing
artifact under `.conductor/tracks/<track>/`.

## Phase 5 Verification-Gated Completion (implemented)

Worker completion is not true completion. The conductor verifies independently
(a worker's `TASK_COMPLETE`/`result.md` is a claim; `verify` writes the verdict),
gates merge on verified tasks, gates close on merge approval, and can reconstruct
state from artifacts.

```bash
python -m conductor verify        --track <id> --json                 # write per-task verification verdicts
python -m conductor fix           --track <id> --task <task_id> --json # bounded fix-loop (max 3)
python -m conductor approve merge --track <id> --json                 # requires verified tasks
python -m conductor close         --track <id> --json                 # requires merge approval; writes final summary
python -m conductor reconcile     --track <id> --json                 # resume reconciliation report
```

Per-task `verification.json`/`verification.md` and track-level `summary.json`/`summary.md`
and `reconciliation.json`/`reconciliation.md` are written under `.conductor/tracks/<track>/`.

## Phase 4 Dispatch Loop (implemented)

Turn an approved plan's ready tasks into dispatch-ready work: deterministic
routing (kind → provider), worktree/branch allocation (degrades cleanly outside
git), route-decision records, compact task artifacts, follow-up/nudge surfaces,
and a stale-risk classifier. Lane delivery reuses Phase 3 safety — non-ready
lanes degrade to `pending_lane`/`blocked_lane` rather than unsafe paste.

```bash
python -m conductor dispatch    --track <id> --json                      # route + allocate + (safe) submit ready tasks
python -m conductor task status --track <id> --task <task_id> --json     # rich per-task runtime status
python -m conductor followup     --track <id> --task <task_id> --body-file <path> --json
python -m conductor nudge        --track <id> --task <task_id> --json
```

Dispatch requires an approved plan and never promotes a task to complete
(verification is Phase 5). Per-task artifacts live under
`.conductor/tracks/<track>/tasks/<task_id>/` (`task.md`, `route.json`, `status.json`).

## Phase 3 tmux Lane Adapter (implemented)

Safely observe and address visible tmux agent lanes. Readiness is classified
deterministically (`absent / shell / provider_ready / busy / blocked_prompt /
unknown`) and `submit` refuses anything that is not `provider_ready` — it never
pastes work into a bare shell, and sends only a short artifact reference.

```bash
python -m conductor lane ensure  --target Conductor:claude --json   # create the tmux window (shell)
python -m conductor lane status  --target Conductor:claude --json   # classify readiness
python -m conductor lane capture --target Conductor:claude --json   # capture recent transcript
python -m conductor lane submit  --target Conductor:claude --task-file <path> --json  # safe artifact-ref submit
```

Provider profiles: `claude`, `codex`, `gemini`, `grok` (`cursor`/`opencode` are
future extension points). Lane state persists under `.conductor/lanes/`.

## Phase 2 Goal Intake (implemented)

Turn a goal into a durable, reviewable, approval-gated plan with a deterministic
task DAG and per-task access lists. No dispatch/tmux/providers yet.

```bash
python -m conductor go --plan-only "<goal>" --json        # goal -> spec.md + plan.md + task DAG (pending approval)
python -m conductor plan review --track <track_id> --json # machine-readable plan + gate state
python -m conductor approve plan --track <track_id> --json # explicit, idempotent approval gate
```

## Phase 1 Kernel (implemented)

A local-first, file-backed state and message substrate under `.conductor/`.
No tmux/provider/worktree/Telegram/dispatch yet — those attach to this layer later.

```bash
python -m pip install -e .                 # installs the `conductor` CLI
python -m conductor init                   # create .conductor/ state root
python -m conductor track new "<goal>"     # create a track (spec/plan/metadata)
python -m conductor message send --track <id> --type PROGRESS --body "..." --worker w1
python -m conductor message list --track <id> --json
python -m conductor lock acquire --track <id> --file <path> --worker <id>
python -m conductor status --json          # operator status across all tracks
python -m conductor doctor --json          # state-root health
python -m pytest -q                        # test suite
```

Every command accepts `--json` (before or after the subcommand) for
Hermes/Telegram automation. See `.hermes/deep-analysis/next-build-plan.md` for
the full phased plan.

## Planning Artifacts

See `.hermes/deep-analysis/`:

- `application-profile.md` — product intent, users, capabilities, and initial scope
- `architecture-map.md` — target architecture and subsystem boundaries
- `next-build-plan.md` — phased implementation plan, currently unauthorized for execution
- `open-questions.md` — decisions needed before build
- `decision-history.md` — accepted decisions so far
