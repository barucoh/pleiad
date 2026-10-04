# GPT-6 migration and rollout

Pleiad uses three Codex models: `gpt-6-astra`, `gpt-6.1-sol`, and `gpt-6-luna`. Its runtime, managed templates, role contracts, and handoff schema adopted this family in v0.1.2. The v0.1.3 release makes the policy available to adopted repositories and completes the remaining project upgrades. There are no OpenAI API model calls in this repository.

OpenAI's [model selection guidance](https://developers.openai.com/api/docs/guides/model-selection) places Astra on demanding or ambiguous work, 6.1 Sol on complex work that balances capability and cost, and Luna on focused frequent work. The [GPT-6 migration guide](https://developers.openai.com/api/docs/guides/latest-model) lists these exact model IDs. Codex model availability and supported efforts must be checked on the target host before dispatch.

| Workload | Route |
| --- | --- |
| Coordinator (CO) | `gpt-6-astra` at Medium; High with a risk rationale |
| Product (PD) and Architecture (AR) | `gpt-6.1-sol` at Medium; Astra High for difficult work with a risk rationale |
| Implementation (IM) | `gpt-6-luna` at Low for focused work; `gpt-6.1-sol` at Low through High for complex work; Astra High by exception |
| QA and Reviewer (QA, RV) | `gpt-6.1-sol` at Medium; High or Astra High with a risk rationale |
| Knowledge Steward (KS) and ephemeral research | Luna Low for routine work; Sol for decisions or broader research; Astra by exception |

The authoritative routing matrix is [`.pleiad/config.yaml`](../../.pleiad/config.yaml). Dispatch validation in `scripts/coordination_protocol.py` rejects unsupported model IDs, including GPT-5.6, GPT-5.5, and `gpt-6-sol`. Negative tests intentionally retain those names as rejection cases. [Configurable routing issue #12](https://github.com/barucoh/pleiad/issues/12) remains separate.

## Release and project upgrade

1. Audit active route IDs in runtime policy, handoff schema, agent files, skills, managed documentation, and bootstrap templates. Keep every managed copy and self-hosted hash aligned.
2. Set the patch version in `.codex-plugin/plugin.json`, then update Pleiad's own applied version through `scripts/manage_repository.py`. Run `python scripts/validate.py`, the relevant unit tests, and CI. Include the route audit and results in the release PR.
3. After the repository owner merges the release PR, verify the matching stable GitHub release. Start a new Codex session with the new plugin version.
4. In each adopted repository, read its own `AGENTS.md`, inspect local changes, and run the released `upgrade-pleiad` dry-run. Stop on managed drift or ambiguous ownership; preserve project-owned content. Apply only a conflict-free upgrade and run `check`.
5. Deliver each repository upgrade through its own issue, worktree, branch, and PR. Verify the applied version and route IDs, and run repository-required checks before merge. Existing Codex tasks keep their current models; use the new routing for new tasks.

The release is complete when the GitHub release tag matches the plugin manifest and each adopted repository passes the managed-state check with only the three supported GPT-6 routes. For quality monitoring, compare representative future tasks on acceptance coverage, corrections, time, and usage; adjust routing through a later issue if evidence warrants it.

Last reviewed: 2026-10-04.
