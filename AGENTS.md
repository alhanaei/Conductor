<!-- The single Conductor policy binding for this checkout. The managed section below is written by the conductor-project-init helper (onboard and migrate); edit nothing inside its markers by hand. -->

<!-- conductor:init:begin -->
# Conductor project adapter

Read `.conductor/policy/084387daacd2bae8a307ab4671e3d4d95f135f56/shared/WORKFLOW.md` as the pinned common policy.
Policy commit: `084387daacd2bae8a307ab4671e3d4d95f135f56`; SHA-256: `539902dd4198ebd101bb0b49a4211949ab031f5b2766497213d734e175133f6c`.
Read `PROJECT.md` for project facts, verification and authoritative task links.
Verification contract: the Verification contract section in `PROJECT.md`; read its source evidence before executing checks.
Keep project lifecycle separate from task progress and execution state.
Respect Parked/Closed lifecycle and confirmed task ownership; initialization does not start work.
Checkpoint destination: `.conductor/HANDOFF.md`. Read existing checkpoints before resuming.
Verify recorded checks before reporting task completion; never infer an unrecorded command.
This adapter grants no deployment, credential, cloud, scheduling, or publication authority.
<!-- conductor:init:end -->
