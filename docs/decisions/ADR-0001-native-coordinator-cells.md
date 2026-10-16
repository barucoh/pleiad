# ADR-0001: Native Coordinator delivery cells

- Status: Proposed
- Date: 2026-10-16
- Tags: coordination, agents, evidence, authorization, recovery
- Load when: Changing delivery topology, native specialist assignment/result admission, independent QA/review, or legacy recovery.

## Context

Mandatory top-level specialist chats added fragile activation, transport and recovery overhead. The owner authorized a native specialist migration while retaining role separation and host permissions. See [candidate design](../pleiad/native-delivery-design.md) and [issue #26](https://github.com/barucoh/pleiad/issues/26).

## Decision

Propose one durable issue Coordinator with native IM, isolated QA and independent RV specialists; one sole IM source writer/worktree/branch/PR. CO owns supervision and recovery; exact-SHA role-authored evidence gates local-review readiness. Standing authorization is explicit initially and in IM assignments. Human merge authority and native approval controls remain explicit.

Typed compact assignments/results/checkpoints preserve event versus recipient identity, changed-head invalidation and durable recovery. Local source bindings/receipt hashes support a trusted host adapter; they are not cryptographic enforcement. Agent/process/workspace handles stay machine-local. Legacy top-level transport is explicit opt-in with no silent checkpoint conversion. Subagents inherit parent sandbox/approvals; role contracts are behavioral.

## Consequences

Native collaboration reduces transport envelopes while retaining specialist accountability. The parent must have sufficient IM/QA capabilities; unavailable isolation/permission is surfaced honestly. CO cannot author QA/RV verdicts through supported adapter paths. Missing local receipts require native/GitHub reconciliation before reuse. Resource lifecycle and Captain admission remain separate follow-up slices. This proposal requires owner review; it is not an Active ADR yet.

## Supersedes

None.
