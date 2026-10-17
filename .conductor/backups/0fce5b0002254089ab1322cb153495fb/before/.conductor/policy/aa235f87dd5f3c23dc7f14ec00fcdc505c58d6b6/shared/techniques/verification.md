# Reusable verification techniques

## Baseline before change
Reproduce the reported behavior, record exact source/environment, and distinguish pre-existing failures from regressions. If reproduction fails, investigate rather than treating the issue description as proven.

## Evidence tied to identity
For every command record its method, exit status, tested SHA or dataset/artifact hash and log reference. Passed, failed and not run are separate outcomes. Recheck the final head after changes.

## Clean analytical rerun
Run ordered transformations from a known input snapshot in a locked environment. Validate row counts, nulls, duplicates, joins, reconciliation and metrics. Use seeds when meaningful and tolerance checks where exact determinism is unavailable. Explain uncertainty and avoid unsupported causal claims.

## Small checkpoints
At meaningful milestones and before context/quota limits, preserve approved work and record the next concrete action. Include what is shared versus local-only. Verify access and artifact integrity on resume.
