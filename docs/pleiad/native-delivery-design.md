# Captain and native delivery cells — candidate design

Authoritative scope: [issue #26](https://github.com/barucoh/pleiad/issues/26). This intermediate review slice stays at plugin 0.1.5. The ADR is Proposed; acceptance, merge and any future patch release belong to the owner.

## Outcome and ownership

One persistent Captain (CP) may manage multiple durable issue Coordinators (CO). Each CO owns assignments, workspaces, native specialist activation, corrections, recovery and durable outcomes for one issue. One issue = one CO = one IM branch/worktree = one PR, normally targeting main. A standalone CO is fully supported. Separate top-level specialists are explicit isolation, long-running ownership or platform exceptions. No Story/release integration branches are introduced.

Captain owns queue, dependency readiness, concurrency admission, overlap checks, active supervision, CO recovery and consolidated local-review readiness. The Captain runtime is follow-up #27. This slice implements one cell only and does not claim multi-cell admission.

Within a cell, only IM edits source/docs/config or commits. QA independently exercises behavior in a fresh isolated detached clone; RV independently reviews the same exact commit. PD/AR/KS/research/host control are used only when necessary; their proposals go to IM. CO is a behavioral non-writer and may schedule a transition but cannot author a specialist verdict. No agent may approve its own delivery.

## Authorization and platform boundary

Verified standing owner authorization is included explicitly in initial CO instructions and propagated to IM: scoped commits, push to the authorized repository, one PR and CI plus independent QA/review are part of issue implementation. No assistant-created publication hold is added. Merge after local review requires explicit owner approval. Deployment, DNS, public exposure, secrets disclosure and unrelated publication remain outside that authority. Native denials remain binding until supported resolution; this change never edits approval policy and makes no auto_review.extra_policy claim.

[Official subagent guidance](https://learn.chatgpt.com/docs/agent-configuration/subagents) confirms inherited sandbox/approvals and that custom role files cannot replace them. Pleiad omits ineffective sandbox overrides, needs adequate parent capabilities for IM/QA, and treats role instructions as behavioral. Supported feature reductions and isolated working copies can narrow practical exposure; unavailable enforcement is reported honestly. [Official auto-review guidance](https://learn.chatgpt.com/docs/sandboxing/auto-review) remains the platform boundary. Documentation was checked on 2026-10-16; capability availability still depends on the host.

## Execution and durable records

CO uses native spawn, follow-up, wait and returned results. `scripts/native_cell.py` constructs compact assignments, specialist results and portable checkpoints against `.pleiad/native-cell.schema.json`. Every assignment has a UUID, role, generation, expected SHA, objective and explicit model/effort/rationale. Generated initial CO/IM instructions contain standing authorization. A specialist result references its assignment, role, generation, exact SHA, durable GitHub evidence, checks and findings or fixes. QA pass additionally certifies its final workspace guard. Local-review readiness requires current IM readiness, independent current QA/RV passes, green CI and resolved findings/uncertainty/denials. This is the terminal delivery outcome; there is no auto-merge action.

The trusted host adapter binds observed native source to assignment and rejects role-string impersonation, same-source independent roles, stale generation/head and replay. Local receipt digests detect edited imported records. This is not cryptographic authentication: all agents share inherited capabilities and a local operator can edit state. Admission must use native return metadata and reconcile specialist-authored GitHub evidence. CO cannot substitute its own payload through the supported adapter.

Lifecycle events and recipient attempts have separate UUIDs. An applied event remains applied even when a child delivery times out or is absent. Reconcile exact recipient identity against native/GitHub evidence before retry; absence authorizes only a new delivery attempt for existing work, not another applied transition. Native denial is a separate unresolved record and cannot be cleared by a timeout/absence.

Commit reconstructible design, constraints and schema; retain issue/PR/branch/SHA, role-attributed findings/evidence and lifecycle records at meaningful boundaries. Agent/task/PID/absolute workspace/device/tunnel handles are machine-local under the Git common directory and are never committed/publicly exposed. On restart validate checkpoint shape, immutable identities, current GitHub head/PR and native receipt/source history before reuse, replacement or resending. Missing local state calls for evidence reconciliation, not duplicate cells.

## Corrections and changed heads

QA/RV findings return to the same IM. A correction assignment advances the generation, even when the commit is unchanged, and IM supplies a complete finding-to-fix verification map. Any observed changed head invalidates prior current QA/RV and CI; retained historical records are evidence only. Re-run independent verification at the final head. Imported stale acceptance cannot satisfy LOCAL_REVIEW_READY; missing/altered receipt history cannot satisfy resume.

## Operational lifecycle and follow-ups

The agreed resource lifecycle is acquire → use → final guard/evidence → owner certificate → cleanup → cleanup receipt. A live consumer lease blocks cleanup. Private server/port/process/device/tunnel/QA-clone handles remain local. This slice preserves QA's final guard requirement and explicit host cleanup ownership. The full resource ledger/guards and temporary-demo path belong to #28.

Approved local preview starts independently of unrelated public hosting. Temporary-demo mode requires direct user scope, uncommitted patch/rollback, bounded owned restart and checks. It grants no PR publication, merge, release, public exposure or deployment authority. #29 covers migration pilot and integration evidence, not this single-cell implementation. These follow-ups are intentionally unimplemented here.

## Adoption and compatibility

Native cells are the new managed default across skills, AGENTS, executable roles, config, runtime, validator and documentation. Manifest schema 3 verifies prior schema 1/2 hashes and path sets before adding native files. Project customizations remain conflicts. Plugin version remains 0.1.5 for this review slice. Existing checkpoints are never rewritten or silently converted. Explicit legacy-top-level mode retains the original cross-chat schema, fan-out/reconciliation engine and hook boundary. Native in-tree calls do not need legacy sender tuples or giant acknowledgement envelopes.

## Evidence and acceptance

Tests exercise a full readiness/correction/recheck loop, source-role/assignment binding, exact-head invalidation, replay/unknown-recipient separation, unresolved denials, imported checkpoint recovery, private-handle rejection and prior managed-state upgrades. Required gates remain validate.py, unittest, managed check, Mermaid render and release-transition check. Independent QA/RV and real CI must pass at the final candidate SHA. No merge or release is performed by this issue.

## Lessons informing the change

The owner retrospective found useful role separation but brittle chat-per-role activation, duplicated publication approval, large handoff envelopes, fan-out replay confusion, delayed QA provisioning and cleanup racing final verification. Native specialist experiments supplied useful evidence, with independent QA and review still required. They did not establish approval bypass, automatic sandbox isolation, or guaranteed performance improvement. Clear initial authorization, mechanical records, active supervision and ownership certificates address the observed lessons without copying private workspace/session metadata.
