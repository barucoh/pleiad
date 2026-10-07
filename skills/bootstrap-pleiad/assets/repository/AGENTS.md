<!-- pleiad:start -->
## Pleiad

- Work from an authoritative issue in a dedicated task, branch, and worktree.
- Name new delivery sessions `#<issue number> <role code> - <issue title>` with role codes `CO`, `PD`, `AR`, `IM`, `QA`, `RV`, and `KS`; cap the full title at 36 Unicode characters by truncating only the issue title and ending it with one `…`. Reject unknown role codes.
- Use Coordinator, Product, Architecture, Implementation, QA, Reviewer, and Knowledge Steward roles through `.codex/agents/`.
- Canonical delivery topology is one issue = one delivery cell = one writable Implementation worktree/branch = one PR. The cell has distinct issue-backed user-visible Coordinator, Implementation, QA, and Reviewer tasks; only Implementation writes source or commits, while QA and Reviewer remain independent and non-authoritative.
- Coordinator owns human-facing progress, activation, supervision, recovery, and consolidated outcomes through the coordination chain. IM/QA/RV coordinate directly through native task messaging and structured handoffs; never require human prompt copying, peer activation, or routine manual continuation.
- Scoped internal coordination follows human cell authorization and host/tool permissions; the plugin grants no permissions. Escalate missing authorization, unavailable task control, or unresolved delivery uncertainty to Coordinator, who exhausts safe recovery before one necessary actionable human blocker. Copy/paste fallback is last resort; human decisions, acceptance, merge authority, and voluntary specialist inspection remain explicit.
- Ephemeral subagents are limited to bounded read-only research, discovery, documentation lookup, log analysis, and evidence gathering; they may not write files or external durable state.
- Communicate through `.pleiad/handoff.schema.json`; messages are transport only and GitHub plus committed canonical artifacts remain authoritative.
- Use `adr-context` to read `docs/decisions/INDEX.md` and load only materially relevant active ADRs.
- Corrections return to the same Implementation task with a finding-to-fix verification map. Implementation never approves its own work; QA and Reviewer remain independent.
- Keep one pull request scoped to one issue. Human merge authority remains explicit.
<!-- pleiad:end -->
