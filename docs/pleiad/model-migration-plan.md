# GPT-6 model migration plan

Pleiad 0.1.2 already routes Codex work to GPT-6 Astra, GPT-6.1 Sol, and GPT-6 Luna. The next migration is an evidence-based review of those routes, not a single global replacement. It covers role instructions, task dispatch, and repository bootstrap and upgrade artifacts. Pleiad makes no OpenAI API model calls, so API request migration is outside this scope.

## Model choice

OpenAI's [model selection guide](https://developers.openai.com/api/docs/guides/model-selection) positions Astra for ambiguous or demanding work, 6.1 Sol for complex work balancing capability and cost, and Luna for focused, frequent tasks. The [latest-model guide](https://developers.openai.com/api/docs/guides/latest-model) gives the same broad progression. These are starting points for Pleiad task routing, not proof that a role always needs one model. Verify exact model IDs and reasoning efforts in the Codex host before dispatch; product availability can differ from API availability.

| Workload | Current Pleiad route | Decision to validate |
| --- | --- | --- |
| Coordinator (CO) | `gpt-6-astra`, Medium; High with risk rationale | Test whether Astra improves ambiguous coordination and cross-task recovery enough to remain the default. Keep difficult CO work on Astra while gathering evidence. |
| Product (PD) and Architecture (AR) | `gpt-6.1-sol`, Medium; Astra High with risk rationale | Keep Sol for normal issue definition and design; compare Astra on ambiguous or high-risk cases. |
| Implementation (IM) | `gpt-6-luna`, Low for bounded work; `gpt-6.1-sol`, Low–High for complex work; Astra High by exception | Check that scope, code risk, and correction history drive escalation. |
| QA and Reviewer (QA, RV) | `gpt-6.1-sol`, Medium; High or Astra High with risk rationale | Verify independent defect detection before considering a cheaper route. |
| Knowledge Steward (KS) and ephemeral research | Luna Low for routine work; Sol for decisions or broader research; Astra by exception | Check ADR accuracy and source attribution. |

The current route authority is [`.pleiad/config.yaml`](../../.pleiad/config.yaml). Role contracts and bootstrap templates must agree with it. The open [configurable routing issue #12](https://github.com/barucoh/pleiad/issues/12) is separate implementation work; reconcile its merged result before changing this plan's baseline.

## Migration sequence

1. **Inventory routes.** Record every model ID and effort in `.pleiad/config.yaml`, `.codex/agents/`, coordination code, handoff schema and examples, managed docs, and bootstrap templates. Compare the installed stable plugin with repository source. Note project-owned overrides separately.
2. **Check host support.** Verify that each target Codex host exposes the selected model and effort. Confirm `gpt-6.1-sol` efforts rather than assuming API and Codex availability match. Fail visibly on an unavailable route; do not silently substitute a model.
3. **Compare representative work.** Select completed issue-backed examples spanning routine edits, complex implementation, ambiguous coordination, architecture decisions, QA, review, and ADR work. Replay comparable inputs with current and proposed routes. Record acceptance-criteria coverage, defects found or introduced, correction turns, time to a usable result, and available usage data. Keep QA and Reviewer independent of Implementation.
4. **Choose routes.** Define the quality bar before comparison. Choose the least costly route meeting it for each workload. Record where Astra adds value and when escalation is required. Document a rationale for changing the CO default or another role contract.
5. **Implement in one issue-backed delivery cell.** Update runtime policy, schema, role instructions, managed copies, bootstrap and upgrade artifacts together. Add focused route-validation tests. Run `python scripts/validate.py` and the relevant test suite; include comparison and validation evidence in the one-issue PR. Only Implementation writes, independent QA and Reviewer check, and the owner approves and merges.
6. **Roll out through a release.** For an approved routing change, use the next `0.1.x` patch release and align `.codex-plugin/plugin.json` with the repository's applied version. After release, update the plugin in adopted projects, start new Codex sessions, run `upgrade-pleiad` dry-run, resolve managed drift, apply, and check. Preserve project-owned overrides and active issue handoffs. Revert to the prior stable release if production misses the quality bar.

## Completion criteria

The migration is complete when target Codex hosts support the chosen routes, representative cases meet the recorded quality bar, managed copies match policy, validation and independent review pass, and adopted repositories report no upgrade drift. A model change without a release remains confined to its issue branch.

Review this plan when OpenAI's [model catalog](https://developers.openai.com/api/docs/models) or Codex host availability changes. Last reviewed: 2026-10-04.
