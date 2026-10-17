@AGENTS.md

# Conductor — Claude Code project adapter

Local adapter for the Conductor checkout, installed from the reviewed Claude Code kit.
The first line imports the vendor-neutral `AGENTS.md`, which holds the project facts,
boundaries, verification contract and task limits that every assistant reads. Nothing
project-specific is restated here. Checkout-local task records are Git metadata.

## Shared practice binding

- Local shared-policy file: `/Users/dr.ahmedalhanaee/.claude/conductor/snapshots/2a14788454aab84a5c4dbba1fcefc7f21697f07f/shared/WORKFLOW.md`
- Expected SHA-256: `adefbfa603a3b050593035410ce07bbb42fd27ebbfa4ba0212d48fcbe7a4a0b2`
- Conductor source revision or reviewed artifact identity: `2a14788454aab84a5c4dbba1fcefc7f21697f07f` (merge of PR #10 on `main`; the same pin as the project adoption in `.conductor/adoption.json`, migrated from `aa235f8` on 2026-10-16. The Codex local adapter section of `AGENTS.md` still binds `9d7743620ee23c6e2219878fea314ea47b1941b1` with the previous digest `0a8dc78d…` until Codex migrates its own adapters.)
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
