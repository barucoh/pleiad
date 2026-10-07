---
name: coordinate-pleiad
description: Coordinate Pleiad role work, durable issue-backed sessions, structured handoffs, correction loops, and resilient cross-task delivery. Use when routing work among Pleiad roles or recovering uncertain cross-task delivery.
---

# Coordinate Pleiad

Preserve direct peer lifecycle routes and independent QA/review; Coordinator supervision does not impersonate specialists or relay every peer event.

Coordinator is the human-facing owner of cell progress, activation, supervision, recovery, and consolidated outcome reporting. When a persistent home task delegates an issue Coordinator, progress and outcomes stay within that coordination chain. Human authorization for the cell workflow covers scoped internal peer coordination, subject to host/tool permission requirements; the plugin grants no permissions and cannot bypass host restrictions. Human product decisions, credentials/permissions, acceptance, and merge authority remain explicit, and voluntary inspection of specialist tasks is welcome.

IM/QA/RV use native task messaging and structured handoffs for readiness, findings, corrections, and completion; they must not ask the human to copy prompts, open peer tasks, or manually continue routine delivery. Escalate unavailable task control, unresolved delivery uncertainty, or missing authorization to Coordinator. Coordinator exhausts safe recovery within existing authority and host/tool permissions, then presents one actionable human blocker only when necessary through the coordination chain. A GitHub-reconstructible copy/paste fallback is a last-resort recovery artifact, never the normal user workflow.

1. Read the authoritative issue, applicable `AGENTS.md`, `.pleiad/config.yaml`, and `docs/pleiad/role-contracts.md`.
2. Route ADR discovery only through `adr-context`.
3. Classify execution before delegation:
   - Use one delivery cell per issue: one writable Implementation worktree/branch and one PR, with distinct issue-backed user-visible Coordinator, Implementation, QA, and Reviewer tasks. Only Implementation writes source or commits; QA and Reviewer are independent and non-authoritative.
   - Use an ephemeral subagent only for bounded read-only research, discovery, log analysis, documentation lookup, or evidence gathering. Require `sandbox_mode = "read-only"`, prohibit file and external-state changes, and request concise evidence.
4. Name every new durable task `#<issue number> <role code> - <issue title>` using `CO`, `PD`, `AR`, `IM`, `QA`, `RV`, or `KS`. Reject unknown codes. The complete title is at most 36 Unicode characters: build the prefix first, then if necessary truncate only the issue-title segment and end with one `…`. Do not include `project_name` or automatically rename existing sessions.
5. Create a UUID operation ID and a handoff conforming to `.pleiad/handoff.schema.json` for every cross-task action.
6. Before every issue-backed task creation call `scripts.coordination_protocol.dispatch_issue_task`; before every required cross-task send call `send_cross_task_handoff`. Both use canonical `validate_handoff`, return concise schema/lifecycle errors, and invoke the transport only after validation succeeds. Pass `target_model`, `effort`, and a one-sentence `rationale` explicitly when creating or activating every durable handoff. Use the repository-native routing matrix: 6-Astra/Medium for Coordinator; 6.1-Sol/Medium for Product, Architecture, QA, and Reviewer defaults; 6-Luna/Low for straightforward Implementation and routine Knowledge Steward work; 6.1-Sol for nontrivial Implementation; 6-Astra/High for difficult tasks with a risk rationale. Reviewer activation uses 6.1-Sol/Medium, justified 6.1-Sol/High, or justified 6-Astra/High.
7. Persist the requested outcome in an authoritative GitHub issue, PR, review comment, commit, ADR, or canonical document. A message is only an optional wake-up optimization.
8. Send any optional wake-up with a 20–30 second watchdog, defaulting to the configured 25 seconds, and retain independent state per target.
9. Treat timeout, handler failure, and delivered-but-acknowledgement-failed as `DELIVERY_UNKNOWN`, not failure. A later transport observation cannot make it retryable. Record reconciliation of the exact operation ID against the target task and GitHub before retrying; only recorded `ABSENT` permits retry. Delivered or applied operations are terminal and cannot be reopened or repeated. If reconciliation is unavailable, preserve uncertainty and stop.
10. Retain a last-resort GitHub-reconstructible copy/paste fallback containing operation ID, issue or PR URL, objective, expected output, evidence, and next owner. Never persist thread IDs.
11. Establish a native delivery cell: Coordinator binds the IM, QA, and RV user-visible tasks and their machine-local handles, then supervises rather than relays. IM sends IMPLEMENTATION_READY directly to QA and RV; QA sends QA_PASSED or QA_CHANGES_REQUESTED directly to RV and IM; RV leads verification, returns CHANGES_REQUESTED directly to the same IM, and emits DELIVERY_CELL_COMPLETED/HUMAN_MERGE_READY to Coordinator only after QA pass and clean independent review at the exact SHA.

12. Coordinator receives routine status from durable GitHub evidence, and direct peer messages are optional wake-ups. Return to Coordinator early only for BLOCKED, escalation, or DELIVERY_UNKNOWN. Reconcile the exact UUID before retrying unknown delivery; never duplicate an applied peer transition. If task control is unavailable, escalate to Coordinator with a reconstructible fallback for safe recovery.

QA runs behavioral commands in a host-provisioned isolated disposable workspace-write QA clone derived from the implementation commit. It starts detached at the exact SHA with the canonical Implementation ref present at that SHA; source mutation, commits, pushes, local ref changes, and Implementation-ref changes are forbidden. Invoke the repository QA workspace check for exact-head, ref-map, and clone-common-dir evidence. Codex host/task-control remains responsible for provisioning and removing the isolated clone; report blocked if cleanup/isolation is unavailable or drift is detected.

Use only `completed`, `changes_requested`, or `blocked` as handoff terminal states. `DELIVERY_UNKNOWN` is transport state only.
