# Source and version manifest

| Field | Value |
| --- | --- |
| Kit | Conductor Codex shared-practice templates |
| Version / status | `0.2.0-draft`, uninstalled, review-branch source |
| Authored / docs checked | 2026-10-09 |
| Repository | `https://github.com/alhanaei/Conductor` |
| Checkout base | `ef9700186f8d9f64861e131d69b6f3be64546761` (does not include this kit) |
| Work branch | `codex/global-project-templates-20261009` |
| Shared policy binding | `shared/PRACTICE.md` entrypoint → root `shared/WORKFLOW.md` |
| Content integrity | `SHA256SUMS`, covering all other kit files |
| Scope | Codex adapters and reusable source templates; no active installation |

Design authority: the shared-practice direction and the included assistant-neutral
kit, version 0.4.0-draft. Its original payload is verified by the root MANIFEST.json.
The Codex templates are retained with thin references to the common workflow.
The former application/runtime material is retired to history.

Official format/discovery sources checked:

- [AGENTS.md](https://learn.chatgpt.com/docs/agent-configuration/agents-md)
- [Skills](https://learn.chatgpt.com/docs/build-skills)
- [Cloud environments](https://learn.chatgpt.com/docs/environments/cloud-environments)
`{{UPPER_SNAKE_CASE}}` marks deliberate installation-time placeholders. Global fields bind
only a policy path/hash. Project fields bind facts, evidence and commands owned by that
project. The setup example's `{{APPROVED_FULL_COMMIT_ID}}` is only usable after an approved
commit containing the kit exists. No secret values belong in these fields.

For this draft, verify `SHA256SUMS` from the kit directory using
`sha256sum -c SHA256SUMS` (Linux) or `shasum -a 256 -c SHA256SUMS` (macOS).
The digest of that checksum file can identify this reviewed artifact. After authorized
publication, record the full containing commit ID in each adopting project's
installation record. Do not insert a self-referential commit ID here or use a moving branch
as a reproducibility pin. Updating any kit file requires regenerated checksums and review.
