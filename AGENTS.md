<!-- The single Conductor policy binding for this checkout. The managed section below is written by the conductor-project-init helper (onboard and migrate); edit nothing inside its markers by hand. -->

<!-- conductor:init:begin -->
# Conductor project adapter

Read `.conductor/policy/2a14788454aab84a5c4dbba1fcefc7f21697f07f/shared/WORKFLOW.md` as the pinned common policy.
Policy commit: `2a14788454aab84a5c4dbba1fcefc7f21697f07f`; SHA-256: `adefbfa603a3b050593035410ce07bbb42fd27ebbfa4ba0212d48fcbe7a4a0b2`.
Read `PROJECT.md` for project facts, verification and authoritative task links.
Verification contract: the Verification contract section in `PROJECT.md`; read its source evidence before executing checks.
Keep project lifecycle separate from task progress and execution state.
Respect Parked/Closed lifecycle and confirmed task ownership; initialization does not start work.
Checkpoint destination: `.conductor/HANDOFF.md`. Read existing checkpoints before resuming.
Verify recorded checks before reporting task completion; never infer an unrecorded command.
This adapter grants no deployment, credential, cloud, scheduling, or publication authority.
<!-- conductor:init:end -->
