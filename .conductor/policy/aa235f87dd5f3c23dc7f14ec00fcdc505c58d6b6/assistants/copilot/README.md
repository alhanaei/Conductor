# GitHub Copilot

Setup draft only. Use [shared policy](../../shared/WORKFLOW.md); current jobs belong in project issues.

Use `.github/copilot-instructions.md` as a short repository-wide adapter. Suggested content:

    Before implementing or analyzing, read the generated native entry, <project facts path>,
    the assigned task contract, and the relevant <verified adopted workflow path> document.
    Work only within the assigned task and explicit authorization.
    Preserve existing CI and manual deployment gates. Return evidence.

Project skills can use `.agents/skills`, `.github/skills` or `.claude/skills` in current docs. Prefer the existing shared `.agents/skills` snapshot if recognized; do not create duplicate same-name skills. Copilot instruction support differs between Chat, cloud agent, review and individual IDEs. For path-specific guidance use documented `.github/instructions/*.instructions.md` files only after confirming the target surface supports them. Cloud-agent operation and its GitHub writes must fit the task's explicit authorization; GitHub integration is not permission to merge/deploy.

Sources: [skills](https://docs.github.com/en/copilot/how-tos/copilot-on-github/customize-copilot/customize-cloud-agent/add-skills), [surface support matrix](https://docs.github.com/en/copilot/reference/custom-instructions-support), [cloud agent](https://docs.github.com/en/enterprise-cloud%40latest/copilot/concepts/about-assigning-tasks-to-copilot)


## Capability and adoption record
- Documentation checked: 2026-10-09
- Actual app/surface and installed version: unverified
- Repository read capability: verify in target app
- Authorized project-record write capability: verify; otherwise use user-mediated recording
- Native instruction/skill discovery: verify in a fresh session using the documented diagnostics
- Tested/adopted practice tag and SHA: not adopted
- Last runtime verification and evidence: not performed
- Stable responsibilities: perform authorized tasks and report evidence under shared policy; no cross-provider control assumed
- Project-specific adoption and active assignment: stored only in that project
