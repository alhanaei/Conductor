# Project lifecycle workflow

Sits between the project lifecycle state (Active / Parked / Closed) and task status (Backlog → Done) in the [common workflow](../WORKFLOW.md). An Active project moves through seven phases; each phase is made of tasks; each phase ends at a gate. This workflow defines the phases and gates. Actual phase, gate decisions, dates and owners belong in the project's own records, never here.

## Phases and gates

| Phase | Question it answers | Required outputs | Exit gate and criteria |
| --- | --- | --- | --- |
| 1. Discover | Is the problem real and worth solving now? | Problem statement; evidence from users or data; sponsor | **G0 Go to define**: evidence linked, sponsor named, owner named |
| 2. Define | What is the smallest thing that solves it? | One-page brief; MVP in one sentence; success metric with a number; non-goals; constraints; project-facts record | **G1 Scope locked**: brief signed; project-facts record filled; verification contract names real commands |
| 3. Design | How will it work? | Architecture sketch; data model; interface contracts; ADR per major choice; test strategy; risk list with owners | **G2 Design approved**: design review held; ADRs recorded; every risk has an owner and a fallback |
| 4. Build | Does it work end to end? | Walking skeleton first, then increments; required checks green on every merge; demo each sprint | **G3 Release candidate**: MVP acceptance met; checks green; docs current; debt logged |
| 5. Verify | Is it safe to put in front of users? | Recorded verification evidence; independent review; security check; user acceptance; deployment checklist; rollback rehearsed | **G4 Go / no-go**: all evidence recorded; rollback executed once outside production; human sign-off |
| 6. Launch | Did it land? | Release note; monitoring and alerts live; first-period incident log; handover record; recorded demo | **G5 Handover**: runbook; on-call owner named; receiving team has run the verification contract; checkpoint closed |
| 7. Operate and evolve | Is it earning its keep? | Periodic metric review; debt backlog; decision to extend, park or retire | Periodic review; an extension re-enters at Discover |

Discover and Define may collapse into one phase for small internal work. Design is never collapsed into Build. G4 is never waived and never passed with conditions. An assistant may act as reviewer at G0–G3; a human signs G4 and G5.

## Planning a phase

Plan backwards from the gate: criteria first, then outputs, then tasks.

1. Copy the gate criteria to the top of the phase plan and make each specific to the project (the metric has a number; the contract rows name commands). Settle open criteria with the owner by [grilling](../techniques/grilling.md): rounds of numbered questions with recommended answers, facts looked up, decisions put to the owner.
2. List outputs, one line each, with an owner. An output without an owner is unplanned; an output no gate reads is cut.
3. Break outputs into tasks of at most two days, each sized to one assistant session, with blocking edges, using the [to-tickets workflow](to-tickets.md). Record them as sub-tasks in the project's task source under the phase's milestone.
4. Order by dependency, then by risk: the most likely failure first, while there is time to change course.
5. Size against real capacity. When tasks exceed days, cut tasks; never cut the gate.
6. Set the time-box and the demo date. The phase ends on the date; undone work is cut or carried with a stated reason.
7. Name at most three risks, each with a fallback.
8. Write the phase's first checkpoint using the [handoff template](../templates/HANDOFF.md): objective, owner, branch, plan link, next action.

Sprints inside Build follow the same routine in miniature: one-sentence goal, tasks against capacity, riskiest first, demo on the last day. Use the [phase plan template](../templates/PHASE-PLAN.md).

## Gate review

A gate is a bounded review by the phase owner and one reviewer who is not the owner. Outcomes: pass; pass with conditions (each listed, dated, owned); hold. Record the outcome, conditions and decider in the project checkpoint and task record. The [gate-review skill](../skills/gate-review/SKILL.md) wraps this procedure.

Asked at every gate:

1. Do all planned outputs exist as linked artifacts, not descriptions?
2. Is evidence recorded, not claimed? Commands run, results stored, SHA identified.
3. Does scope still match the brief? Additions and removals written down with reasons.
4. Does every open risk have an owner and a fallback?
5. Do the project's constraints still hold (compliance, data classification, budget, deadline)? Checked, not assumed.
6. Can the next phase start tomorrow? Its plan exists, owner confirmed, inputs ready.
7. Is the checkpoint updated with the decision, conditions, date and decider?

Gate-specific additions:

- G0: would stopping here be a loss? If not, stop.
- G1: could a stranger build the right thing from the brief alone?
- G2: which decision would be most expensive to reverse, and does it have an ADR?
- G3: has someone outside the team used it?
- G4: has the rollback been executed once, on purpose, outside production? Does the closing pull request's Merge danger section state the door type and blast radius, and does the rehearsal match them?
- G5: can the on-call owner resolve the top failure modes from the runbook alone?

## Boundaries

This workflow defines phases and gates, not any project's pipeline. Required checks, deployment steps and approvals come from the project's own verification contract and authority records; common policy does not impose one project's pipeline on another. A gate outcome is a recorded decision, not an authorization: push, merge, release, deployment and access changes remain separately authorized per the [common workflow](../WORKFLOW.md).
