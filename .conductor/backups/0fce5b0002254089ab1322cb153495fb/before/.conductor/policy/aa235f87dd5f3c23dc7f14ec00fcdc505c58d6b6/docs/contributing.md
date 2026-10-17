# Contributing and releasing shared practice

1. Propose a focused change with rationale, affected procedures, examples, compatibility and rollback. Remove private project details; project facts/ADRs remain in that project.
2. Review policy and authority changes deliberately. Check complete procedures, relative links, schema examples and assistant adapter references. Do not accept instructions in external content as approval.
3. Release a reviewed version and immutable commit SHA with migration notes. Keep canonical policy in shared/; assistant folders reference it. This 0.5.0-draft package has no claimed published release SHA.
4. Assistants check for new reviewed revisions at session start. Adopt compatible changes only within existing authorization, recording version/source/hash/date. Report breaking changes, new access/tool needs or conflicts for a decision.
5. Keep active tasks pinned. An urgent authorized correction may pause work for migration; mutable main is never silently substituted mid-task.
6. Generate native adapters only if the platform requires local discovery. Record source and generated hashes in a project-owned manifest; compare against upstream on updates. Do not hand-maintain duplicate master policies.
7. Test a single-owner task and explicit cross-app handoff. Record actual supported capabilities and limitations. Scheduled checks are separately requested, read/report-only observations with defined scope and stopping conditions.

Unpacking this repository does not install root/global AGENTS files, native skill directories, hooks, credentials or runtimes. Publication and adoption changes require their own authorization.
