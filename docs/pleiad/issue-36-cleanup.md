# Issue 36 cleanup evidence

[Issue and bounded audit](https://github.com/barucoh/pleiad/issues/36) define this behavior-preserving cleanup against released 0.1.6 (`eb8eef50800f3e5d0468a045e36e8ce24d7c34c4`). Pleiad coordinates a small number of issue cells and serialized local resource operations; this is not a throughput optimization. ADR-0001 is Proposed, not an Active decision; its native-source, independence and resource constraints agree with the issue.

The [owner's subsequent instruction](https://github.com/barucoh/pleiad/pull/37#issuecomment-6222645220) authorizes merging this cleanup and releasing 0.1.7, superseding the initial no-release scope. The current candidate changes only release metadata and this evidence wording after the reviewed cleanup; Captain handles merge/release after fresh exact-head QA/RV and CI. The 0.1.6 measurement baseline below remains historical and reproducible.

## Bounded audit and verification map

| Opportunity | Affected callers and change | Preservation evidence |
|---|---|---|
| Repeated adoption policy | Bootstrap/upgrade entrypoints retain conflict-free apply/check, managed hashes, project-owned preservation and rollback; require installed lifecycle/role/resource discovery instead of duplicating procedures. | Fresh/prior-version managed adoption, conflict/idempotence and release-fixture tests; entrypoint link/discovery test. |
| Repeated CO procedures | Coordinate entrypoint routes to installed procedures, retaining standalone topology, explicit initial CO/IM authorization and permission boundaries. | Native source/result, changed-head, correction, denial/replay tests; independent entrypoint evaluation below. |
| Role boilerplate | Seven non-CP contracts condense escalation/permissions/authority and require shared procedure discovery; each keeps its own writer/independence restrictions. | Role discovery/boundary tests, existing native independence tests and managed generation check. CP contract unchanged. |
| Duplicate UUID/digest | Resource acquisition, leases, certification, handle bindings and demos reuse native `uid`/`digest`; resource `require` and `ResourceError` remain local. | Frozen JSON wire-byte digest, UUID v4/uniqueness and ResourceError regression, plus resource transaction/cleanup suite. No transaction or exception-save code changed. |
| Hook aliases | One source-then-alias loop replaces two identical loops. | Every alias at both levels, alias collisions, top-level-over-metadata precedence, malformed values/metadata, prompt fallback and empty-dict regressions; executable hook probes. |

The first three changes remove repeated context while keeping required discovery explicit. The last two reuse existing behavior without a new abstraction. Leaving these copies would require synchronized maintenance at every site. No unrestricted re-audit was performed. Legacy runtime/imports, schemas/wire contracts, distinct event/recipient states, Captain admission, source receipts and resource locking/fsync/save-on-exception were intentionally retained. No runtime or model-cost benchmark was run. Global skills, approval policy and hook installation were outside scope.

## Measurements

UTF-8 bytes, whitespace-delimited words and physical lines are proxies, not tokens, model costs or runtime savings. Normalize CRLF to LF. Count each listed file once. Canonical managed source lives under `skills/bootstrap-pleiad/assets/repository/`; installed mirrors are counted separately. New tests and this evidence document are not production/instruction savings. Managed metadata hashes are regenerated, not a claimed reduction.

| Group | Before bytes / words / lines | After bytes / words / lines |
|---|---:|---:|
| Canonical instructions: three skills + seven role templates | 32,807 / 3,980 / 214 | 25,828 / 2,886 / 194 |
| Installed role mirrors only | 18,181 / 2,142 / 141 | 16,221 / 1,806 / 134 |
| Canonical production code: resource + hook templates | 29,094 / 2,567 / 611 | 28,790 / 2,546 / 599 |
| Installed code mirrors only | 29,094 / 2,567 / 611 | 28,790 / 2,546 / 599 |
| Bootstrap complete cold-start bundle | 53,948 / 6,572 / 423 | 51,001 / 6,122 / 415 |
| Upgrade complete cold-start bundle | 53,444 / 6,502 / 423 | 50,867 / 6,092 / 415 |
| Standalone CO complete cold-start bundle | 53,511 / 6,527 / 418 | 50,656 / 6,053 / 409 |
| Original four-file CO subset (not complete context) | 23,198 / 2,900 / 148 | 21,183 / 2,570 / 142 |

The same complete bundle includes the selected skill, AGENTS, config, plugin manifest, CO/IM/QA/RV contracts, lifecycle, role contracts, resources, ADR-routing skill and index on both sides. Representative tasks use this self-hosting repository's installed policy, including the resulting shipped policy for adoption checks. This conservative union covers adoption verification and standalone issue delivery through independent specialist activation; newly mandatory references are included in the baseline comparison too. It does not count only shortened entrypoints. The four-file audit subset differs from the earlier candidate's estimate; measurements here use the released baseline.

Conditionally loaded full references (unchanged, counted once when applicable): Captain procedure 9,774 bytes / 1,274 words; legacy procedure 9,352 / 1,193; relevant Proposed ADR-0001 2,739 / 317; native runtime plus schema 39,815 / 3,251 for mechanical implementation inspection. For this issue's ADR-relevant standalone task, complete context including the ADR is 56,250 -> 53,395 bytes and 6,844 -> 6,370 words. Runtime/schema can be executed without loading their full text; targeted command inspection is not claimed as measured full-file context. Repository-specific issue text, extra applicable AGENTS, ADRs, findings and tool output vary by task and are not a measured saving. Captain and legacy are not required for the standalone scenario. Resource procedure text is already in every complete bundle.

Reproduce the table from the repository root at the cleanup candidate (Python 3; no network):

```python
from pathlib import Path
import subprocess

base = "eb8eef50800f3e5d0468a045e36e8ce24d7c34c4"
assets = "skills/bootstrap-pleiad/assets/repository/"
names = ("bootstrap-pleiad", "upgrade-pleiad", "coordinate-pleiad")
skills = [f"skills/{n}/SKILL.md" for n in names]
roles = [f".codex/agents/{n}.toml" for n in
         ("coordinator", "implementation", "qa", "reviewer", "architecture", "product", "knowledge_steward")]
code = ["scripts/resource_guards.py", "scripts/pretool_handoff_guard.py"]
common = ["AGENTS.md", ".pleiad/config.yaml", *roles[:4],
          *[f"docs/pleiad/{n}.md" for n in ("coordination", "role-contracts", "resources")],
          ".codex-plugin/plugin.json", "skills/adr-context/SKILL.md", "docs/decisions/INDEX.md"]
groups = {"canonical instructions": skills + [assets + p for p in roles],
          "installed roles": roles, "canonical code": [assets + p for p in code],
          "installed code": code}
groups.update({n + " cold-start": [s, *common] for n, s in zip(names, skills)})
groups["four-file CO subset"] = [skills[2], roles[0], *common[6:8]]
groups.update({n + " conditional": [f"docs/pleiad/{n}.md"] for n in ("captain", "legacy-coordination")})
groups["ADR conditional"] = ["docs/decisions/ADR-0001-native-coordinator-cells.md"]
groups["native inspection"] = ["scripts/native_cell.py", ".pleiad/native-cell.schema.json"]
for label, paths in groups.items():
    counts = []
    for before in (True, False):
        texts = [(subprocess.check_output(["git", "show", base + ":" + p]).decode("utf-8")
                  if before else Path(p).read_text(encoding="utf-8")).replace("\r\n", "\n")
                 for p in dict.fromkeys(paths)]
        counts.append(tuple(sum(f(t) for t in texts) for f in
                            (lambda t: len(t.encode("utf-8")), lambda t: len(t.split()),
                             lambda t: len(t.splitlines()))))
    print(label, counts)
```

## Independent skill evaluation

Coordinator ran two independent unseeded read-only planning evaluations using realistic coordination and bootstrap/upgrade requests. The coordination evaluator discovered standalone CO, same-IM correction, independent QA/RV, initial authorization, changed-head invalidation, supported denial/unknown-recipient recovery and certified cleanup. The adoption evaluator preserved owner files and prior checkpoints, stopped on hash drift, used apply/check and scoped rollback, and discovered the installed procedures. Neither reported a guidance defect. Both loaded the shared procedures and assigned contracts; relevant ADR/native inspection and legacy recovery were conditional. These are behavioral planning evaluations, not live adoption/tool-execution pilots or token benchmarks. Local regression tests exercise actual managed adoption separately. Final independent exact-SHA QA/RV and CI are recorded on the PR by Coordinator.

The reviewed cleanup passed: `python scripts/validate.py`; full `python -m unittest discover -s tests -v` (154 tests, one platform skip); `python scripts/manage_repository.py check --target . --project-name Pleiad`; `python scripts/validate_hooks.py`; `python scripts/check_latest_release.py --latest 0.1.6`; `npm run validate:mermaid` (10 blocks); skill-creator `quick_validate.py` for all three edited skills; `git diff --check`. Git-for-Windows fixture cloning failed under sandbox access restrictions; the approved elevated full-suite rerun passed. No test was weakened to mask the host restriction. The owner-authorized 0.1.7 metadata candidate repeats the required gates; current exact-head results are recorded on PR #37.
