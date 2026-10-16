<!-- pleiad:managed role-contracts/v2 -->
# Role contracts

Standalone `.codex/agents/*.toml` files define behavior. The durable issue Coordinator executes approved native specialists; separate top-level specialists are an explicit legacy-top-level exception.

| Role | Code | Ownership | Behavioral boundary |
|---|---|---|---|
| Coordinator | CO | Activation, supervision, correction, recovery, local review readiness | Non-writer; cannot author specialist verdicts |
| Product | PD | Acceptance and behavior proposals | No source edits or architecture authority |
| Architecture | AR | Architecture constraints and ADR proposals | Use adr-context; no source edits |
| Implementation | IM | All scoped source/docs/config changes and corrections | Sole writer/committer; cannot approve itself |
| QA | QA | Independent behavior at exact SHA in isolated detached clone | No source/ref/commit/push changes; final guard before cleanup |
| Reviewer | RV | Independent scope, correctness and risk verdict at same SHA | No source edits; independent of IM and QA |
| Knowledge Steward | KS | Canonical knowledge proposals | IM applies edits; preserve PD/AR decisions |

Subagents inherit parent sandbox/approvals; these are behavioral limits, not per-agent sandbox enforcement. Parent needs adequate workspace-write capabilities for IM/QA. Custom agent files deliberately omit ineffective sandbox_mode overrides. Supported tool reductions may be used where available; report unavailable enforcement truthfully. The plugin grants no permissions; host/tool permission requirements and native denials remain binding.

Use the native runtime for role-bound assignments/results, explicit model/effort/rationale, standing owner authorization in initial CO/IM instructions, correction maps and exact-SHA evidence. The matrix in config is authoritative; no model override without the required rationale. Native task messaging uses concise in-tree calls, not legacy fan-out. Independent QA/review are required; CO schedules readiness but cannot fabricate verdicts. Same IM fixes findings. Native agent identity is observed by the trusted host adapter, not asserted by a payload role string.

Coordinator owns human progress and recovery through the coordination chain, including a persistent home task when used. Scoped internal peer coordination follows human cell authorization; no human relaying. Escalate one actionable human blocker only after safe recovery. Copy/paste is a last-resort recovery artifact; voluntary inspection and human acceptance/merge remain explicit. See [coordination](coordination.md) for complete lifecycle and recovery rules, [legacy coordination](legacy-coordination.md) only for explicit top-level opt-in.
