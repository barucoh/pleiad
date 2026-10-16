# pleiad:managed captain-queue/v1
"""Portable Captain queue and local CP/CO transport adapter; performs no transport.

One serialized Captain owns writes. Persist a reservation BEFORE create/send, then
bind only host-observed handles. Payloads never grant platform permissions.
"""
from __future__ import annotations

import argparse
import copy
import json
import re
import sys
from pathlib import Path, PurePosixPath

from coordination_protocol import _validate_schema, validate_routing
from native_cell import AUTHORIZATION, CellError, _portable, digest, local_path as cell_local_path, rehydrate as rehydrate_cell, require, uid, validate as validate_cell

VERSION = "captain-queue/v1"
SCHEMA = Path(__file__).resolve().parents[1] / ".pleiad/captain-queue.schema.json"
TERMINAL = {"local_review_ready", "closed", "cancelled"}


def identity(queue):
    return {k: queue[k] for k in ("schema_version", "project_id", "repository")}


def entry(queue, issue):
    item = next((c for c in queue["cells"] if c["issue_number"] == issue), None)
    require(item is not None, "issue missing from durable queue")
    return item


def evidence(queue, urls):
    prefix = f"https://github.com/{queue['repository']}/"
    require(urls and all(re.fullmatch(re.escape(prefix) + r"(?:issues|pull)/[1-9]\d*(?:#[A-Za-z0-9_-]+)?", u) for u in urls), "same-repository durable issue/PR evidence required")
    _portable(urls)


def ownership(paths):
    require(paths and len(paths) == len(set(paths)), "explicit unique writable ownership required")
    for path in paths:
        require(path == "." or (path and "\\" not in path and not path.startswith("/") and not re.search(r"[:*?\[\]]", path) and all(p not in {"", ".", ".."} for p in path.split("/"))), "ownership must be canonical repository-relative paths; use . for repository-wide")


def cell_evidence(c, urls):
    require(any(u == c["issue_url"] or u.startswith(c["issue_url"] + "#") or (c["pr_url"] and (u == c["pr_url"] or u.startswith(c["pr_url"] + "#"))) for u in urls), "exact issue/PR reconciliation evidence required")


def overlap(left, right):
    # Conservative across Windows and case-sensitive hosts sharing one project.
    left, right = ([p.casefold() for p in paths] for paths in (left, right))
    return any(a == "." or b == "." or a == b or PurePosixPath(a) in PurePosixPath(b).parents or PurePosixPath(b) in PurePosixPath(a).parents for a in left for b in right)


def validate(queue):
    schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
    errors = _validate_schema(queue, schema, schema, "$")
    require(not errors, "; ".join(errors[:4]))
    _portable(queue)
    numbers = [c["issue_number"] for c in queue["cells"]]
    require(len(numbers) == len(set(numbers)), "one durable CO per issue")
    holders = [c for c in queue["cells"] if c["lease"]]
    require(len(holders) <= queue["cap"], "concurrency cap exceeded")
    for i, c in enumerate(holders):
        require(not any(overlap(c["ownership"], o["ownership"]) for o in holders[i + 1:]), "overlapping writable ownership")
    ids = []
    for c in queue["cells"]:
        ownership(c["ownership"])
        require(c["issue_url"] == f"https://github.com/{queue['repository']}/issues/{c['issue_number']}", "issue repository mismatch")
        evidence(queue, c["evidence"])
        require(c["issue_number"] not in [d["issue_number"] for d in c["dependencies"]], "self dependency")
        require(len({d["issue_number"] for d in c["dependencies"]}) == len(c["dependencies"]), "duplicate dependency")
        a = c["assignment"]
        if a:
            ids.append(a["id"])
            require(a["authorization"] == AUTHORIZATION, "initial CO standing authorization required")
            require(not validate_routing(dict(to_role="coordinator", target_model=a["model"], effort=a["effort"], rationale=a["rationale"], execution_mode="durable", sandbox_mode="read-only")), "invalid CO routing")
        require(c["state"] == "queued" or a is not None or c["state"] in {"closed", "cancelled"}, "active issue needs durable assignment")
        require(c["state"] not in {"active", "blocked"} or c["lease"], "active/blocked cell must retain capacity and ownership")
        if c["state"] in TERMINAL:
            require(not c["lease"] and not c["blocker"], "terminal cell must be quiescent and unblocked")
            require(not any(d["status"] == "unresolved" for d in c["denials"]), "native denial blocks terminal readiness")
        if c["state"] == "local_review_ready":
            require(c["progress"] and c["progress"]["state"] == "LOCAL_REVIEW_READY", "CO exact-head readiness evidence required")
        if c["progress"]:
            p = c["progress"]
            require(a and p["assignment_id"] == a["id"] and p["generation"] == a["generation"], "stale CO progress")
            evidence(queue, p["evidence"])
            require(c["cell_id"] == p["cell_id"] and c["pr_url"] == p["pr_url"] and c["sha"] == p["sha"], "sealed CO cell/PR/head identity mismatch")
        for attempt in c["attempts"]:
            ids.append(attempt["id"])
            require(a and attempt["assignment_id"] == a["id"] and attempt["generation"] <= a["generation"], "attempt assignment mismatch")
            if attempt["status"] in {"applied", "absent"}:
                evidence(queue, attempt["evidence"])
        for recovery in c["recoveries"]:
            evidence(queue, recovery["evidence"])
        for d in c["denials"]:
            evidence(queue, d["evidence"])
    require(len(ids) == len(set(ids)), "duplicate assignment/attempt identity")
    # Cycles are a configuration error, including forward references once added.
    graph = {c["issue_number"]: [d["issue_number"] for d in c["dependencies"]] for c in queue["cells"]}
    def visit(node, chain):
        require(node not in chain, "dependency cycle")
        for dep in graph.get(node, []):
            visit(dep, chain | {node})
    for node in graph:
        visit(node, set())
    return queue


