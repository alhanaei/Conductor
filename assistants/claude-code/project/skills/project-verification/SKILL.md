---
name: project-verification
description: Verify code or analytics changes using this project's filled verification contract and record reproducible evidence before a completion claim or handoff. Do not infer commands from other repositories or use unresolved template commands.
---

# Project verification

1. Read the active project instructions (`AGENTS.md`, imported by `CLAUDE.md`) for the
   verification contract and pinned shared practice. Confirm the project identity, changed
   scope, acceptance criteria, and evidence location. Treat this skill as a template until
   the project contract is filled and reviewed.
2. Select applicable checks from the project's verified commands, working directories,
   prerequisites, and expected results. Inspect their source scripts/configuration before
   execution. If commands or paths are missing or contain placeholders, report the exact
   gap; do not guess, install dependencies, or claim verification succeeded. Continue
   independent checks that are defined, available, and authorized.
3. Check authorization and side effects before execution. Do not let a check implicitly
   deploy, spend money, publish, modify credentials, or overwrite unrelated work. Follow
   the shared policy's authorization rules for any such action.
4. For code changes, run the appropriate focused tests and required lint/type/build checks
   from the contract. Capture command, cwd, revision, runtime, exit result, and relevant
   output. Separate existing failures from regressions when evidence supports that claim.
5. For analytics, follow the separate reproduction/reconciliation procedure in the contract.
   Record approved input identifiers and versions, retrieval time, query or script, units,
   filters, joins, missing-value rules, formulas, assumptions, runtime and seeds as relevant.
   Recompute key results and compare totals or an independent sample; record tolerances
   and discrepancies. Link safe project-local provenance and output artifacts. Passing code
   tests does not substitute for checking calculations and input provenance.
6. Save a concise evidence record at the project-defined destination: checked scope,
   commands/procedures, results, failures, skipped/unavailable checks with reasons, and
   remaining risks. Never include secret-bearing logs or restricted raw data.
7. Report passed, failed, and not-run checks separately. State what the evidence supports
   and what remains unverified. Use the project's checkpoint for the next action; do not
   publish evidence or update external issues without the required authorization.
