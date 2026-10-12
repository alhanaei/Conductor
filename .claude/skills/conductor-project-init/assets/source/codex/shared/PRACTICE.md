# Conductor shared practice: Codex entrypoint

The assistant-neutral [shared workflow](../../shared/WORKFLOW.md) is the canonical
policy. Read it explicitly at task start, together with the relevant procedures
linked there. The [full guide](../../GUIDE.md) supplies rationale and adoption guidance.
This file is a thin compatibility entrypoint for the preserved Codex templates,
not a second policy master.

Pin a reviewed Conductor commit or verified artifact. When distributing a local
snapshot, preserve the relative layout of this entrypoint and the shared files it
references, or bind the adapters directly to the canonical shared workflow in that
same pinned snapshot. Verify the complete snapshot with the root MANIFEST.json;
checking only this entrypoint's digest does not verify its referenced policy.
Record the source revision, shared workflow digest, adapter digests and destination
mapping in the actual project's installation record. A remote URL is not loaded
automatically. Missing or mismatched policy files block dependent work.

Project plans, decisions, ownership, checkpoints, code and data remain in the real
project repository. One assistant per project is the default. Installation and
parallel work require their own authorization. Nothing in this source kit installs
instructions or skills or creates a controller or runtime.