def create(repository, cap=2):
    return validate(dict(schema_version=VERSION, project_id=uid(), repository=repository, cap=cap, cells=[]))


def enqueue(queue, issue_number, title, ownership_paths, *, dependencies=(), priority=0, issue_state="open", evidence_urls):
    """Import authoritative issue evidence; never recreate an existing assignment."""
    validate(queue)
    evidence(queue, evidence_urls)
    require(issue_state in {"open", "closed"}, "fresh issue state required")
    candidate = copy.deepcopy(queue)
    old = next((c for c in candidate["cells"] if c["issue_number"] == issue_number), None)
    if old:
        require(old["ownership"] == list(ownership_paths) and old["dependencies"] == list(dependencies), "ownership/dependency changes require explicit reconciliation")
        old.update(title=title, priority=priority, issue_state=issue_state, evidence=list(evidence_urls))
        # Closure does not discard live work or uncertain activation.
        if issue_state == "closed" and not old["lease"] and not old["blocker"]:
            old["state"] = "closed"
    else:
        candidate["cells"].append(dict(issue_number=issue_number, issue_url=f"https://github.com/{queue['repository']}/issues/{issue_number}", title=title,
            ownership=list(ownership_paths), dependencies=list(dependencies), priority=priority, issue_state=issue_state,
            state="closed" if issue_state == "closed" else "queued", lease=False, blocker="", reconciliation_required=False, cell_id="", pr_url="", branch="", sha="", assignment=None, progress=None, attempts=[], recoveries=[], denials=[], evidence=list(evidence_urls)))
    if entry(candidate, issue_number)["assignment"] is None:
        entry(candidate, issue_number)["reconciliation_required"] = False
    validate(candidate)
    queue.update(candidate)


def admission_blocker(queue, cell):
    if any(d["status"] == "unresolved" for d in cell["denials"]):
        return "native denial requires supported resolution"
    if cell["issue_state"] != "open":
        return "issue closed; reconcile active CO and release ownership"
    for dep in cell["dependencies"]:
        other = next((c for c in queue["cells"] if c["issue_number"] == dep["issue_number"]), None)
        allowed = {"closed"} if dep["requires"] == "closed" else {"local_review_ready", "closed"}
        if not other or other["reconciliation_required"] or other["state"] not in allowed or other["lease"]:
            return f"dependency #{dep['issue_number']} requires {dep['requires']}"
    holders = [c for c in queue["cells"] if c["lease"] and c is not cell]
    if len(holders) >= queue["cap"]:
        return "concurrency cap reached"
    for other in holders:
        if overlap(cell["ownership"], other["ownership"]):
            return f"writable ownership overlaps #{other['issue_number']}"
    return ""


def current_activation(c):
    if not c["assignment"]:
        return None
    return next((a for a in reversed(c["attempts"]) if a["kind"] == "activate" and a["generation"] == c["assignment"]["generation"]), None)


