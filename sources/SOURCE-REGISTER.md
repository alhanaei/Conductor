# Source register

Primary references checked on 9 October 2026. Design choices in this kit are proposed practice, not claims that GitHub provides a universal controller. Actual platform capabilities and permissions require testing.

- **G1** [GitHub Projects overview](https://docs.github.com/en/issues/planning-and-tracking-with-projects/learning-about-projects/about-projects) — Fields, views and built-in automation

- **G2** [GitHub issue dependencies](https://docs.github.com/en/rest/issues/issue-dependencies) — Native dependency relationships and API

- **G3** [GitHub Apps and OAuth apps](https://docs.github.com/en/apps/oauth-apps/building-oauth-apps/differences-between-github-apps-and-oauth-apps) — Bot identity and authentication distinctions

- **G4** [Automating Projects using Actions](https://docs.github.com/en/enterprise-cloud%40latest/issues/planning-and-tracking-with-projects/automating-your-project/automating-projects-using-actions) — User and organization Project authentication

- **G6** [Deployments and environments](https://docs.github.com/en/actions/reference/workflows-and-actions/deployments-and-environments) — Plan-dependent environment protection

- **G9** [GitHub App security practices](https://docs.github.com/en/apps/creating-github-apps/about-creating-github-apps/best-practices-for-creating-a-github-app) — Narrow permissions, tokens and webhook validation

- **G10** [Required status checks](https://docs.github.com/en/pull-requests/how-tos/merge-and-close-pull-requests/troubleshooting-required-status-checks) — Current head and check source requirements

- **M1** [Media-Studio CI at inspected commit](https://github.com/alhanaei/Media-Studio/blob/e01743636f5063e6c3e79c5169082b56dee4e1ac/.github/workflows/ci.yml) — Private source; accessible with repository permission

- **M2** [Media-Studio staging at inspected commit](https://github.com/alhanaei/Media-Studio/blob/e01743636f5063e6c3e79c5169082b56dee4e1ac/.github/workflows/deploy-staging.yml) — Private source; manual staging and release contract

- **M3** [Media-Studio main branch metadata](https://api.github.com/repos/alhanaei/Media-Studio/branches/main) — Authenticated read showed classic protection; snapshot 9 October

- **P1** [Codex instructions and skills](https://learn.chatgpt.com/docs/agent-configuration/agents-md) — See ZIP for skills, long-running work and cloud sources

- **P2** [Claude Code memory and instructions](https://code.claude.com/docs/en/memory) — Version-sensitive AGENTS and CLAUDE discovery

- **P3** [Copilot instruction support](https://docs.github.com/en/copilot/reference/custom-instructions-support) — Surface differences; skill source in ZIP

- **P4** [Antigravity skills](https://www.antigravity.google/docs/skills) — Current native discovery; rules and plan sources in ZIP

- **P5** [Jules documentation](https://jules.google/docs/) — AGENTS and explicit environment setup

- **P6** [Grok Build skills](https://docs.x.ai/build/features/skills-plugins-marketplaces) — Native skills and metadata limitations

- **P7** [Kilo skills](https://kilo.ai/docs/customize/skills) — Current shared and native skill locations

- **S1** [mattpocock/skills at 49dd158](https://github.com/mattpocock/skills/tree/49dd158d1076134a641b33efb035946536778336) — MIT-licensed skill library consulted 18 October 2026; the pull request Merge danger section (#26) and the grilling and to-tickets procedures (#25) are adapted from it, not vendored

Additional provider-specific primary links and dated caveats are in the corresponding assistants/ folder. Media-Studio is a project-specific source example; its release pipeline is not a universal policy.
