# pleiad:managed native-cell/v1
"""Single Coordinator cell records and native collaboration adapter.

No network, agent spawning, Git mutation, or permission-policy changes happen here.
The host supplies the observed result source; role labels in a payload are not identity.
"""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
import re
import subprocess
import sys
from pathlib import Path
from uuid import uuid4

from coordination_protocol import _validate_schema, validate_routing

VERSION = "native-cell/v1"
AUTHORIZATION = (
    "Standing owner authorization (2026-10-15, reaffirmed 2026-10-16): requested "
    "implementation includes committing scoped changes, pushing the issue branch to this "
    "same authorized repository, creating/updating its PR, and running CI plus independent "
    "QA/review. No additional routine publication consent or assistant-created publication "
    "hold. Only merge to main waits for explicit owner approval after local review. "
    "No deployments, DNS, public exposure, secrets disclosure, unrelated publication, or "
    "permission bypass. An existing platform denial is not reopened by this authorization."
)
ROLES = {"coordinator", "implementation", "qa", "reviewer", "product", "architecture", "knowledge_steward"}
STATES = {"IMPLEMENTATION_ACTIVE", "IMPLEMENTATION_READY", "CHANGES_REQUESTED", "CORRECTION_ACTIVE", "LOCAL_REVIEW_READY"}
SHA = re.compile(r"[0-9a-f]{40}")
SCHEMA = Path(__file__).resolve().parents[1] / ".pleiad/native-cell.schema.json"


class CellError(ValueError):
    pass


def require(condition, message):
    if not condition:
        raise CellError(message)


def uid():
    return str(uuid4())


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True).encode()).hexdigest()


def identity(cell):
    return {key: cell[key] for key in ("schema_version", "cell_id", "repository", "issue_number", "issue_url", "branch")}


def verify_pr_binding(cell, local):
    """First observed nonempty PR is immutable; blank setup may be filled once."""
    sealed = local.get("pr_url", "")
    require(not sealed or sealed == cell["pr_url"], "sealed PR identity changed; reconcile without reusing evidence")
    require(sealed or not any(r["status"] in {"ready", "passed"} for r in cell["results"]), "verification PR binding missing; reconcile before reuse")


def receipt_digest(cell, record):
    return digest({"identity": identity(cell), "pr_url": cell["pr_url"] if record["status"] in {"ready", "passed"} else "", "record": record})


def _portable(value):
    """Reject local handles in records intended for GitHub or version control."""
    if isinstance(value, str):
        require(not re.search(r"(?<![A-Za-z0-9])[A-Za-z]:[\\/]|(?:^|\s)/(?:Users|home|tmp|private|var)/", value) and not value.startswith("\\\\"), "private absolute path in durable record")
    if isinstance(value, dict):
        require(not ({"agent_id", "thread_id", "pid", "workspace_path", "port", "process_handle"} & set(value)), "machine-local handle in durable record")
        for child in value.values():
            _portable(child)
    elif isinstance(value, list):
        for child in value:
            _portable(child)


def _current_results(cell):
    return {r["role"]: r for r in cell["results"] if r["generation"] == cell["generation"] and r["sha"] == cell["sha"]}


