---
name: bootstrap-pleiad
description: Bootstrap Pleiad into a software repository. Use when adopting the workflow, installing repository-native role configuration, or configuring issue-driven Codex delivery for a new project.
---

# Bootstrap Pleiad

1. Read every applicable `AGENTS.md` and inspect existing `.codex`, `.agents`, `.github`, and `docs/decisions` conventions.
2. Derive the project display name from explicit repository metadata; ask if ambiguous.
3. Run `python <plugin-root>/scripts/manage_repository.py dry-run --target <repository> --project-name "<project name>"`. Present its deterministic create, update, managed-block update, delete, preserve, unchanged, and conflict classifications.
4. Verify approval before writing; an explicit request to adopt or upgrade already authorizes the scoped conflict-free apply. Ask only when scope or authority is missing. Never replace an existing project-owned file wholesale.
5. Within the authorized scope, run the same command with `apply`, then `check`. The tool installs managed files, merges only the marked `AGENTS.md` block, preserves create-if-missing ADR files and project-owned Codex configuration, and refuses ambiguous ownership.
6. Record managed hashes in `.pleiad/managed.json`; never edit that state by hand. The applied version is updated only after a conflict-free apply.
7. Validate that standalone `.codex/agents/*.toml` roles, structured handoffs, ADR routing, durable delivery, and approved native specialist agent rules are discoverable. Report changes, preserved files, conflicts, and rollback through version control.

Bootstrap also installs the repository-native model-routing policy. Every durable handoff must explicitly pass `target_model`, `effort`, and a one-sentence `rationale`; use the deterministic matrix in `.pleiad/config.yaml` and reject implicit/default routing or invalid role/model/effort pairs.

For every new delivery session, use `#<issue number> <role code> - <issue title>` with `CO` Coordinator, `PD` Product, `AR` Architecture, `IM` Implementation, `QA` QA, `RV` Reviewer, or `KS` Knowledge Steward. The complete title is at most 36 Unicode characters. Build the prefix first; if truncation is required, truncate only the issue-title segment and end with one Unicode ellipsis `…`. Reject unknown codes and do not include `project_name`. Apply this prospectively; do not rename existing sessions unless explicitly requested. Do not create a delivery session without an authoritative issue.

Verify the managed Coordinator ownership and recovery policy in `AGENTS.md`, `docs/pleiad/coordination.md`, `docs/pleiad/role-contracts.md`, and the CO/IM/QA/RV executable contracts. Coordinator is the human-facing owner of cell progress, activation, supervision, recovery, and consolidated outcome reporting. When a persistent home task delegates an issue Coordinator, progress and outcomes stay within that coordination chain. Human authorization for the cell workflow covers scoped internal peer coordination, subject to host/tool permission requirements; the plugin grants no permissions and cannot bypass host restrictions. Human product decisions, credentials/permissions, acceptance, and merge authority remain explicit, and voluntary inspection of specialist tasks is welcome.

Coordinator uses native spawn/follow-up/wait/results for approved IM/QA/RV specialists and typed native checkpoints at meaningful boundaries; they must not ask the human to copy prompts, open peer tasks, or manually continue routine delivery. Escalate unavailable task control, unresolved delivery uncertainty, or missing authorization to Coordinator. Coordinator exhausts safe recovery within existing authority and host/tool permissions, then presents one actionable human blocker only when necessary through the coordination chain. A GitHub-reconstructible copy/paste fallback is a last-resort recovery artifact, never the normal user workflow. Preserve native role separation and independent QA/review.

Default new delivery to one durable CO with native IM/isolated QA/independent RV specialists, one IM source writer/worktree/branch and one PR. Subagents inherit parent sandbox/approvals; role files are behavioral and cannot enforce a separate read-only sandbox. Include verified standing owner commit/push/PR/CI/QA/review authorization in initial CO/IM instructions; no extra publication hold. Native denials remain binding until supported resolution; merge and external deployment authority stay explicit.

Managed manifest schema 5 recognizes verified schema 1/2/3/4 path sets, including prior 0.1.5, before adding native runtime/schema, Captain queue/role/procedure and resource ownership plus retained legacy documentation. Preserve owner modifications as conflicts. Upgrade defaults for new cells only: existing legacy checkpoints stay unchanged and require explicit legacy-top-level selection for recovery; never silently convert or reopen their applied events. Use native_cell.py for native records; legacy coordination_protocol.py remains supported only for explicit top-level operation. Keep handles local; validate role-bound exact-SHA evidence and recover before replacing agents.
