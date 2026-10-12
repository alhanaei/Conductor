# Reusable architecture patterns

These are decision aids, not actual project architecture. Record the project's selected option, alternatives, consequences and evidence in its own ADR.

## Separate durable records from ephemeral sessions
Use a project issue and immutable artifact references for continuity. Sessions are replaceable. Choose this when work crosses apps or exceeds one context window. Tradeoff: checkpoints must be maintained and artifact access verified. Avoid copying private chat transcripts as the work ledger.

## Reproducible analytics pipeline
Separate approved input snapshots, transformations, validation and delivered outputs. Keep dependencies and parameters explicit. Choose this for analyses that must be checked or repeated. Tradeoff: storage/retention and nondeterministic routines need clear policy. Keep raw private data in approved governed storage, with safe hashes/references in Git.

## Isolated change with explicit integration
Use a task branch/worktree, scoped change, exact-head checks and review before authorized integration. Default to one active assistant per project. Parallel exceptions need semantic-conflict review and separate workspaces; Git isolation does not isolate shared services.

## Thin native adapters
Keep shared practice canonical and generate minimal platform entry files only where discovery requires them. Record immutable source paths and hashes. Tradeoff: adapters need version-specific discovery tests; a remote link alone may not be loaded.
