@AGENTS.md

# Conductor — Claude Code project adapter

Local adapter for the Conductor checkout, installed from the reviewed Claude Code kit.
The first line imports the vendor-neutral `AGENTS.md`, which holds the project facts,
boundaries, verification contract and task limits that every assistant reads. Nothing
project-specific is restated here. Checkout-local task records are Git metadata.

## Shared practice binding

- Local shared-policy file: `/Users/dr.ahmedalhanaee/.claude/conductor/snapshots/4f849af696de2501e552afcac8109a8bee639b5a/shared/WORKFLOW.md`
- Expected SHA-256: `0a8dc78dbaaa801e6f93fcffe02dbd2e46231dddaaa7fac7c69bf259fe4ee04a`
- Conductor source revision or reviewed artifact identity: `4f849af696de2501e552afcac8109a8bee639b5a` (branch `claude/claude-code-adapter-kit-20261010`, which adds the Claude Code kit on top of the Codex adoption source `9d7743620ee23c6e2219878fea314ea47b1941b1` pinned in `AGENTS.md`; the shared policy digest is identical at both revisions)
- Read and verify that file at task start. Follow it as the canonical common workflow.
  If absent, unresolved, or inconsistent with the imported `AGENTS.md` or global guidance,
  report the mismatch and pause dependent work. Do not fetch or switch to a moving policy
  version silently.

## Claude Code specifics

- Project skill: `.claude/skills/project-verification/` runs the verification contract
  defined in `AGENTS.md`. Personal skill: `~/.claude/skills/conductor-handoff/` prepares
  the project checkpoint at `/Users/dr.ahmedalhanaee/GitHub/Conductor/.git/conductor-local/checkpoint.md`.
  The shared workflow remains usable without skill discovery.
- Same-named skills installed for Codex under `.agents/skills/` and `~/.agents/skills/`
  are pinned copies of the same source; do not edit one copy independently.
- Claude installation integrity check: `python3 /Users/dr.ahmedalhanaee/GitHub/Conductor/.git/conductor-local/claude_verify_installation.py`,
  cwd the checkout root, Python 3 standard library, expect exit 0. Evidence:
  `.git/conductor-local/claude-verification.json`. The Codex check in `AGENTS.md` remains
  separate and unchanged.
- Explicit task limits recorded in `AGENTS.md` or the checkpoint take precedence over
  inherited commit, push, worktree or delegation defaults.


<!-- conductor:init:begin -->
# Conductor Claude Code adapter

Project facts, policy binding and verification contract are in the imported `AGENTS.md` and in `PROJECT.md`; nothing is restated here.
Native skills: `.claude/skills/conductor-project-init` for setup and `.claude/skills/project-verification` for recorded checks.
Explicit task limits in `AGENTS.md` or the checkpoint take precedence over inherited commit, push, worktree or delegation defaults.
<!-- conductor:init:end -->
