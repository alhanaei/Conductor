# To-tickets workflow

Turn an approved outcome, a phase plan or a spec into sub-tasks on the project's task source, each sized to one assistant session and each declaring what blocks it. This workflow is the concrete form of the [lifecycle workflow](lifecycle.md)'s planning step "break outputs into tasks of at most two days" and follows the sub-task rules in the [backlog workflow](backlog.md). The project's task records are the only tracker; nothing is written to a local scratch file.

1. Start from a tracked parent. The source is a task record, a phase plan linked from one, or a spec the owner has approved; read its full body and comments. A plan that exists only in chat is recorded as a task first, per the backlog workflow's entry rule.
2. Read the area before cutting it. Inspect the code, data or documents the work touches, the project glossary if one exists, and the ADRs for that area. Name tickets in the project's vocabulary. Note any prefactoring that would make the change easy; it becomes the first ticket.
3. Draft vertical slices. Each slice cuts a narrow but complete path through every layer the outcome needs (schema, service, interface, tests, documentation), never one layer across the whole feature. A finished slice is demoable or verifiable on its own. Each slice fits a single fresh session with no carried context; a slice that needs the previous session's memory is two slices. Prefactoring slices come first.
4. Give each slice its blocking edges: the slices that must finish before it can start. A slice with no blockers can start at once. Check each edge is a real dependency, not an ordering habit.
5. Treat a wide refactor as the exception. One mechanical change whose blast radius fans across the codebase (a rename, a retype of a shared symbol) cannot land green as a vertical slice. Sequence it as expand, migrate, contract: add the new form beside the old; migrate call sites in batches sized by blast radius, each batch its own ticket blocked by the expand; delete the old form in a ticket blocked by every batch. If even the batches cannot stay green alone, they share an integration branch and all block one final integrate-and-verify ticket.
6. Confirm granularity with the owner in one grilling round ([technique](../techniques/grilling.md)): present the slices as a numbered list with title, blocked-by and what each delivers end to end; ask whether the granularity is right, whether each edge is real, and what to merge or split. Iterate until the owner approves. Delegated agents present the breakdown in their report and never file it.
7. File each approved slice as a sub-task of the parent on the project's task source, in dependency order so blockers have identifiers first. Each sub-task carries its own priority and category and the Ready facts, as the backlog workflow requires; use the platform's native blocking relationship where one exists, otherwise a Blocked by list. Do not close or edit the parent beyond linking its children; a parent that now exists only to hold them is a tracking record.
   A filed sub-task is also the unit that can be handed to a cloud coding agent (GitHub Copilot coding agent by issue assignment, Codex cloud, Claude Code on the web) when the task's authorization allows it; such an agent starts with no conversation context, so the body must stand alone: the Ready facts, the acceptance tests, the allowed paths and the stop conditions, with nothing left in chat.
8. Write for durability. Describe the behaviour the slice makes work from the user's side, not a layer-by-layer implementation list; avoid file paths and code in the ticket body, which go stale. The exception is a decision a prototype encoded more precisely than prose can (a state machine, a schema, a type shape): inline the decision-rich part and say where it came from.

Work the frontier afterwards: any sub-task whose blockers are all Done is selectable under the backlog workflow's priority rule. Filing tickets authorizes nothing; starting one follows the common workflow's Ready to In progress gate.

## Sub-task body

```markdown
## Parent
<parent task reference>

## What to build
<the end-to-end behaviour this slice makes work, from the user's side>

## Acceptance criteria
- [ ] <criterion and the test or inspection that establishes it>

## Blocked by
<references, or "None (can start immediately)"; omit when set as native edges>
```