def next_actions(queue):
    """Active follow-through, not a passive poll: every cell gets an action/reason."""
    validate(queue)
    output = []
    for c in sorted(queue["cells"], key=lambda c: (-c["priority"], c["issue_number"])):
        uncertain = next((a for a in reversed(c["attempts"]) if a["status"] in {"unknown", "failed"}), None)
        if c["reconciliation_required"]:
            action, reason = "reconcile", "fresh issue/branch/PR/head and CO evidence required before readiness or dependency reuse"
        elif any(d["status"] == "unresolved" for d in c["denials"]):
            action, reason = "resolve_denial", "supported native resolution required; no retry"
        elif uncertain:
            action, reason = "reconcile", f"observe exact attempt {uncertain['id']} before retry"
        elif c["blocker"]:
            action, reason = "resolve_blocker", c["blocker"]
        elif c["lease"] and c["issue_state"] == "closed":
            action, reason = "reconcile_closed", "prove CO stopped and ownership released"
        elif c["state"] in TERMINAL:
            action, reason = "report", "local review ready; owner controls merge" if c["state"] == "local_review_ready" else c["state"]
        elif c["state"] == "queued":
            reason = admission_blocker(queue, c)
            action = "wait_dependency_or_capacity" if reason else "activate"
        elif current_activation(c) and current_activation(c)["status"] == "absent":
            action, reason = "retry_activation", "current-generation activation proven absent; retry same logical assignment"
        elif not current_activation(c) or current_activation(c)["status"] != "applied":
            action, reason = "reconcile", "current-generation applied activation required before CO continuation"
        elif c["progress"]:
            action, reason = "continue_co", c["progress"]["next_action"]
        else:
            action, reason = "inspect_co", "retrieve bound CO progress and drive its next action"
        output.append(dict(issue_number=c["issue_number"], action=action, reason=reason))
    return output


def reserve(queue, issue, objective, *, model="gpt-6-astra", effort="Medium", rationale="Coordinate independent issue work."):
    """Reserve capacity/ownership and unknown activation atomically before transport."""
    validate(queue)
    c = entry(queue, issue)
    require(c["state"] == "queued" and not c["assignment"] and not c["blocker"], "reconcile existing assignment; never create a duplicate CO")
    require(not c["reconciliation_required"], "fresh issue reconciliation required before admission")
    require(not admission_blocker(queue, c), admission_blocker(queue, c))
    candidate = copy.deepcopy(queue)
    c = entry(candidate, issue)
    c["assignment"] = dict(id=uid(), generation=0, objective=objective, model=model, effort=effort, rationale=rationale, authorization=AUTHORIZATION)
    c.update(state="active", lease=True)
    c["attempts"].append(dict(id=uid(), assignment_id=c["assignment"]["id"], generation=0, kind="activate", status="unknown", evidence=[]))
    validate(candidate)
    queue.update(candidate)
    return c["attempts"][-1]


def initial_instructions(queue, issue):
    c = entry(validate(queue), issue)
    a = c["assignment"]
    require(a, "reserve durable assignment first")
    return (f"Coordinate {c['issue_url']}; assignment {a['id']}; generation {a['generation']}. {a['objective']}\n"
        f"Model {a['model']}, effort {a['effort']}: {a['rationale']}\n{a['authorization']}\n"
        "Human project/cell authorization covers scoped CP/CO native task messaging and CO specialist collaboration, subject to host/tool permissions. "
        "This payload grants no platform permission and does not reopen a native denial. Propagate standing authority explicitly to IM. "
        "Read AGENTS.md, .pleiad/config.yaml, .codex/agents/coordinator.toml and adr-context; use coordinate-pleiad. "
        "Only IM writes source/commits. Use native independent QA/RV and exact-SHA gates. Return durable cell evidence, next action/blocker and quiescent ownership status to Captain. "
        "Keep transport handles local. No extra publication hold, recurring automation, merge or release.\n"
        f"Writable ownership: {json.dumps(c['ownership'])}; dependencies: {json.dumps(c['dependencies'])}.\n"
        f"Resume existing cell {c['cell_id'] or '(not yet created)'}; branch {c['branch']}; PR {c['pr_url']}; SHA {c['sha']}. "
        "Reconcile the original cell and applied work before replacements; never create another IM branch/PR for a recovery.")


def new_local(queue, captain_source):
    require(captain_source, "host-observed Captain identity required")
    return dict(identity=digest(identity(queue)), captain=captain_source, bindings={}, receipts={})


def local_guard(queue, local):
    require(local.get("identity") == digest(identity(queue)) and local.get("captain"), "local project identity missing/changed; reconcile before transport")


