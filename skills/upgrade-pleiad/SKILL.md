---
name: upgrade-pleiad
description: Upgrade an existing repository to a newer Pleiad release. Use after updating the plugin or when repository-native Pleiad files report schema or version drift.
---

# Upgrade Pleiad

1. Read `.pleiad/config.yaml`, applicable `AGENTS.md`, and repository conventions.
2. Compare the applied schema/version with the installed plugin version.
3. Run `python <plugin-root>/scripts/manage_repository.py dry-run --target <repository> --project-name "<project name>"`. Treat its classifications as authoritative.
4. Stop on every conflict. Never overwrite project-owned content, existing ADRs, source code, or locally modified managed files whose recorded hash has drifted.
5. After approval, run the same command with `apply`, then `check`. The operation is deterministic and idempotent; recognized v0.2.0 generated agents migrate to standalone current Codex agent files and the obsolete generated role registry is removed.
6. The tool validates managed-state schema, plugin version, project identity, the complete managed path set, file hashes, and managed-block hash. It writes schema, applied plugin version, and new hashes only after a conflict-free apply. `check` must pass before completion.
7. Report changed files, deleted obsolete generated files, preserved customizations, unresolved conflicts, exact validation, and version-control rollback instructions.

The upgrade preserves and validates the repository-native model-routing policy. Every durable handoff must explicitly pass `target_model`, `effort`, and a one-sentence `rationale`; invalid role/model/effort pairs, implicit defaults, and write-capable ephemeral research are conflicts.

Existing sessions are not renamed automatically. Apply the canonical `#<issue number> <role code> - <issue title>` policy prospectively unless the user requests a one-time rename audit. Repository migration must preserve `project_name` metadata while ensuring it is absent from `session_title_format`.

Verify the managed Coordinator ownership and recovery policy in `AGENTS.md`, `docs/pleiad/coordination.md`, `docs/pleiad/role-contracts.md`, and the CO/IM/QA/RV executable contracts. Coordinator is the human-facing owner of cell progress, activation, supervision, recovery, and consolidated outcome reporting. When a persistent home task delegates an issue Coordinator, progress and outcomes stay within that coordination chain. Human authorization for the cell workflow covers scoped internal peer coordination, subject to host/tool permission requirements; the plugin grants no permissions and cannot bypass host restrictions. Human product decisions, credentials/permissions, acceptance, and merge authority remain explicit, and voluntary inspection of specialist tasks is welcome.

IM/QA/RV use native task messaging and structured handoffs for readiness, findings, corrections, and completion; they must not ask the human to copy prompts, open peer tasks, or manually continue routine delivery. Escalate unavailable task control, unresolved delivery uncertainty, or missing authorization to Coordinator. Coordinator exhausts safe recovery within existing authority and host/tool permissions, then presents one actionable human blocker only when necessary through the coordination chain. A GitHub-reconstructible copy/paste fallback is a last-resort recovery artifact, never the normal user workflow. Preserve direct peer lifecycle routes and independent QA/review.
