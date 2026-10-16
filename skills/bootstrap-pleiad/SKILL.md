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

Before handing off an adopted repository, read its installed `AGENTS.md`, `.pleiad/config.yaml`, and CO/IM/QA/RV `.codex/agents/*.toml` contracts. Verify discovery of [role boundaries](assets/repository/docs/pleiad/role-contracts.md), [native delivery and recovery](assets/repository/docs/pleiad/coordination.md), and [resource ownership](assets/repository/docs/pleiad/resources.md); read these installed procedures to check adoption. They govern sole IM writing, independent exact-SHA QA/RV, native source binding, denial/replay recovery, and certified cleanup. Roles inherit parent permissions; the plugin grants no permissions.

Check explicit model/effort/rationale against config, and prospective issue-backed titles against its role codes and 36-character limit; truncate only the issue title with `…`, omit project name, and leave existing sessions alone. Preserve `project_name` metadata.

Initial CO instructions and IM assignments must carry verified standing owner commit/push/PR/CI/QA/review authorization, without an extra publication hold. Human merge approval and separate external-action authority remain explicit; preserve native denials.

Manifest schema 5 accepts verified schema 1/2/3/4 path sets, including 0.1.5. Adoption changes defaults for new cells only. Preserve existing checkpoints unchanged; never reopen applied events or silently convert legacy state. For existing legacy cells or an explicit top-level exception, read the installed [legacy procedure](assets/repository/docs/pleiad/legacy-coordination.md) and require `legacy-top-level` opt-in. If delivery follows adoption, use coordinate-pleiad; if a persistent project home is requested, read the installed [Captain procedure](assets/repository/docs/pleiad/captain.md).
