# Portable task and checkpoint contracts

Use [run-contract.schema.json](run-contract.schema.json) for optional structured project-owned task/checkpoint records. Human-readable [templates](../templates/) are equally usable. This is a format, not a daemon, scheduler, lock service or authority grant.

Usually one assistant owns project work. assignment_mode is manual; the source assignment is the project issue. There are no lease/heartbeat requirements. project_record_ref points to the actual project lifecycle record rather than copying that live value into Conductor or every task.

Required facts include task intent/status, exact adopted policy, owner/approval reference, environment, allowed actions, code/data/artifact identities, verification, review and a timestamped checkpoint with reporting_app and freshness. Unavailable facts must be reported, not invented. Optional task fields priority, category, parent_task_ref and owner_blocked carry the [backlog workflow](../workflows/backlog.md) dimensions; their values are project-defined. Examples are fictional with dummy hashes, example.invalid URLs and no actual authority.

Schema validation establishes shape and simple gates only. A Done record requires verification and accepted/not-required review structurally; a human/authorized reviewer must still verify truthful evidence and all task-specific acceptance, exact-head CI, merge or artifact identity. Use null execution_state when work is complete.

When interrupted, save artifacts and explicit next action. Confirm ownership transfer, current source state, access and hashes before resuming. Missing updates mean stale or unknown activity.
