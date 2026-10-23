# Grilling: a structured interview for readiness

Grilling is how an assistant takes a record from Backlog to Ready, or a phase plan to its phase gate criteria, by interviewing the owner until nothing is silently assumed. It produces the Ready facts the [backlog workflow](../workflows/backlog.md) requires and the phase gate criteria the [lifecycle workflow](../workflows/lifecycle.md) plans backwards from. It is a technique, not an authority: the answers go to the project's task record, and the record's owner decides when the interview is done.

## The design tree and the frontier

Treat the outcome as a tree of decisions: each decision branches into the decisions that hang off it. The frontier is every decision whose prerequisites are already settled, the questions that can be asked now without guessing at answers not yet heard. Work in rounds: ask the whole frontier in one round, wait for the owner's answers, recompute the frontier, ask the next round. A question whose answer depends on another question still open in this round belongs to a later round.

## Asking a round

Number each question and give a recommended answer. Word each question so that "yes" accepts the recommendation; the owner can answer the easy ones in one word and spend attention on the rest. A question may carry several choices. State in plain text what each choice commits the project to.

```
Q1 - <question title>: <question body, with choices where there are several>
Recommended: <your recommended answer and the reason in one line>

Q2 - <question title>: ...
Recommended: ...
```

Grilling stays plain text: no platform question widget, no form. It works in every assistant and every surface (a terminal agent, Copilot Chat, a cloud agent commenting on an issue), and the owner's answers land in the record as written. On a surface that runs asynchronously, such as a cloud agent, a round is one comment on the record and the owner's reply is the next.

## Facts are the assistant's job; decisions are the owner's

When a frontier question needs a fact from the environment (a file, a command's output, a documented limit, an existing record), look it up: a search, a read, or a bounded sub-agent. Never ask the owner for anything that can be looked up. A running lookup is an unsettled prerequisite: only the questions downstream of it wait; ask the rest of the frontier now. Decisions (scope, priority, trade-offs, what is out) go to the owner, every time.

## What the tree must cover

For a task record, the frontier is empty only when every Ready fact has an answer the owner gave or accepted: bounded outcome, acceptance criteria with the test or inspection that establishes each, non-goals, dependencies, allowed paths, services and actions, data classification, environment, budget, stop conditions, plus exactly one priority and one category. For a phase plan, the frontier is empty when every phase gate criterion in the lifecycle workflow is specific to the project (the metric has a number, the contract rows name commands) and at most three risks each have an owner and a fallback.

## Ending

Grilling ends when the frontier is empty and the owner confirms a shared understanding. Write the answers to the task record or phase plan through supported authorized writes, or return them as a standard update for an authorized recorder. Do not start the work on the strength of the interview; starting follows the backlog workflow's selection step and the common workflow's status transitions; readiness itself is the owner gate Ready. There is no cap on rounds or questions; a tree that keeps growing is a sign the outcome is too large for one record, which is itself an answer to put to the owner.
