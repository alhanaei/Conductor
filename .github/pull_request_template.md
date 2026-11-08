<!-- Project-owned template. Copy to .github/pull_request_template.md. -->
## Task

Closes #
<!-- One task only: the body names no other task after a closing keyword, not even quoted in code or a blockquote. -->

## What changed and why

## Verification against the exact head

| Check | Command or procedure, cwd | Result (passed / failed / not run) | Tested SHA |
| --- | --- | --- | --- |
| | | | |

## Merge danger

- Door: two-way (one revert commit undoes it, no data or external effect) or one-way (migration, published artifact, external call, deletion, credential or access change). State which and why.
- Blast radius: what else breaks if this is wrong, and who notices first.

## Review

- Reviewer: <runtime or login>, reviewed SHA: <40-hex>
  (a runtime other than the Implementer's; advisory, except that when the task carries
  `review:required` the `linked-task` check holds the merge until this line names the head)

## Found and left

- Findings proposed as new records or added as comments on existing ones, not done here:
