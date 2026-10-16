# Candidate 0.1.6: local review and pilot

This is the cumulative #26–#29 candidate, built on stable 0.1.5. No tag, release, merge, deployment or installation in another project is performed here. ADR-0001 remains **Proposed** for owner review. Exact final SHA, CI and independent QA/RV evidence are recorded on [issue #29](https://github.com/barucoh/pleiad/issues/29) and its PR; live observations are appended there after the head stabilizes, avoiding an evidence-only commit that invalidates verification.

## Review without moving primary main

Use a separate local clone. These commands create only the review directory/ref and leave the primary checkout unchanged:

```powershell
git clone --no-checkout https://github.com/barucoh/pleiad.git pleiad-candidate-review
Set-Location pleiad-candidate-review
git fetch origin codex/29-captain-migration-pilot
git switch --detach origin/codex/29-captain-migration-pilot
git rev-parse HEAD
git diff --stat origin/main...HEAD
git diff origin/main...HEAD
python scripts/validate.py
python -m unittest discover -s tests -v
python scripts/manage_repository.py check --target . --project-name Pleiad
python scripts/check_latest_release.py
npm ci
npm run validate:mermaid
python scripts/validate_hooks.py
```

Compare `HEAD` with the exact accepted SHA in the PR. A changed head requires fresh QA/RV/CI. Review the cumulative diff against main and the scoped final diff against `origin/codex/28-cell-resource-guards`. The review stack is ordinary issue PRs: #26 → #27 → #28 → #29, with each targeting its predecessor. It is not Story/integration-branch functionality. Preserve unrelated #12/PR #14.

Owner approval is required for every merge. Merge predecessors in that order; after each merge, explicitly retarget/reconcile the next PR and inspect its resulting diff/base. A squash/rebase can change ancestry: rebase only the remaining scoped slice on the approved predecessor result, then rerun required gates and exact-head independent QA/RV. Never merge merely to unblock development. The final candidate's owner-approved integration to main will trigger the existing release workflow for 0.1.6; that publication consequence must be reviewed before merging the final PR. No agent publishes or tags it in advance.

## Install and migrate in an authorized disposable fixture

Stable is 0.1.5 as observed on 2026-10-16; recheck GitHub before release decisions. Candidate manifest and applied managed state are 0.1.6, manifest schema 5. Use a candidate source pinned to the reviewed SHA for explicit development evaluation; normal projects use the latest stable release. Follow [installation](../installation.md) for the marketplace shape. Start a new session to load the intended skill/role files; a cached 0.1.4 skill is not candidate evidence.

In a clean disposable copy of a real adopted project, preserve its original identity and obtain a version-control recovery checkpoint before apply. Do not substitute this repository's `Pleiad` name for another project:

```powershell
python <candidate-root>/scripts/manage_repository.py dry-run --target <fixture> --project-name "<existing project name>"
python <candidate-root>/scripts/manage_repository.py apply --target <fixture> --project-name "<existing project name>"
python <candidate-root>/scripts/manage_repository.py check --target <fixture> --project-name "<existing project name>"
python <candidate-root>/scripts/manage_repository.py apply --target <fixture> --project-name "<existing project name>"
```

Review deterministic changes before applying within the owner-authorized scope. Any conflict stops all writes. The second apply must be a no-op. Project source, project-owned `.codex/config.toml`, existing ADRs and policy outside the managed AGENTS block are preserved. Customized managed files/block hashes are conflicts; reconcile them with the owner rather than replacing their hashes. Marker text alone is insufficient proof of ownership. The released fixture archives in `tests/fixtures/releases/` are immutable original managed bytes from 0.1.0, 0.1.3 and 0.1.5; `provenance.json` pins their commits/archive hashes. Tests verify original ledgers before upgrading. Synthetic schema-path fixtures remain separate from actual released installs.

Upgrade changes defaults for **new** cells. Existing legacy checkpoints stay unchanged. Resume those with explicit `legacy-top-level` and the retained protocol; do not load them into native mode, reset applied events or invent new cells. Rollback restores the previous tracked managed files and manifest together from the recovery checkpoint. Preserve private native/queue/resource state until reconciliation establishes what actually ran.

## Permission and hook truth

The candidate changes `.codex/hooks.json` and the repository runtime it invokes. Review and trust the exact changed project hook through `/hooks` in a new session; never auto-trust it. [Official hook guidance](https://learn.chatgpt.com/docs/hooks) says changed non-managed command definitions are skipped until human trust review. `validate_hooks.py` and direct guard subprocesses are deterministic preflight probes; they do not prove a live trusted hook fired in this session. Record actual observed tool names/coverage separately. The matcher covers `codex_app__create_thread` and `codex_app__send_message_to_thread` on supported local-function paths; specialist native spawn/follow-up/wait/results are validated by native-cell boundaries. Specialized task paths can have unverified hook coverage.

Captain generates compact `PLEIAD_CAPTAIN` envelopes after queue reservation; legacy top-level calls retain the old envelope. The hook checks shape/routing/operation, while serialized queue admission, exact recipient reconciliation and host-observed source identity remain separate. No valid JSON blob is proof of authorization or an actual native result.

[Subagents inherit parent sandbox and approvals](https://learn.chatgpt.com/docs/agent-configuration/subagents); role contracts are behavioral limits. Parent capabilities must support IM and QA work. No new policy override or custom-reviewer setting is needed. [Native approval denials remain binding](https://learn.chatgpt.com/docs/sandboxing/auto-review): do not retry through another actor/command, change policy or treat absence/timeouts as approval. The live pilot must report actual approval limitations, never manufacture a denial to claim coverage.

## Bounded live Captain exercises

Use the existing persistent project home as Captain, cap 2, with two separately authorized bounded issue CO sessions. Each durable CO is a real supported task creation, not a renamed ephemeral child. Each CO owns its native specialist tree and only its assigned IM can edit source. Standalone CO remains supported. Read-only observational pilot cells need no source branch/PR and must never claim implementation/CI/local-review readiness.

1. Persist a candidate Captain queue and its private host bindings under Git common-dir. Enqueue authoritative pilot issues with nonoverlapping ownership; reserve each sequentially before actual task creation. Persist the distinct assignment/recipient IDs, generate initial instructions and bind only native create-return sources. Show the cap/dependency/ownership refusals through automated adversarial tests and report actual live admissions separately.
2. Exercise a real independent finding, return it to the same issue IM, commit the fix with a finding-to-fix verification map, and invalidate earlier QA/RV/CI. Provision a fresh isolated detached exact-head QA clone with canonical IM ref and distinct Git common-dir. Keep its resource consumer lease through final before/after source/ref checks. Admit fresh QA and independent RV results only from their observed sources at the final SHA.
3. Persist an active CO/native assignment, actually interrupt the scoped native child through supported controls, inspect its observed state and reconcile checkpoint/results before resuming the same cell. An unknown recipient never replays an applied parent event. Missing identity/receipts or unresolved denial blocks replacement. If the host lacks durable-chat interruption, report that limitation: a real native child interruption plus same-CO recovery does not prove a top-level process crash was injected.
4. Keep actual handles/PIDs/absolute paths and raw outputs private. Publish sanitized issue/PR/SHA, logical UUIDs, role-attributed findings/results, native observation categories and limitations. Do not record model simulation as live native-tool evidence. Required acceptance remains unproven until the actual independent evidence exists.
5. Release resource leases only after each consumer's final evidence, obtain exact owner certificate, then perform supported cleanup with observed identity and record its receipt. Never delete an active or replacement clone. Missing/replaced handles or interrupted CLEANING require reconciliation; no timer-based deletion. Local preview is independent of unrelated hosting and never implies tunnel/deployment authority.

## Separately authorized Lingo pilot

Do nothing in Lingo until the owner directs it. The eventual pilot is a single bounded issue from the **existing Lingo home Captain**, preserving that home and cap 2. First install the owner-approved stable Pleiad version, start a new session, dry-run/apply/check with Lingo's existing project identity and preserve customization. Review the changed project hook manually. Reconcile any existing legacy cells explicitly; do not silently convert them or create another project home.

Then enqueue the chosen issue, reserve nonoverlapping ownership/capacity, run one IM correction if an independent finding requires it, and obtain fresh exact-SHA isolated QA/RV plus CI. Record the inherited permission boundary and any actual denial honestly. Keep the end-state at locally reviewable PRs with human acceptance/merge gates. No message, upgrade, source change, deployment, public exposure or approval-policy change in Lingo is authorized by this runbook.
