<!-- Project-owned template. Copy to .github/pull_request_template.md. -->
## Task

Closes #

## What changed and why

## Verification against the exact head

| Check | Command or procedure, cwd | Result (passed / failed / not run) | Tested SHA |
| --- | --- | --- | --- |
| | | | |

## Merge danger

- Door: two-way (one revert commit undoes it, no data or external effect) or one-way (migration, published artifact, external call, deletion, credential or access change). State which and why.
- Blast radius: what else breaks if this is wrong, and who notices first.

## Review

- Independent reviewer and reviewed SHA (advisory; merge remains the integrator's gate):

## Found and left

- Findings proposed as new records or added as comments on existing ones, not done here:
