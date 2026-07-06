# Conductor — Target Architecture Map

## Status

- stage: architecture draft
- evidence_level: inferred from user intent + existing dispatcher patterns
- implementation_authorized: false

## System Shape

```text
Operator / Telegram / CLI
          |
          v
+-----------------------------+
| Conductor Control Plane     |
| - intake                    |
| - planner / DAG builder     |
| - scheduler / router        |
| - monitor / verifier        |
| - notification policy       |
+-----------------------------+
          |
          v
+-----------------------------+
| Unified Messaging Layer     |
| - message envelope          |
| - event log                 |
| - task/run correlation      |
| - follow-up artifacts       |
+-----------------------------+
          |
          v
+-----------------------------+
| tmux Lane Runtime           |
| claude | codex | gemini ... |
+-----------------------------+
          |
          v
+-----------------------------+
| Project Workspaces          |
| repo files, tests, services |
+-----------------------------+
```

## Core Subsystems

### 1. Control Plane

Owns the outer loop:

- receives a goal
- creates workflow graph
- selects lanes
- writes task artifacts
- submits task prompts
- monitors state/events
- requests verification
- closes or escalates tasks

The control plane must stay deterministic where possible. Model calls can propose plans/routes, but validation should happen through schema and policy checks.

### 2. Workflow / Task Graph

Each goal becomes a workflow:

```text
workflow_id
  task_id
    dependencies
    owner_lane
    state
    input_refs
    output_refs
    verification_refs
```

Recommended task states:

```text
pending -> ready -> dispatched -> working -> ready_for_review -> verifying -> complete
                                             \-> blocked
                                             \-> failed
                                             \-> cancelled
```

### 3. Unified Messaging Layer

Message envelope draft:

```json
{
  "message_id": "msg_...",
  "workflow_id": "wf_...",
  "run_id": "run_...",
  "task_id": "task_...",
  "sender": {"type": "operator|conductor|worker|system|verifier", "id": "..."},
  "recipient": {"type": "lane|task|workflow|operator|broadcast", "id": "..."},
  "kind": "assignment|status|question|result|event|verification|followup",
  "body_ref": "messages/msg_...md",
  "summary": "short operator-visible summary",
  "requires_ack": false,
  "created_at": "ISO-8601",
  "causation_id": "optional prior message_id",
  "correlation_id": "workflow/run/task scope"
}
```

Important rule: large bodies should be saved as artifacts and referenced by path, not pasted raw into tmux lanes.

### 4. Lane Runtime Adapter

tmux is the first runtime backend. It should support:

- ensure lane exists
- classify lane readiness
- submit short artifact-based instruction
- capture pane output
- detect obvious prompts/auth blocks
- map pane to lane target (`<project>:<provider>`)

Provider-specific quirks belong at adapter edge.

### 5. Scheduler / Router

Routing inputs:

- task type: implementation, debugging, review, research, runtime, ops
- task risk: low, normal, high
- lane capability
- lane health
- lane busy/blocked state
- sticky affinity to existing workflow/project
- cost/latency class where relevant

Routing output must be saved as a route decision record.

### 6. State Store

MVP can use local filesystem JSONL/Markdown under `.conductor/` or `.hermes/conductor/`.

Suggested layout:

```text
.conductor/
  conductor.json
  workflows/<workflow_id>/workflow.json
  workflows/<workflow_id>/messages/*.json
  workflows/<workflow_id>/messages/*.md
  workflows/<workflow_id>/tasks/<task_id>/task.md
  workflows/<workflow_id>/tasks/<task_id>/status.json
  workflows/<workflow_id>/tasks/<task_id>/result.md
  lanes/<escaped_lane_target>.json
  events.jsonl
```

Use SQLite later if query complexity grows. Start with append-only JSONL + atomic JSON projections for debuggability.

### 7. Verification Engine

Verification should be external to worker claims:

- run commands from task artifact when safe
- inspect changed files/diffs
- inspect result artifacts
- compare acceptance criteria
- mark evidence level
- only then advance to `complete`

## MVP Boundary

The MVP should prove a full closed loop with one workflow and two worker lanes:

1. Operator submits one goal.
2. Conductor splits into 2–3 tasks.
3. Tasks dispatch to tmux lanes.
4. Workers write result artifacts.
5. Conductor ingests results.
6. Conductor runs or requests verification.
7. Operator receives a grounded final summary.

## Design Principle

Conductor should be a **deterministic outer supervisor** over agent inner loops. The agents reason and edit; Conductor manages identity, state, routing, messaging, verification, recovery, and operator visibility.