def context(c):
    return digest({k: c[k] for k in ("issue_number", "issue_url", "ownership", "dependencies", "assignment")})


def bind(queue, local, issue, source):
    """Trusted host adapter uses observed durable CO session ID, never payload role."""
    validate(queue)
    local_guard(queue, local)
    c = entry(queue, issue)
    require(c["assignment"] and source and source != local["captain"], "independent observed CO source required")
    require(source not in local.get("retired", []), "retired CO source cannot be rebound")
    key = c["assignment"]["id"]
    old = local["bindings"].get(key)
    require(not old or old == dict(source=source, context=context(c)), "reconcile existing CO binding before replacement")
    require(not any(b["source"] == source for k, b in local["bindings"].items() if k != key), "one durable CO source per issue")
    local["bindings"][key] = dict(source=source, context=context(c))


def source_guard(queue, local, c, source):
    local_guard(queue, local)
    require(local["bindings"].get(c["assignment"]["id"]) == dict(source=source, context=context(c)) and source != local["captain"], "missing/altered bound CO source; reconcile")


def reconcile(queue, local, issue, attempt_id, *, observed, evidence_urls, source=""):
    """Explicit fresh host/GitHub evidence resolves attempts, never inferred timeout."""
    validate(queue)
    local_guard(queue, local)
    evidence(queue, evidence_urls)
    require(observed in {"applied", "absent", "failed"}, "unknown delivery needs reconciliation")
    c = entry(queue, issue)
    cell_evidence(c, evidence_urls)
    a = next((a for a in c["attempts"] if a["id"] == attempt_id), None)
    require(a and a["status"] in {"unknown", "failed"}, "applied/absent attempts cannot be replayed")
    if observed == "applied":
        source_guard(queue, local, c, source)
    if observed == "absent":
        require(a["kind"] != "activate" or not local["bindings"].get(c["assignment"]["id"]), "observed CO binding proves activation; cannot repeat")
        require(not c["progress"] or a["kind"] != "activate", "observed CO progress proves activation; cannot repeat")
    a.update(status=observed, evidence=list(evidence_urls))
    local["receipts"][a["id"]] = digest(a)
    validate(queue)


def attempt(queue, issue, kind="continue"):
    """Persist send intent; activation retries reuse assignment only after absence."""
    validate(queue)
    c = entry(queue, issue)
    require(c["assignment"] and c["lease"] and not c["blocker"], "active reserved unblocked CO required")
    require(not c["reconciliation_required"], "fresh issue/CO reconciliation required before transport")
    require(not any(d["status"] == "unresolved" for d in c["denials"]), "native denial requires supported resolution")
    require(not any(a["status"] in {"unknown", "failed"} for a in c["attempts"]), "reconcile failed/unknown activation or send before another action")
    require(kind in {"activate", "continue"}, "unsupported transport action")
    if kind == "activate":
        previous = [a for a in c["attempts"] if a["kind"] == kind and a["generation"] == c["assignment"]["generation"]]
        require(previous and previous[-1]["status"] == "absent" and not c["progress"], "successful activation cannot repeat")
    else:
        require(current_activation(c) and current_activation(c)["status"] == "applied", "reconcile current-generation successful activation first")
    record = dict(id=uid(), assignment_id=c["assignment"]["id"], generation=c["assignment"]["generation"], kind=kind, status="unknown", evidence=[])
    c["attempts"].append(record)
    validate(queue)
    return record


