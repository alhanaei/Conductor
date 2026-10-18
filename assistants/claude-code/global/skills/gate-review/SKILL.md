---
name: gate-review
description: Review a project phase against its lifecycle gate (G0–G5) using the project's phase plan, checkpoint and recorded verification evidence, and return a pass / pass-with-conditions / hold decision for the project record. Do not decide G4 or G5 without a human decider.
---

# Gate review

Native Claude Code copy of the shared `gate-review` procedure in
`shared/workflows/lifecycle.md`. The shared workflow remains canonical; this file only makes
the procedure discoverable in the project.

1. Read the project `AGENTS.md`, the pinned shared practice, the phase plan for the gate
   under review and the project checkpoint. Confirm the gate (G0–G5), the phase owner, and
   a reviewer who is not the owner. If the phase plan or its gate criteria are missing,
   report the gap; do not review against criteria you infer.
2. Confirm authority: a gate review reads records and returns a decision. It does not
   push, merge, release, deploy, change access or publish evidence. Writes to the phase
   plan's gate record or the checkpoint happen only through supported authorized writes;
   otherwise return the decision as a standard update for an authorized recorder.
3. Answer the seven gate questions from the lifecycle workflow with one line of linked
   evidence each: outputs exist as artifacts; evidence is recorded, not claimed (commands,
   results, SHA); scope still matches the brief; every open risk has an owner and a
   fallback; project constraints still hold (compliance, data classification, budget,
   deadline); the next phase can start tomorrow; the checkpoint is updated.
4. Answer the gate-specific addition: G0 would stopping here be a loss; G1 could a stranger
   build the right thing from the brief; G2 does the most expensive-to-reverse decision
   have an ADR; G3 has someone outside the team used it; G4 has the rollback been executed
   once outside production; G5 can the on-call owner resolve the top failure modes from the
   runbook alone.
5. For verification evidence, use the project's filled verification contract and the
   `project-verification` skill's recorded results. Static reading of a plan is not runtime
   proof; say which checks were run and which were not.
6. Return exactly one outcome: pass; pass with conditions, each condition dated and owned;
   or hold, naming the specific failed criterion. For G0–G3 an assistant may return the
   outcome. For G4 and G5 return the evidence summary and a recommendation only; the
   decision line is written by a human decider. G4 is never waived and never passed with
   conditions.
7. Record the decision line (date, decider, outcome, conditions) in the phase plan's gate
   record and the project checkpoint, or return it for recording. Note explicitly that a
   gate outcome authorizes nothing beyond moving the project's phase state.
