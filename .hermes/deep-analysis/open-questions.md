# Conductor — Open Questions

## Blockers Before Implementation

1. **Standalone or Hermes extension?**
   - Option A: standalone project under `/home/alhanaei/projects/Conductor`.
   - Option B: extension/refactor of existing Hermes dispatcher package.
   - Recommendation: standalone first, but borrow contracts from Hermes dispatcher.

2. **Storage namespace?**
   - `.conductor/` signals independent product identity.
   - `.hermes/conductor/` integrates with existing Hermes repo patterns.
   - Recommendation: `.conductor/` for product, with optional Hermes adapter later.

3. **Planner mode?**
   - Deterministic/manual task split first.
   - Model-assisted planner with schema validation later.
   - Recommendation: deterministic/manual first for safety and testability.

4. **Initial providers?**
   - Minimum: Claude + Codex.
   - Better MVP: Claude + Codex + Gemini.
   - Add Grok once lane adapter is robust.

5. **First UI?**
   - CLI only first.
   - TUI or web dashboard later.
   - Recommendation: CLI + Telegram summaries first.

## Design Questions

1. Should workers be allowed to message each other directly, or must all worker-to-worker coordination pass through Conductor?
2. Should Conductor own task decomposition fully, or allow a planner lane to propose a DAG that Conductor validates?
3. Should Conductor maintain project-level lane affinity/memory summaries?
4. Should the first task target existing Hermes dispatcher self-improvement or a sandbox repo?
5. What is the minimum proof Ahmed wants for task completion: tests only, diff review, runtime check, or Hermes final verification?