def progress(queue, local, issue, source, cell, *, cell_local, observed_sha, observed_pr, next_action, blocker="", quiescent=False, evidence_urls):
    """Admit CO-authored, role-verified cell evidence, never synthesize verdicts as CP.

    Host supplies freshly observed GitHub head/PR and native-cell receipts.
    """
    validate(queue)
    c = entry(queue, issue)
    # Authenticate against the existing CP binding before any mutation. Once a
    # bound CO submits new evidence, every failing admission path must leave its
    # cached readiness unusable, including malformed/stale cell or receipt data.
    source_guard(queue, local, c, source)
    c["reconciliation_required"] = True
    require(current_activation(c) and current_activation(c)["status"] == "applied", "current-generation applied activation required before CO progress")
    require(not any(d["status"] == "unresolved" for d in c["denials"]), "native denial requires supported resolution")
    evidence(queue, evidence_urls)
    validate_cell(cell)
    rehydrate_cell(cell, cell_local, observed_sha=observed_sha, observed_pr=observed_pr, observed_issue_url=cell["issue_url"], observed_branch=cell["branch"])
    require(cell["repository"] == queue["repository"] and cell["issue_number"] == issue, "CO cell identity mismatch")
    require(next_action, "active supervision needs a concrete next action")
    require(not any(a["status"] in {"unknown", "failed"} for a in c["attempts"]), "reconcile transport before progress admission")
    require(c["state"] not in {"closed", "cancelled"}, "terminal cell requires explicit reopen reconciliation")
    require(not c["cell_id"] or c["cell_id"] == cell["cell_id"], "one CO cell identity per issue")
    require(not c["pr_url"] or c["pr_url"] == cell["pr_url"], "one CO PR identity per issue")
    require(not c["branch"] or c["branch"] == cell["branch"], "one CO branch identity per issue")
    if not c["lease"] and (c["sha"] != cell["sha"] or cell["state"] != "LOCAL_REVIEW_READY" or not quiescent):
        require(not admission_blocker(queue, c), "changed head needs capacity/ownership admission before continuation")
    if any(d["status"] == "unresolved" for d in cell["denials"]):
        blocker = "native denial: supported resolution required"
    candidate = copy.deepcopy(queue)
    c = entry(candidate, issue)
    record = dict(assignment_id=c["assignment"]["id"], generation=c["assignment"]["generation"], cell_id=cell["cell_id"], state=cell["state"], sha=cell["sha"], pr_url=cell["pr_url"], next_action=next_action, evidence=list(evidence_urls), cell_digest=digest(cell))
    c.update(progress=record, blocker=blocker, reconciliation_required=False, state="blocked" if blocker else "active", lease=True, cell_id=cell["cell_id"], pr_url=cell["pr_url"], branch=cell["branch"], sha=cell["sha"])
    if cell["state"] == "LOCAL_REVIEW_READY" and quiescent and not blocker:
        c.update(state="local_review_ready", lease=False)
    elif c["issue_state"] == "closed" and quiescent and not blocker:
        c.update(state="closed", lease=False)
    validate(candidate)
    queue.update(candidate)
    local["receipts"][c["assignment"]["id"]] = digest(record)


def recover(queue, local, issue, *, observed_status, evidence_urls):
    """Retire proven stopped/lost execution; no retry or denial clearance implicit."""
    validate(queue)
    local_guard(queue, local)
    c = entry(queue, issue)
    evidence(queue, evidence_urls)
    require(observed_status in {"stopped", "lost-confirmed"}, "prove old CO stopped/lost before recovery")
    require(c["assignment"] and c["lease"] and not c["blocker"], "resolve blockers/native denials through supported flow first")
    require(not c["reconciliation_required"], "fresh issue/CO reconciliation required before recovery")
    require(not any(d["status"] == "unresolved" for d in c["denials"]), "native denial requires supported resolution")
    require(not any(a["status"] in {"unknown", "failed"} for a in c["attempts"]), "reconcile pending transport before replacement")
    key = c["assignment"]["id"]
    binding = local["bindings"].get(key)
    require(binding and binding["context"] == context(c), "reconcile missing source/context before recovery")
    c["recoveries"].append(dict(generation=c["assignment"]["generation"], observed_status=observed_status, evidence=list(evidence_urls)))
    local.setdefault("retired", []).append(binding["source"])
    del local["bindings"][key]
    c["assignment"]["generation"] += 1
    c["progress"] = None
    local["receipts"].pop(key, None)
    record = dict(id=uid(), assignment_id=key, generation=c["assignment"]["generation"], kind="activate", status="unknown", evidence=[])
    c["attempts"].append(record)
    validate(queue)
    return record


def denial(queue, issue, reason, evidence_urls):
    validate(queue)
    evidence(queue, evidence_urls)
    c = entry(queue, issue)
    require(c["state"] not in TERMINAL and reason, "active denial context required")
    _portable(reason)
    record = dict(id=uid(), reason=reason, status="unresolved", evidence=list(evidence_urls))
    c["denials"].append(record)
    validate(queue)
    return record


def resolve_denial(queue, issue, denial_id, evidence_urls):
    """Host records actual supported native resolution, never a timeout/absence."""
    validate(queue)
    evidence(queue, evidence_urls)
    record = next((d for d in entry(queue, issue)["denials"] if d["id"] == denial_id), None)
    require(record and record["status"] == "unresolved", "unresolved denial required")
    record.update(status="resolved", evidence=list(evidence_urls))
    validate(queue)


