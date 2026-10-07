<!-- pleiad:managed role-contracts/v1 -->
# Role contracts

The executable contracts are the standalone files in `.codex/agents/`. Each declares its inputs, outputs, terminal states, escalation conditions, forbidden actions, permission posture, and authority. The `name` field is the discovery source of truth.

| Role | Code | Owns | Permission posture | Separation boundary |
|---|---|---|---|---|
| Coordinator | CO | Human-facing progress, activation, supervision, recovery, consolidated outcomes, routing and readiness | Read-only repository | Does not implement, verify, approve, or merge |
| Product | PD | User value, behavior, acceptance criteria | Read-only | Does not decide architecture or approve delivery |
| Architecture | AR | Boundaries and architecture constraints | Read-only | Uses `adr-context`; does not implement or override ADRs |
| Implementation | IM | Scoped changes and corrections | Workspace-write in its issue worktree | Never approves or merges its own work |
| QA | QA | Independent behavioral verification | Host-provisioned isolated disposable workspace-write clone | May create test outputs, but does not modify source, commit, push, local refs, or review-approve |
| Reviewer | RV | Independent correctness and risk review | Read-only against implementation | Does not modify, self-review, or merge |
| Knowledge Steward | KS | Canonical documentation and ADR hygiene | Workspace-write in its issue worktree | Preserves Product/Architecture decision authority |

Coordinator is the human-facing owner of cell progress, activation, supervision, recovery, and consolidated outcome reporting. When a persistent home task delegates an issue Coordinator, progress and outcomes stay within that coordination chain. Human authorization for the cell workflow covers scoped internal peer coordination, subject to host/tool permission requirements; the plugin grants no permissions and cannot bypass host restrictions. Human product decisions, credentials/permissions, acceptance, and merge authority remain explicit, and voluntary inspection of specialist tasks is welcome.

IM/QA/RV use native task messaging and structured handoffs for readiness, findings, corrections, and completion; they must not ask the human to copy prompts, open peer tasks, or manually continue routine delivery. Escalate unavailable task control, unresolved delivery uncertainty, or missing authorization to Coordinator. Coordinator exhausts safe recovery within existing authority and host/tool permissions, then presents one actionable human blocker only when necessary through the coordination chain. A GitHub-reconstructible copy/paste fallback is a last-resort recovery artifact, never the normal user workflow.

The role codes are authoritative for prospective session titles. Unknown codes are invalid.

Model routing is also authoritative: Coordinator uses 6-Astra/Medium; Product and Architecture use 6.1-Sol/Medium, with 6-Astra/High for difficult work. Implementation uses 6-Luna/Low for routine work, 6.1-Sol for nontrivial work, and 6-Astra/High for difficult work. QA and Reviewer use 6.1-Sol/Medium, with 6-Astra/High for difficult work. Knowledge Steward uses 6-Luna/Low, with 6.1-Sol/Medium for decision-heavy work and 6-Astra/High for difficult work. Every handoff carries explicit Target model, Effort, and one-sentence Rationale. High effort requires a risk rationale; corrections return to the same Implementation task. Only the 6-Astra route is allowed for Coordinator.

Roles that write or make material decisions run only in issue-backed user-visible tasks. An agent file is a reusable contract, not permission to invoke that role as an ephemeral subagent. Ephemeral subagents are restricted to bounded read-only information gathering.

All roles use `.pleiad/handoff.schema.json`. Handoff and ADR algorithms are centralized in the schema, `docs/pleiad/coordination.md`, and `adr-context`, not repeated in individual role files.
