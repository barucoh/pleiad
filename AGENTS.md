# Pleiad repository rules

- Work from a GitHub issue in a dedicated branch and worktree.
- Name new issue-delivery sessions `#<issue number> <role code> - <issue title>` using the canonical two-character role code and a maximum full title length of 36 Unicode characters.
- Keep each pull request scoped to one issue and include verification evidence.
- Never push directly to `main`; only `barucoh` may approve and merge.
- Run `python scripts/validate.py` before publishing changes.
- Treat `.codex-plugin/plugin.json` as the release-version authority.
- Do not change the version unless the pull request is intended to produce a release.
- Keep pre-1.0 releases on the `0.1.x` line and increment only the patch component unless `barucoh` explicitly directs a minor or major change.
- Until the first release exists, repository-source development is the documented bootstrap exception. Afterwards use the latest stable Pleiad release.

<!-- pleiad:start -->
## Pleiad

- Work from an authoritative issue in one durable Coordinator task, one writable Implementation worktree/branch, and one PR. Standalone Coordinator is supported.
- Name new durable sessions `#<issue number> <role code> - <issue title>` with `CP`, `CO`, `PD`, `AR`, `IM`, `QA`, `RV`, and `KS`; cap the full title at 36 Unicode characters by truncating only the issue title and ending with one `…`. Reject unknown codes.
- Coordinator uses native specialist subagents through `.codex/agents/` for IM, independent isolated QA, independent RV, and necessary PD/AR/KS/research. Only IM edits project files or commits; specialists return proposals to IM. Preserve others' edits. No second source writer.
- Coordinator owns human-facing progress, activation, supervision, recovery, corrections, and consolidated outcomes. Use native spawn/follow-up/wait/results in its tree; no human relaying or routine cross-chat fan-out. Native task messaging is transport, not delivery authority.
- Include scoped standing owner commit/push/PR/CI/QA/review authorization in initial CO instructions and propagate it to IM with `scripts/native_cell.py assign --instructions`. Routine issue publication needs no additional consent hold. Human merge approval after local review remains required; deployment, DNS, public exposure, secrets disclosure, and unrelated publication require separate authority. Preserve native denials until supported resolution.
- Subagents inherit parent sandbox/approvals. Role instructions are behavioral limits, never a promise of separate per-agent enforcement. Parent needs adequate IM/QA capabilities; CO remains a behavioral non-writer. The plugin grants no permissions and cannot bypass host/tool permission requirements.
- Persist typed native boundaries using `.pleiad/native-cell.schema.json`; bind independent role evidence to observed native source, assignment, generation and exact SHA. GitHub and committed canonical artifacts remain authoritative. Keep runtime agent/task/PID/workspace handles machine-local.
- Corrections return to the same IM with a finding-to-fix verification map. Changed SHA invalidates earlier QA/RV evidence. CO schedules transitions but cannot author QA/RV verdicts or approve its own delivery.
- Resume by validating the checkpoint and reconciling native/GitHub identity before replacements or uncertain dispatch. Event IDs differ from recipient IDs; unknown delivery never replays an applied parent event. Escalate unresolved uncertainty through Coordinator; copy/paste is a last-resort recovery artifact.
- Legacy top-level operation requires explicit `legacy-top-level` opt-in and the retained `.pleiad/handoff.schema.json` contract. Never silently convert a legacy checkpoint or create separate top-level specialists by default.
- Use `adr-context` for selective ADR retrieval. Human acceptance and merge authority remain explicit.
- Captain is the persistent project home for a durable issue queue; it admits COs under cap/dependencies/writable ownership, actively drives next actions and reconciles uncertain activation before retry. CP/CO is the limited durable cross-session transport; specialists stay in the CO tree. Standalone CO remains supported. Existing Captain home titles need not change per issue.
<!-- pleiad:end -->