def configured_cap(repository):
    path = Path(repository) / ".pleiad/config.yaml"
    if not path.exists():
        return 2
    match = re.search(r"(?m)^captain_concurrency_cap: ([1-9]\d*)$", path.read_text(encoding="utf-8"))
    require(match, "positive captain_concurrency_cap required in config")
    return int(match[1])


def rehydrate(queue, local, observations):
    """Reconstruct from durable issues/CO checkpoints plus fresh host observations.

    Observations require issue_state/issue_url for every issue, plus branch,
    sha/pr_url for every observed cell and source/cell_digest when applicable.
    Unresolved dispatches may resume only to reconcile, never to resend. Missing local state
    must be rebuilt from actual host history before this function can succeed.
    """
    validate(queue)
    # Fail closed even if a caller catches the error: stale readiness cannot
    # satisfy a dependency or be reported by next_actions. Persist these flags.
    for c in queue["cells"]:
        c["reconciliation_required"] = True
    local_guard(queue, local)
    for c in queue["cells"]:
        observed = observations.get(str(c["issue_number"]), {})
        require(observed.get("issue_url") == c["issue_url"], "fresh exact issue identity required")
        require(observed.get("issue_state") == c["issue_state"], "fresh issue state reconciliation required")
        if c["cell_id"]:
            require(all(k in observed for k in ("branch", "pr_url", "sha")), "fresh GitHub branch/PR/head required")
            require(observed["branch"] == c["branch"] and observed["pr_url"] == c["pr_url"] and observed["sha"] == c["sha"], "GitHub branch/PR/head changed; reconcile CO and reverify before reuse")
        if not c["assignment"]:
            c["reconciliation_required"] = False
            continue
        key = c["assignment"]["id"]
        applied = current_activation(c) and current_activation(c)["status"] == "applied"
        if applied:
            b = local["bindings"].get(key, {})
            source_guard(queue, local, c, b.get("source"))
            require(observed.get("source") == b["source"], "fresh exact CO transport binding required")
        for a in c["attempts"]:
            if a["status"] in {"applied", "absent", "failed"}:
                require(local["receipts"].get(a["id"]) == digest(a), "transport receipt missing/altered; reconcile")
        if c["progress"]:
            require(local["receipts"].get(key) == digest(c["progress"]) and observed.get("cell_digest") == c["progress"]["cell_digest"], "CO progress/head changed; reconcile before reuse")
        c["reconciliation_required"] = False
    return next_actions(queue)


def save(queue, path):
    validate(queue)
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(path.suffix + ".new")
    temp.write_text(json.dumps(queue, indent=2) + "\n", encoding="utf-8")
    temp.replace(path)


def local_path(repository, project_id):
    return cell_local_path(repository, project_id).parent.parent / "captains" / f"{project_id}.json"


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--checkpoint", required=True, type=Path)
    sub = parser.add_subparsers(dest="command", required=True)
    init = sub.add_parser("init")
    init.add_argument("--repository", required=True)
    init.add_argument("--cap", type=int)
    add = sub.add_parser("enqueue", help="read portable issue specification JSON")
    add.add_argument("--spec", type=Path, required=True)
    reserve_cmd = sub.add_parser("reserve")
    reserve_cmd.add_argument("--issue", type=int, required=True)
    reserve_cmd.add_argument("--objective", required=True)
    instructions = sub.add_parser("instructions")
    instructions.add_argument("--issue", type=int, required=True)
    sub.add_parser("actions")
    sub.add_parser("validate")
    args = parser.parse_args(argv)
    try:
        if args.command == "init":
            require(not args.checkpoint.exists(), "existing project checkpoint: reconcile instead of duplicating")
            queue = create(args.repository, args.cap if args.cap is not None else configured_cap(Path.cwd()))
            output = queue
        else:
            queue = validate(json.loads(args.checkpoint.read_text(encoding="utf-8")))
            if args.command == "enqueue":
                enqueue(queue, **json.loads(args.spec.read_text(encoding="utf-8")))
                output = next_actions(queue)
            elif args.command == "reserve":
                output = reserve(queue, args.issue, args.objective)
            elif args.command == "instructions":
                print(initial_instructions(queue, args.issue))
                return 0
            else:
                output = next_actions(queue)
        save(queue, args.checkpoint)
        print(json.dumps(output, indent=2))
        return 0
    except (CellError, KeyError, TypeError, OSError, json.JSONDecodeError) as exc:
        print(f"PLEIAD_CAPTAIN_INVALID: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
