# Conductor — Decision History

## Accepted / User-Stated

| Decision | Evidence |
|---|---|
| Project name is `Conductor` | User: "new project called Conductor" |
| It is dispatcher-style | User: "its a dispatcher style agent" |
| It runs on tmux | User: "I will run on tmux" and later clarified: "it will use Tmux" |
| It is similar to the existing Hermes dispatcher pattern | User: "similar to dispatcher" |
| It uses specific real agent CLIs as lanes | User clarified: "it will use Tmux with Claude code, Codex, Gemini, and grok" |
| It uses multiple agents and multiple tasks | User: "it will use multiple agent With multiple tasks" |
| It needs unified messaging for coordination | User: "The will use some unified messaging to coordinate the work" |
| A top-level conductor manages tasks | User: "The conducter will run on top managing all task" |

## Proposed, Not Yet Approved

| Proposal | Rationale |
|---|---|
| Python-first implementation | Aligns with existing Hermes dispatcher and local tooling |
| Local filesystem state before SQLite | Easier debugging, review, and recovery in tmux workflows |
| CLI-first MVP | Faster path to proving the control loop |
| Deterministic outer supervisor | Prevents the conductor from becoming another ungrounded agent loop |
| Verification-gated completion | Worker claims are not enough for reliable dispatch |
