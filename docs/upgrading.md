# Upgrading

Pleiad upgrades have two independent layers. Pleiad is an Agentic SDLC; its new name and identifier replace the prior Agentic SDLC plugin identity.

1. Update or reinstall the plugin package from its marketplace, then start a new Codex session.
2. Invoke `upgrade-pleiad` inside each adopted repository to migrate repository-native artifacts.

A verified managed manifest from an earlier `0.1.x` release can upgrade to the current patch. The historical pre-relaunch `1.0.0` source installation is also recognized. In both cases, every recorded managed file and block hash must still match before apply; malformed versions, future versions, and drift remain conflicts.

The repository migration first reports a deterministic dry run. It updates only recognized managed files or marked managed blocks, preserves project-owned Codex configuration and create-if-missing ADR files, stops on ambiguous ownership or modified managed hashes, validates the result, and records the applied schema and plugin version only after success. Run `python <plugin-root>/scripts/manage_repository.py check --target <repository>` after apply and in drift audits.

The Pleiad 0.1.0 migration recognizes an installed `agentic-sdlc` v0.3.0 managed state, verifies every recorded legacy hash before changing it, then replaces it with Pleiad paths, markers, schema IDs, and managed hashes. It removes only verified old managed Pleiad-identity paths; a stale or modified legacy path stops as a conflict. A second apply is a no-op. It also continues to recognize canonical v0.2.0 generated agent files and removes only the exact obsolete generated `.codex/config.toml` role registry. A customized legacy registry stops as a conflict; unrelated project-owned `.codex/config.toml` content is preserved.

Plugin replacement is separate from repository migration: remove `agentic-sdlc@agentic-sdlc-public` (or use your marketplace selector), install `pleiad`, start a new session, and then dry-run `upgrade-pleiad`. Codex saved-project labels and local checkout paths are not repository-managed state; after merge, rename or re-add the saved project through the supported Codex UI for the new checkout path.

## Release policy

Pleiad relaunches at `0.1.0`. Subsequent pre-1.0 releases increment only the patch component (`0.1.1`, `0.1.2`, and so on) unless `barucoh` explicitly directs a minor or major version change.

1. Publish the Pleiad `0.1.0` plugin package after this release PR is approved and merged by `barucoh`.
2. Replace the installed `agentic-sdlc` plugin with `pleiad`, then start a new Codex session.
3. In every adopted repository, run `upgrade-pleiad` dry-run, resolve any reported managed-state conflict without overwriting custom content, then apply and check.
4. Use the supported Codex saved-project UI to point saved projects at the renamed local checkout; no repository migration changes this host state.

Existing sessions are not renamed automatically. The canonical `#<issue number> <role code> - <issue title>` policy applies prospectively unless the user explicitly requests a rename audit; repository migrations never infer or rewrite task titles.

This repository dogfoods its own releases. A release pull request must bump both the plugin manifest and repository configuration to the same version. CI accepts that explicit release-candidate state; after the owner merges it, release automation publishes the matching stable tag. Automation never receives pull-request approval or merge authority.

For local plugin development, update the local plugin source, refresh its cache-busting build metadata with the Codex plugin creator workflow, reinstall with `codex plugin add pleiad@<marketplace-name>`, and start a new session.

Coordinator is the human-facing owner of cell progress, activation, supervision, recovery, and consolidated outcome reporting. When a persistent home task delegates an issue Coordinator, progress and outcomes stay within that coordination chain. Human authorization for the cell workflow covers scoped internal peer coordination, subject to host/tool permission requirements; the plugin grants no permissions and cannot bypass host restrictions. Human product decisions, credentials/permissions, acceptance, and merge authority remain explicit, and voluntary inspection of specialist tasks is welcome.

Coordinator uses native spawn/follow-up/wait/results with role-bound native checkpoints; they must not ask the human to copy prompts, open peer tasks, or manually continue routine delivery. Escalate unavailable task control, unresolved delivery uncertainty, or missing authorization to Coordinator. Coordinator exhausts safe recovery within existing authority and host/tool permissions, then presents one actionable human blocker only when necessary through the coordination chain. A GitHub-reconstructible copy/paste fallback is a last-resort recovery artifact, never the normal user workflow. Independent QA/review remain required.

Version 0.1.5 propagates this policy through managed `AGENTS.md`, coordination and role documentation, and CO/IM/QA/RV executable contracts. Installing the plugin alone does not update existing repositories: run the released `upgrade-pleiad` dry-run, apply the conflict-free plan with existing approval, then check.

Candidate 0.1.6 advances managed manifest schema to 5. It verifies complete recorded schema 1/2/3/4 path sets, file hashes and the managed AGENTS block before adding native cells, Captain and resource ownership. Actual released 0.1.0, 0.1.3 and 0.1.5 fixture archives are covered by migration tests; older clean 0.1.x ledgers are supported by the same version/path validation. Unrecorded files with only a managed marker are ambiguous and block updates. Never regenerate hashes by hand to accept drift. Preserve custom policy outside the managed AGENTS block, project-owned Codex config, source and existing ADRs. A customized managed file needs owner-led reconciliation against the original release, not forced apply.

New cells use native specialists. Existing legacy checkpoints remain byte-for-byte unchanged and need explicit `legacy-top-level` recovery through the retained runtime/documentation. Installing a plugin does not convert existing cells. Native source bindings, Captain queue state and resource handles remain under Git common-dir; checkpoint migration is not an agent restart or a permission reset.

Role contracts are behavioral: agents inherit parent sandbox/approvals. No new approval-policy override or custom-reviewer setting is required. Preserve native denials until the host's supported resolution; a role string, timeout, fresh process or repeated command cannot resolve one. Captain's compact task envelope passes the same project hook as explicit legacy envelopes; native specialists use native-cell records rather than legacy sender tuples. See [hook coverage and human trust review](pleiad/hooks.md).

Before applying to another repository, save a clean version-control checkpoint, run the candidate dry-run with that project's identity, review every preservation/conflict, apply within the authorized scope, then check. A repeat apply must report no changes. Rollback restores the previous tracked managed files and manifest together from that checkpoint; retain running cell/receipt/resource state for reconciliation rather than deleting it. See the [local-review and pilot runbook](pleiad/migration-pilot.md) for commands and release/merge gates. This candidate performs no installation elsewhere.
