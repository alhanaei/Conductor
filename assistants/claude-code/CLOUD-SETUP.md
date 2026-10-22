# Cloud setup — instructions only

Claude Code has two remote modes that behave differently. A cloud session (claude.ai/code
or `claude --cloud`) runs on hosted infrastructure from a fresh clone of the repository's
remote branch. Remote Control drives a session that still runs on the local machine and
sees local files. A project (beta) coordinates many such sessions as threads; see
[Projects](#projects-beta) below. Treat each cloud environment as a separate installation.
This kit changes no saved home files, credentials, permissions or published environment.

## What reaches a cloud session

Carried over from the repository: root `CLAUDE.md`, `.claude/rules/`, `.claude/skills/`,
`.claude/agents/`, `.claude/commands/`, and repository `.claude/settings.json` hooks and
permissions in a single-repository session. Not carried over: `~/.claude/CLAUDE.md`,
personal `~/.claude/skills/`, user-scope plugins and MCP servers, and local or managed
settings files. Skills enabled on the claude.ai account load separately.

Consequences for this kit:

- The project adapter and `project-verification` skill travel with the repository once
  committed and pushed. The global adapter and `conductor-handoff` do not.
- The shared-policy snapshot must be readable inside the clone. Prefer a vendored, pinned
  copy of `shared/WORKFLOW.md` inside the repository with its digest recorded in
  `AGENTS.md`, or a cloud setup script that places the snapshot at the bound path. A
  home-directory path from the Mac does not exist remotely.
- A cloud session uses the pushed branch, not local uncommitted edits. Confirm the exact
  remote revision before relying on adapters or policy copies in that session.

## Projects (beta)

A Claude Code project is one coordinating conversation that starts a thread per task. Each
thread is a cloud session on its own branch, or, on request, a Remote Control session on the
user's computer. Docs checked 2026-10-22: [Projects](https://code.claude.com/docs/en/claude-projects).
Observed 2026-10-22 in a one-repository test project (#41); items marked "docs" are from the
documentation and were not observed. Availability is per account and plan; verify it in the
sidebar, do not assume it.

What a cloud thread starts with:

- The repository's `CLAUDE.md`, with its `@` imports (observed), `.claude/CLAUDE.md` (docs)
  and `.claude/rules/` (docs only, not observed; #41 criterion 2 was dropped on
  2026-10-22 when Projects mode was parked for Conductor work).
- Not the repository's `.claude/skills/` (observed: `conductor-project-init` and
  `project-verification` were in the clone but not in the thread's skill list), nor
  `.claude/agents/`, `.claude/commands/` or `.claude/settings.json` (docs). The
  repository-scope route below therefore does not reach project threads; use the account
  route.
- Skills enabled on the claude.ai account, claude.ai plugins and connectors (observed).
  Nothing from the user's machine.
- Standing rules that would live in `.claude/settings.json` go in project instructions, and
  variables in the cloud environment.
- Project instructions: up to 16,000 characters sent to every new thread and to the
  coordinator, set in **Project settings > Memory**, not in Git.
- Project memory: files Claude writes itself under a `MEMORY.md` index, read by every cloud
  thread at start and not by a thread on the user's computer.

How threads behave by default:

- They run in auto mode, work on a new branch from the default branch, may open a pull request
  on their own for a concrete change, and then watch it with auto-fix on whether or not
  auto-fix is on for other cloud sessions. State the pull request and merge policy in project
  instructions; the kit's [project instructions template](PROJECT-INSTRUCTIONS.template.md)
  carries Conductor's rules for this.
- A sandbox pauses between turns; if it cannot resume, the thread continues from a fresh clone
  and uncommitted changes are lost. Commit and push work in progress on long tasks.
- Threads keep running after the laptop closes, wait across plan limits and resume on their
  own, and routines can start threads on a schedule. Record that this was verified (surface,
  date, limits) in the project's installation record; the shared rule that a prompt alone
  guarantees no execution still stands.
- Threads reach GitHub through the Claude GitHub App acting as the user who owns the project
  (observed). Pull requests and comments a thread creates show that user as author (for
  example `alhanaei`, `author_association: OWNER`), and its commits carry the container's
  git identity, `Claude <noreply@anthropic.com>`. A thread has no route to a separate bot
  account such as `conductor-claude` unless the environment is given one.
- Branch protection binds a thread only when bypass is off. With `enforce_admins` off
  (observed on this repository on 2026-10-22: one required approval, two required checks,
  admins not enforced) the thread acts as the admin and could bypass every rule, and an
  author cannot approve their own pull request anyway. The owner's setting since
  2026-10-22 is "Do not allow bypassing" on and "Require approvals" off: the required
  checks (`verify`, `linked-task`) then bind every session, and merging stays the owner's
  own action, held by project instructions rather than by a review requirement.
- A cloud session already doing the work can become a project (**Continue as project**) or
  feed one (**Move to project**). A local session cannot be added; push its branch and name it
  in the task instead.

Consequences for this kit:

- Project instructions and project memory are instruction layers outside the repository,
  unversioned and unhashed. Keep policy in the pinned snapshot named in `AGENTS.md`, keep
  repository rules in `CLAUDE.md`, and record the filled project instructions (or a digest)
  in the installation record. Treat project memory as notes, never as the project record.
- The **Overview** pane is live thread state, not a backlog. Task records stay the only
  backlog; every thread starts from one, and the project's pull request check still enforces
  the link at merge.
- Boundary skills such as `project-verification` must be account skills to reach threads;
  the committed repository copies serve local and plain cloud sessions. An account skill is
  not in Git and can drift from the kit unnoticed, so record the SHA-256 of each uploaded
  skill file in the installation record, matching the kit `SHA256SUMS`.
- State "never merge, never mark a draft ready" in project instructions. Nothing else stops a
  thread acting as an admin owner.
- A project belongs to one user and cannot be shared, so a second person or another assistant
  resumes only from the repository checkpoint and the task record, as the shared handoff
  workflow already requires.

Discovery check in a project: open one thread and have it quote its loaded memory files and
its available-skills list (a thread cannot type `/context` or `/skills`), confirm the pinned
snapshot path resolves inside the clone with the recorded digest, confirm that no repository
skill is expected to load and that each account skill still matches its recorded digest, and
record the result in the installation record before sending the rest of the work.

## Making conductor-init available

Local, user scope: copy `global/skills/conductor-init/` from a pinned snapshot to
`~/.claude/skills/conductor-init/`, verify the four files against the kit `SHA256SUMS`,
record the installation project-locally, and confirm the skill in a fresh session. This
copy is invisible to cloud sessions.

Cloud sessions have no personal skills folder, so choose one of three documented routes:

1. **Account skill.** Upload the `conductor-init` folder as a skill on the claude.ai
   account. Account skills load in cloud, Cowork and signed-in terminal sessions. The
   kit's `SKILL.md` uses only `name` and `description`, which the upload accepts. The
   helper still needs a readable pinned Conductor source inside the cloud workspace.
2. **Environment setup script.** In the cloud environment's setup script, clone the
   reviewed Conductor commit to a known path, verify `MANIFEST.json` and the kit
   `SHA256SUMS`, and copy the skill into that user's `~/.claude/skills/conductor-init/`.
   The docs show setup scripts writing `~/.claude/CLAUDE.md`; skills work the same way.
   Publishing the environment is configuration work that needs its own authorization.
3. **Repository scope.** Commit the generated `conductor-project-init` (stage one output)
   under the project's `.claude/skills/` and push it. Repository skills carry over to a plain
   cloud session, which can then run stage two without any global installation. They do not
   load in a project thread (observed, #41); there, use route 1.

Whichever route is used, the generated project skill and the vendored policy snapshot
must be committed and pushed before a cloud session can see them; local uncommitted
files never reach the clone.

## Acceptance check in a new cloud session

1. Confirm actual repository identity and revision; inspect existing changes without reset.
2. Run `/context` and `/skills`; compare loaded memory files and skills with the intended
   mapping. Expect no personal skills unless the account provides them.
3. Resolve and read the pinned policy; compare its hash and source ID to the project binding.
4. Confirm `project-verification` is discovered and no confusing duplicate exists.
5. Resolve all required placeholders and identify real verification commands without
   running application code merely to install this documentation kit.
6. Record the environment identity, source binding and discovery result in the project's
   installation record. Stop dependent work on missing files or mismatches.

GitHub access must be supported and working before any remote operation; authentication
does not authorize writes. Prepare local progress drafts if posting is not authorized.
No central runtime, distributed lock service, chat migration or simultaneous assistants
are required to use this kit. Follow the canonical [shared practice](../../shared/WORKFLOW.md).
