---
name: upgrade-pleiad
description: Upgrade an existing repository to a newer Pleiad release. Use after updating the plugin or when repository-native Pleiad files report schema or version drift.
---

# Upgrade Pleiad

1. Read `.pleiad/config.yaml`, applicable `AGENTS.md`, and repository conventions.
2. Compare the applied schema/version with the installed plugin version.
3. Run `python <plugin-root>/scripts/manage_repository.py dry-run --target <repository> --project-name "<project name>"`. Treat its classifications as authoritative.
4. Stop on every conflict. Never overwrite project-owned content, existing ADRs, source code, or locally modified managed files whose recorded hash has drifted.
5. Within the authorized scope, run the same command with `apply`, then `check`. The operation is deterministic and idempotent; recognized v0.2.0 generated agents migrate to standalone current Codex agent files and the obsolete generated role registry is removed.
6. The tool validates managed-state schema, plugin version, project identity, the complete managed path set, file hashes, and managed-block hash. It writes schema, applied plugin version, and new hashes only after a conflict-free apply. `check` must pass before completion.
7. Report changed files, deleted obsolete generated files, preserved customizations, unresolved conflicts, exact validation, and version-control rollback instructions.

Before completing upgrade, read installed `AGENTS.md`, config, CO/IM/QA/RV contracts, [role boundaries](../bootstrap-pleiad/assets/repository/docs/pleiad/role-contracts.md), [native delivery/recovery](../bootstrap-pleiad/assets/repository/docs/pleiad/coordination.md), and [resources](../bootstrap-pleiad/assets/repository/docs/pleiad/resources.md). Verify these procedures are discoverable: sole IM writing, independent exact-SHA QA/RV, source binding, denial/replay recovery, and certified cleanup. Roles inherit parent permissions; the plugin grants no permissions.

Validate explicit model/effort/rationale against config; invalid pairs, implicit defaults and write-capable ephemeral research are conflicts. Apply issue-backed titles prospectively using config's role codes and 36-character limit; omit project name, truncate only the issue title with `…`, and do not rename existing sessions. Preserve `project_name` metadata.

Initial CO instructions and IM assignments retain verified standing owner commit/push/PR/CI/QA/review authorization without an extra publication hold. Human merge approval and separate external-action authority remain explicit; preserve native denials.

Schema 5 recognizes verified schema 1/2/3/4 path sets, including 0.1.5. Preserve owner modifications as conflicts and existing checkpoints unchanged. Defaults change for new cells only; never silently convert legacy state or reopen applied events. Existing legacy cells and explicit top-level exceptions require `legacy-top-level` opt-in and the installed [legacy procedure](../bootstrap-pleiad/assets/repository/docs/pleiad/legacy-coordination.md). For subsequent delivery use coordinate-pleiad; for a persistent project home read the installed [Captain procedure](../bootstrap-pleiad/assets/repository/docs/pleiad/captain.md).
