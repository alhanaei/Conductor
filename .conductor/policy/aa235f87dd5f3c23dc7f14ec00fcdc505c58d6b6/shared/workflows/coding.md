# Coding workflow

1. Establish the task contract, actual repository state, ownership and authorization. Read the real project’s adopted project-facts record and relevant existing instructions. Inspect implementation paths and existing tests before choosing a design.
2. Reproduce the bug or capture the baseline behavior where possible. Record pre-existing failures. For a new feature, map each acceptance criterion to a testable behavior and choose the smallest coherent implementation.
3. Use the repository's established architecture and dependency conventions. Avoid unrequested rewrites, speculative abstractions and unrelated cleanup. New dependencies need a concrete reason and must not silently introduce paid services or new access.
4. Implement in small reviewable increments. Add or update tests for behavior, negative cases, boundaries and regression paths. Protect compatibility, error handling, auth boundaries and observability as relevant.
5. Run targeted tests while iterating, then the prescribed broader checks. For UI changes, inspect real rendered behavior at relevant viewports and states; include accessibility and interaction checks. For APIs, exercise request/response contracts and failure cases. Use safe local test data.
6. Inspect the final diff, generated files, lockfile changes and unintended side effects. Verify no secrets are included. Record each check against the tested SHA or identified working-tree snapshot.
7. Save a checkpoint with completion status and next steps. If push/PR is explicitly authorized, publish only to the specified repository/branch and verify the resulting URL/SHA and required CI. Otherwise provide the local patch/artifact and ask for the exact publication action.
8. Submit the immutable implementation to a separate reviewer. Address findings within scope; obtain re-review for materially changed code. The integrator handles conflicts and re-runs combined checks after integration.
9. Stop at the task's authorized completion gate. Do not merge, release or deploy because the implementation looks good or CI is green. Preserve existing manual staging and production approvals.

On long work: maintain momentum through recoverable failures, but do not loop unchanged tests without a hypothesis. Checkpoint before expensive steps, major context loss or a usage limit. Use the handoff workflow when another agent must continue.