def validate(cell):
    schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
    errors = _validate_schema(cell, schema, schema, "$")
    require(not errors, "; ".join(errors[:4]))
    _portable(cell)
    prefix = "https://github.com/" + cell["repository"]
    require(re.fullmatch(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+", cell["repository"]), "invalid repository")
    require(cell["issue_url"] == f"{prefix}/issues/{cell['issue_number']}", "issue identity mismatch")
    require(not cell["pr_url"] or re.fullmatch(re.escape(prefix) + r"/pull/[1-9]\d*", cell["pr_url"]), "PR repository mismatch")
    require(cell["branch"] != "main" and cell["branch"].strip(), "dedicated issue branch required")
    ids = []
    assignments = {a["id"]: a for a in cell["assignments"]}
    for a in cell["assignments"]:
        ids.append(a["id"])
        require(a["generation"] <= cell["generation"], "future assignment generation")
        require(not validate_routing({"to_role": a["role"], "target_model": a["model"], "effort": a["effort"], "rationale": a["rationale"], "execution_mode": "durable", "sandbox_mode": "workspace-write" if a["role"] in {"implementation", "qa", "knowledge_steward"} else "read-only"}), "invalid assignment routing")
        require(a["authorization"] == (AUTHORIZATION if a["role"] in {"coordinator", "implementation"} else ""), "initial CO/IM standing authorization required")
    seen_assignments = set()
    for r in cell["results"]:
        ids.append(r["id"])
        a = assignments.get(r["assignment_id"])
        require(a is not None and a["role"] == r["role"] and a["generation"] == r["generation"], "result is not role/assignment/generation bound")
        require(r["assignment_id"] not in seen_assignments, "assignment result replay")
        seen_assignments.add(r["assignment_id"])
        require(r["role"] != "coordinator", "Coordinator cannot author specialist verdicts")
        allowed = {"implementation": {"ready", "blocked"}, "qa": {"passed", "changes_requested", "blocked"}, "reviewer": {"passed", "changes_requested", "blocked"}}
        require(r["status"] in allowed.get(r["role"], {"completed", "blocked"}), "result status violates role authority")
        require(r["role"] == "implementation" or a["sha"] == r["sha"], "stale specialist evidence")
        require(bool(r["evidence"]), "durable specialist evidence required")
        require(all(url.startswith(prefix + "/") for url in r["evidence"]), "specialist evidence must belong to the authorized repository")
        if r["status"] == "passed":
            require(r["role"] in {"qa", "reviewer"}, "only QA/RV issue verification verdicts")
            require(not r["findings"] and r["checks"] and all(c["status"] == "passed" for c in r["checks"]), "pass requires checks and no findings")
            if r["role"] == "qa":
                require(r["final_guard"] is True, "QA final guard required before pass")
    require(len(ids) == len(set(ids)), "assignment/result UUID reused")
    event_ids = [e["id"] for e in cell["events"]]
    require(len(event_ids) == len(set(event_ids)), "applied lifecycle event replay")
    boundaries = [(e["kind"], e["generation"]) for e in cell["events"] if e["kind"] == "local_review_ready"]
    require(len(boundaries) == len(set(boundaries)), "local readiness boundary replay")
    delivery_ids = [d["id"] for d in cell["deliveries"]]
    require(len(delivery_ids) == len(set(delivery_ids)), "recipient UUID reused")
    require(not set(delivery_ids) & set(event_ids), "event and recipient IDs must differ")
    for d in cell["deliveries"]:
        require(d["event_id"] in event_ids and d["assignment_id"] in assignments, "orphan recipient delivery")
    require(not ({d["id"] for d in cell["denials"]} & set(event_ids)), "denial and event IDs must differ")
    current = _current_results(cell)
    if cell["state"] in {"IMPLEMENTATION_READY", "LOCAL_REVIEW_READY"}:
        require(cell["pr_url"] and current.get("implementation", {}).get("status") == "ready", "readiness requires current IM result and PR")
    if cell["state"] == "LOCAL_REVIEW_READY":
        require(all(current.get(role, {}).get("status") == "passed" for role in ("qa", "reviewer")), "local readiness requires independent current SHA QA/RV passes")
        require(cell["ci"] == "passed" and not cell["pending_findings"], "local readiness requires CI and resolved findings")
        require(not any(d["status"] == "unresolved" for d in cell["denials"]), "native denial remains unresolved")
        terminal_events = {e["id"] for e in cell["events"] if e["kind"] == "local_review_ready"}
        require(not any(d["status"] == "unknown" and d["event_id"] not in terminal_events for d in cell["deliveries"]), "reconcile unknown dispatch before local readiness")
    require(cell["state"] not in {"CHANGES_REQUESTED", "CORRECTION_ACTIVE"} or cell["pending_findings"], "correction requires recorded findings")
    require(len({f["id"] for f in cell["pending_findings"]}) == len(cell["pending_findings"]), "duplicate finding identity")
    return cell


def create(repository, issue_number, branch, sha):
    return validate(dict(schema_version=VERSION, mode="native", cell_id=uid(), repository=repository,
        issue_number=issue_number, issue_url=f"https://github.com/{repository}/issues/{issue_number}",
        branch=branch, pr_url="", sha=sha, generation=0, state="IMPLEMENTATION_ACTIVE", ci="pending",
        assignments=[], results=[], events=[], deliveries=[], denials=[], pending_findings=[]))


def event(cell, kind, reference):
    item = dict(id=uid(), kind=kind, sha=cell["sha"], generation=cell["generation"], reference=reference)
    cell["events"].append(item)
    return item


def assignment(cell, role, objective, model, effort, rationale):
    validate(cell)
    require(role in ROLES, "unknown role")
    if role in {"qa", "reviewer"}:
        require(cell["state"] == "IMPLEMENTATION_READY", "specialist verification requires IM readiness")
    if role == "implementation":
        require(cell["state"] in {"IMPLEMENTATION_ACTIVE", "CHANGES_REQUESTED", "CORRECTION_ACTIVE"}, "IM assignment requires active work or correction")
    require(not any(a["role"] == role and a["generation"] == cell["generation"] and a["id"] not in {r["assignment_id"] for r in cell["results"]} for a in cell["assignments"]), "reconcile existing assignment before replacement")
    correction = role == "implementation" and cell["state"] == "CHANGES_REQUESTED"
    item = dict(id=uid(), role=role, sha=cell["sha"], generation=cell["generation"] + int(correction), objective=objective,
        model=model, effort=effort, rationale=rationale, authorization=AUTHORIZATION if role in {"coordinator", "implementation"} else "")
    candidate = copy.deepcopy(cell)
    candidate["assignments"].append(item)
    if role == "implementation" and cell["state"] == "CHANGES_REQUESTED":
        candidate["generation"] += 1
        candidate["ci"] = "pending"
        candidate["state"] = "CORRECTION_ACTIVE"
    validate(candidate)
    cell.update(candidate)
    return item


def initial_instructions(cell, item):
    require(item in cell["assignments"], "unknown assignment")
    return (f"Issue {cell['issue_url']}; branch {cell['branch']}; role {item['role']}; assignment {item['id']}; "
        f"SHA {item['sha']}; generation {item['generation']}. {item['objective']}\n"
        f"Model {item['model']}, effort {item['effort']}: {item['rationale']}\n{item['authorization']}\n"
        "Read AGENTS.md, your .codex/agents contract, and adr-context. Native specialist agents are authorized. "
        "Only IM edits source/commits; preserve others' edits. QA uses an isolated detached clone; RV is independent. "
        "Subagents inherit parent sandbox/approvals; role instructions are behavioral. Return a native-cell result "
        "bound to this assignment and exact SHA. Never merge or publish a release.\n"
        + ("Findings requiring a fix-to-verification map: " + json.dumps(cell["pending_findings"]) if item["role"] == "implementation" else ""))


def bind(cell, local, assignment_id, source_agent):
    """Record a host-observed spawn result, never a role label supplied by the agent."""
    validate(cell)
    verify_pr_binding(cell, local)
    a = next((a for a in cell["assignments"] if a["id"] == assignment_id), None)
    require(a is not None and source_agent, "assignment and observed native agent source required")
    require(local.get("coordinator"), "observed Coordinator identity required")
    require(local.get("identity", digest(identity(cell))) == digest(identity(cell)), "immutable cell identity changed; reconcile")
    contexts = local.get("contexts", {})
    for prior in cell["assignments"]:
        require(contexts.get(prior["id"], digest(prior)) == digest(prior), "assignment context changed; reconcile")
    require(source_agent != local["coordinator"], "Coordinator cannot bind itself as specialist")
    previous = local["bindings"].get(assignment_id)
    require(previous is None or previous["source"] == source_agent, "reconcile bound assignment before replacement")
    for b in local["bindings"].values():
        require(b["source"] != source_agent or b["role"] == a["role"], "one agent cannot impersonate independent roles")
        if a["role"] == "implementation" and b["role"] == "implementation":
            retired = {r["old_source"] for r in local.get("recoveries", [])}
            require(b["source"] == source_agent or b["source"] in retired, "corrections return to the same IM agent; recover it before replacement")
    local["bindings"][assignment_id] = {"source": source_agent, "role": a["role"]}
    local["identity"] = digest(identity(cell))
    local["pr_url"] = cell["pr_url"]
    local["contexts"] = {prior["id"]: digest(prior) for prior in cell["assignments"]}


def result(item, sha, status, evidence, *, findings=(), fixes=(), checks=(), final_guard=False):
    """Specialist-side mechanical record constructor; admission verifies native source."""
    require(item["role"] != "coordinator", "Coordinator cannot author specialist verdicts")
    return dict(id=uid(), assignment_id=item["id"], role=item["role"], sha=sha, generation=item["generation"],
        status=status, evidence=list(evidence), findings=list(findings), fixes=list(fixes), checks=list(checks), final_guard=final_guard)


def receive(cell, local, source_agent, record):
    """Host adapter: source_agent MUST come from native control return metadata."""
    validate(cell)
    verify_pr_binding(cell, local)
    schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
    errors = _validate_schema(record, schema["properties"]["results"]["items"], schema, "result")
    require(not errors, "; ".join(errors[:4]))
    _portable(record)
    require(local.get("identity") == digest(identity(cell)), "immutable cell identity changed; reconcile before result admission")
    a = next((a for a in cell["assignments"] if a["id"] == record["assignment_id"]), None)
    require(a and local.get("contexts", {}).get(a["id"]) == digest(a), "assignment context changed; reconcile before result admission")
    binding = local["bindings"].get(record.get("assignment_id"))
    require(binding and binding["source"] == source_agent and source_agent != local["coordinator"], "result source is not the bound specialist")
    require(binding["role"] == record.get("role"), "native source role mismatch")
    require(record.get("generation") == cell["generation"], "stale assignment generation")
    require(not any(r["id"] == record.get("id") or r["assignment_id"] == record.get("assignment_id") for r in cell["results"]), "result already applied; reconcile without replay")
    candidate = copy.deepcopy(cell)
    require(not any(d["status"] == "unresolved" for d in candidate["denials"]), "native denial requires supported resolution")
    if record["role"] == "implementation" and record["status"] == "ready":
        require(candidate["state"] in {"IMPLEMENTATION_ACTIVE", "CORRECTION_ACTIVE"}, "unexpected IM readiness")
        require(candidate["pr_url"] and record["checks"] and all(c["status"] == "passed" for c in record["checks"]), "IM readiness requires PR and passing local gates")
        expected = {f["id"] for f in candidate["pending_findings"]}
        require({f["finding_id"] for f in record["fixes"]} == expected and all(f["evidence"] for f in record["fixes"]), "finding-to-fix verification map incomplete")
        candidate["sha"] = record["sha"]
        candidate["pending_findings"] = []
        candidate["state"] = "IMPLEMENTATION_READY"
        candidate["ci"] = "pending"
    else:
        require(record["sha"] == candidate["sha"], "stale exact-SHA result")
        if record["status"] == "changes_requested":
            require(record["role"] in {"qa", "reviewer"} and record["findings"], "independent findings required")
            candidate["pending_findings"].extend(record["findings"])
            candidate["state"] = "CHANGES_REQUESTED"
    candidate["results"].append(copy.deepcopy(record))
    event(candidate, record["status"], record["id"])
    validate(candidate)
    cell.update(candidate)
    local["pr_url"] = cell["pr_url"]
    local.setdefault("receipts", {})[record["id"]] = receipt_digest(cell, record)


def rehydrate(cell, local, *, observed_sha, observed_pr, observed_issue_url, observed_branch):
    """Resume only after fresh native/GitHub identity and receipt reconciliation.

    Missing local state is recovery work, not permission to recreate agents. Rebuild
    bindings/receipts from observed native history and role-authored GitHub evidence.
    """
    validate(cell)
    verify_pr_binding(cell, local)
    require(cell["sha"] == observed_sha and cell["pr_url"] == observed_pr, "reconcile changed GitHub head/PR before reuse")
    require(cell["issue_url"] == observed_issue_url and cell["branch"] == observed_branch, "reconcile observed issue/branch before reuse")
    require(local.get("coordinator") and local.get("identity") == digest(identity(cell)), "immutable cell identity missing or altered; reconcile")
    for a in cell["assignments"]:
        require(local.get("contexts", {}).get(a["id"]) == digest(a), "assignment context missing or altered; reconcile")
        if a["role"] != "coordinator":
            binding = local.get("bindings", {}).get(a["id"], {})
            require(binding.get("role") == a["role"] and binding.get("source") and binding["source"] != local["coordinator"], "pending specialist source missing; reconcile before replacement")
    for r in cell["results"]:
        require(local.get("receipts", {}).get(r["id"]) == receipt_digest(cell, r), "result receipt missing or altered; reconcile native/GitHub evidence")
        require(local.get("bindings", {}).get(r["assignment_id"], {}).get("role") == r["role"], "specialist identity missing; reconcile before resume")
    local["pr_url"] = cell["pr_url"]
    return cell


def recover_agent(cell, local, old_source, new_source, *, observed_status, pending_observations, evidence):
    """Host-only replacement after proven loss, exact-head and delivery reconciliation.

    The caller must first rehydrate using fresh GitHub/native observations. This
    recovery changes execution handles, never issue ownership or applied results.
    """
    validate(cell)
    verify_pr_binding(cell, local)
    require(local.get("identity") == digest(identity(cell)), "reconcile cell identity before recovery")
    require(observed_status in {"stopped", "lost-confirmed"}, "prove old native execution stopped/lost before replacement")
    require(new_source and new_source != old_source and new_source != local.get("coordinator"), "new independent native source required")
    require(evidence and all(url.startswith("https://github.com/") for url in evidence), "durable recovery evidence required")
    require(not any(d["status"] == "unresolved" for d in cell["denials"]), "native denial is not resolved by agent replacement")
    require(not any(d["status"] == "unknown" for d in cell["deliveries"]), "reconcile uncertain recipients before replacement")
    affected = [a for a in cell["assignments"] if local.get("bindings", {}).get(a["id"], {}).get("source") == old_source]
    require(affected, "unknown old source")
    require(not any(b["source"] == new_source for b in local["bindings"].values()), "replacement cannot reuse another role's source")
    pending = [a for a in affected if a["id"] not in {r["assignment_id"] for r in cell["results"]}]
    require(set(pending_observations) == {a["id"] for a in pending} and all(v == "absent" for v in pending_observations.values()), "reconcile every pending result as absent; never duplicate applied work")
    for a in affected:
        require(local.get("contexts", {}).get(a["id"]) == digest(a), "reconcile assignment context before replacement")
    for a in pending:
        local["bindings"][a["id"]]["source"] = new_source
    local.setdefault("recoveries", []).append({"old_source": old_source, "new_source": new_source, "observed_status": observed_status, "evidence": list(evidence)})


def changed_head(cell, sha):
    validate(cell)
    require(SHA.fullmatch(sha), "full commit SHA required")
    require(sha != cell["sha"] or cell["state"] == "CHANGES_REQUESTED", "head unchanged")
    cell["generation"] += 1
    cell["sha"] = sha
    cell["ci"] = "pending"
    cell["state"] = "CHANGES_REQUESTED" if cell["pending_findings"] else "IMPLEMENTATION_ACTIVE"
    event(cell, "head_observed", sha)
    validate(cell)


def local_review_ready(cell, local):
    rehydrate(cell, local, observed_sha=cell["sha"], observed_pr=cell["pr_url"], observed_issue_url=cell["issue_url"], observed_branch=cell["branch"])
    require(local.get("pr_url") == cell["pr_url"] and cell["pr_url"], "sealed verification PR required for readiness")
    candidate = copy.deepcopy(cell)
    candidate["state"] = "LOCAL_REVIEW_READY"
    validate(candidate)
    if not any(e["kind"] == "local_review_ready" and e["generation"] == candidate["generation"] for e in candidate["events"]):
        event(candidate, "local_review_ready", candidate["pr_url"])
    cell.update(candidate)


def delivery(cell, event_id, assignment_id):
    validate(cell)
    require(not any(d["status"] == "unresolved" for d in cell["denials"]), "native denial requires supported resolution before dispatch")
    previous = [d for d in cell["deliveries"] if d["event_id"] == event_id and d["assignment_id"] == assignment_id]
    if previous:
        require(previous[-1]["status"] != "unknown", "reconcile unknown recipient before retry")
        if previous[-1]["status"] == "applied":
            return previous[-1]
    item = dict(id=uid(), event_id=event_id, assignment_id=assignment_id, status="unknown")
    candidate = copy.deepcopy(cell)
    candidate["deliveries"].append(item)
    validate(candidate)
    cell.update(candidate)
    return item


def reconcile(cell, delivery_id, observed):
    require(observed in {"absent", "applied"}, "supported native/GitHub reconciliation required")
    item = next((d for d in cell["deliveries"] if d["id"] == delivery_id), None)
    require(item and item["status"] == "unknown", "only unknown recipient can be reconciled")
    item["status"] = observed
    validate(cell)
    # Parent lifecycle event stays applied even when this child was absent.


def denial(cell, reason):
    item = dict(id=uid(), reason=reason, status="unresolved", evidence="")
    cell["denials"].append(item)
    if cell["state"] == "LOCAL_REVIEW_READY":
        cell["state"] = "IMPLEMENTATION_READY"
    validate(cell)
    return item


def resolve_denial(cell, denial_id, evidence):
    require(evidence.startswith("https://github.com/"), "durable supported-resolution evidence required")
    item = next((d for d in cell["denials"] if d["id"] == denial_id), None)
    require(item and item["status"] == "unresolved", "unresolved denial required")
    item.update(status="resolved", evidence=evidence)
    validate(cell)


def load_checkpoint(path, *, mode="native"):
    value = json.loads(Path(path).read_text(encoding="utf-8"))
    if value.get("schema_version") != VERSION:
        require(mode == "legacy-top-level", "legacy checkpoint: explicitly opt into legacy-top-level; never silently convert")
        return value  # Pass unchanged to the retained legacy adapter; no migration.
    require(mode == "native", "native checkpoint cannot use legacy transport")
    return validate(value)


def save_checkpoint(cell, path):
    validate(cell)
    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = destination.with_suffix(destination.suffix + ".new")
    temporary.write_text(json.dumps(cell, indent=2) + "\n", encoding="utf-8")
    temporary.replace(destination)


def local_path(repository, cell_id):
    common = subprocess.check_output(["git", "rev-parse", "--git-common-dir"], cwd=repository, text=True).strip()
    return (Path(repository) / common).resolve() / "pleiad/native-cells" / f"{cell_id}.json"


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--checkpoint", required=True, type=Path)
    sub = parser.add_subparsers(dest="command", required=True)
    init = sub.add_parser("init")
    for key in ("repository", "branch", "sha"):
        init.add_argument("--" + key, required=True)
    init.add_argument("--issue-number", required=True, type=int)
    assign = sub.add_parser("assign")
    for key in ("role", "objective", "model", "effort", "rationale"):
        assign.add_argument("--" + key, required=True)
    assign.add_argument("--instructions", action="store_true")
    make = sub.add_parser("result", help="specialist constructs a result; does not admit a verdict")
    for key in ("assignment-id", "sha", "status"):
        make.add_argument("--" + key, required=True)
    make.add_argument("--evidence", action="append", required=True)
    make.add_argument("--checks", type=Path, required=True)
    make.add_argument("--findings", type=Path)
    make.add_argument("--fixes", type=Path)
    make.add_argument("--final-guard", action="store_true")
    bind_cmd = sub.add_parser("bind", help="local host adapter records observed spawn source")
    bind_cmd.add_argument("--assignment-id", required=True)
    bind_cmd.add_argument("--source", required=True)
    bind_cmd.add_argument("--coordinator", required=True)
    receive_cmd = sub.add_parser("receive", help="host supplies source from native result metadata")
    receive_cmd.add_argument("--source", required=True)
    receive_cmd.add_argument("--result", type=Path, required=True)
    resume = sub.add_parser("resume")
    resume.add_argument("--observed-sha", required=True)
    resume.add_argument("--observed-pr", required=True)
    resume.add_argument("--observed-issue-url", required=True)
    resume.add_argument("--observed-branch", required=True)
    head = sub.add_parser("head")
    head.add_argument("--sha", required=True)
    pr = sub.add_parser("pr")
    pr.add_argument("--url", required=True)
    ci = sub.add_parser("ci")
    ci.add_argument("--status", choices=["pending", "passed", "failed"], required=True)
    sub.add_parser("ready")
    sub.add_parser("validate")
    args = parser.parse_args(argv)
    try:
        if args.command == "init":
            require(not args.checkpoint.exists(), "checkpoint exists; rehydrate and reconcile instead of duplicating cell")
            cell = create(args.repository, args.issue_number, args.branch, args.sha)
            output = cell
        else:
            cell = load_checkpoint(args.checkpoint)
            output = None
            if args.command == "assign":
                item = assignment(cell, args.role, args.objective, args.model, args.effort, args.rationale)
                output = initial_instructions(cell, item) if args.instructions else item
            elif args.command == "result":
                item = next((a for a in cell["assignments"] if a["id"] == args.assignment_id), None)
                require(item is not None, "unknown assignment")
                read = lambda p: json.loads(p.read_text(encoding="utf-8")) if p else []
                print(json.dumps(result(item, args.sha, args.status, args.evidence, checks=read(args.checks), findings=read(args.findings), fixes=read(args.fixes), final_guard=args.final_guard), indent=2))
                return 0
            elif args.command in {"bind", "receive", "resume"}:
                path = local_path(Path.cwd(), cell["cell_id"])
                local = json.loads(path.read_text()) if path.exists() else {"coordinator": getattr(args, "coordinator", ""), "bindings": {}}
                if args.command == "resume":
                    rehydrate(cell, local, observed_sha=args.observed_sha, observed_pr=args.observed_pr, observed_issue_url=args.observed_issue_url, observed_branch=args.observed_branch)
                elif args.command == "bind":
                    require(local["coordinator"] == args.coordinator, "local Coordinator identity mismatch")
                    bind(cell, local, args.assignment_id, args.source)
                    path.parent.mkdir(parents=True, exist_ok=True)
                    path.write_text(json.dumps(local, indent=2), encoding="utf-8")
                else:
                    receive(cell, local, args.source, json.loads(args.result.read_text(encoding="utf-8")))
                    path.write_text(json.dumps(local, indent=2), encoding="utf-8")
            elif args.command == "head":
                changed_head(cell, args.sha)
            elif args.command == "pr":
                require(not cell["pr_url"] or cell["pr_url"] == args.url, "one cell owns one PR")
                cell["pr_url"] = args.url
            elif args.command == "ci":
                cell["ci"] = args.status
            elif args.command == "ready":
                path = local_path(Path.cwd(), cell["cell_id"])
                require(path.exists(), "local specialist/PR receipts required for readiness")
                local_review_ready(cell, json.loads(path.read_text(encoding="utf-8")))
        save_checkpoint(cell, args.checkpoint)
        print(output if isinstance(output, str) else json.dumps(output or {"cell_id": cell["cell_id"], "state": cell["state"], "sha": cell["sha"]}, indent=2))
        return 0
    except (CellError, KeyError, TypeError, json.JSONDecodeError) as exc:
        print(f"PLEIAD_NATIVE_INVALID: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
