# Cloud setup — instructions only

The Mac's home configuration and personal skills are not inherited by a cloud task.
Treat each environment as a separate installation. This kit changes no saved home files,
setup configuration, credentials, permissions, or published environment.

## Choose how policy reaches the task

Prefer project-root `AGENTS.md`, project `.agents/skills/`, and a reviewed vendored policy
snapshot when portability matters. Alternatively, prepare a pinned Conductor checkout or
artifact at a known readable cloud path. Fill the project binding with the path and digest;
the runtime must explicitly read it. A GitHub link alone is insufficient.

Use the source checks, merge rules, and destination mapping in [LOCAL-SETUP.md](LOCAL-SETUP.md),
with cloud paths. A cloud global adapter, if separately requested, goes in that cloud user's
Codex home, and user skills in that cloud user's `.agents/skills`. Never assume the local
username, home directory, credentials, or policy path exists remotely. Repo-scoped skills
must be available in the selected repository checkout to be discovered.

## Separate repository state from prepared environment state

A task's repository refresh and its prepared filesystem are different sources of state.
Confirm the actual project branch/HEAD, cleanliness, policy digest, and installed skill
files at task start. A refreshed repo does not prove that a cloud home snapshot is current.
An uncommitted task workspace change is not automatically a future environment installation.

For an authorized persistent environment update, prepare and test the intended files in
the environment's setup/edit flow, save the configuration, and publish or republish it.
Ask before that publication unless specifically authorized. Then start a new task and
verify discovery and digests again. Existing tasks retain their own working state.
See [official cloud environment guidance](https://learn.chatgpt.com/docs/environments/cloud-environments).

## Acceptance check in a new task

1. Confirm actual repository identity and revision; inspect existing changes without reset.
2. List loaded instruction sources, including overrides; compare with the intended mapping.
3. Resolve and read the pinned policy; compare its hash and source ID to the project binding.
4. Confirm both intended skill names and absence of confusing duplicate installations.
5. Resolve all required placeholders and identify real verification commands without running
   application code merely to install this documentation kit.
6. Record the environment identity, source binding, and discovery result in the project's
   installation record. Stop dependent work on missing files or mismatches.

GitHub access must be supported and working before any remote operation; authentication
does not authorize writes. Prepare local progress drafts if posting is not authorized.
No central runtime, distributed lock service, chat migration, or simultaneous assistants
are required to use this kit. Follow the canonical [shared practice](shared/PRACTICE.md).
