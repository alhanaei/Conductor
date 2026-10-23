<!-- The single Conductor policy binding for this checkout. The managed section below is written by the conductor-project-init helper (onboard and migrate); edit nothing inside its markers by hand. -->

<!-- conductor:init:begin -->
# Conductor project adapter

Read `.conductor/policy/d447a4bd747969639ce5c0d5269f5a2e6c15c8bd/shared/WORKFLOW.md` as the pinned common policy.
Policy commit: `d447a4bd747969639ce5c0d5269f5a2e6c15c8bd`; SHA-256: `7be78c359aaf6b0f7861c68b791024cca5c9d64c22b76e463b8ef69917463c83`.
Read `PROJECT.md` for project facts, verification and authoritative task links.
Verification contract: the Verification contract section in `PROJECT.md`; read its source evidence before executing checks.
Keep project lifecycle separate from task progress and execution state.
Respect Parked/Closed lifecycle and confirmed task ownership; initialization does not start work.
Checkpoint destination: `.conductor/HANDOFF.md`. Read existing checkpoints before resuming.
Verify recorded checks before reporting task completion; never infer an unrecorded command.
This adapter grants no deployment, credential, cloud, scheduling, or publication authority.
<!-- conductor:init:end -->
