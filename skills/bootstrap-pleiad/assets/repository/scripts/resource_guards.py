# pleiad:managed resource-guards/v1
"""Fail-closed operational ownership records. No deletion, kill or network code.

Use LedgerStore.transaction for every host operation, including the host's cleanup
callback. The exclusive lock is never stolen on restart. JSON/digests detect drift,
not malicious changes by actors sharing host permissions.
"""
from __future__ import annotations

import copy
import hashlib
import json
import os
import re
import subprocess
from contextlib import contextmanager
from pathlib import Path
from uuid import UUID, uuid4

from coordination_protocol import _validate_schema

VERSION = "cell-resources/v1"
KINDS = {"qa-clone", "server", "port", "process", "device", "tunnel"}
CHECKS = {"final", "passed", "exact_sha", "clone_boundary", "source_unchanged", "refs_unchanged"}
SCHEMA = Path(__file__).resolve().parents[1] / ".pleiad/resource-ledger.schema.json"


class ResourceError(ValueError):
    pass


def require(condition, message):
    if not condition:
        raise ResourceError(message)


def uid():
    return str(uuid4())


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True).encode()).hexdigest()


def token(value):
    require(isinstance(value, str) and re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,100}", value), "logical token required; no local handles")
    return value


def create(cell_id, owner, generation, sha):
    return validate(dict(schema_version=VERSION, cell_id=cell_id, owner=token(owner), generation=generation,
                         sha=sha, resources=[]))


def validate(ledger):
    schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
    errors = _validate_schema(ledger, schema, schema, "$")
    require(not errors, "; ".join(errors[:4]))
    token(ledger["owner"])
    ids = []
    for resource in ledger["resources"]:
        ids.append(resource["id"])
        token(resource["name"])
        require(resource["owner"] == ledger["owner"], "resource owner mismatch")
        require(resource["cell_id"] == ledger["cell_id"], "resource cell mismatch")
        for lease in resource["leases"]:
            token(lease["consumer"])
            ids.append(lease["id"])
        require(len({x["consumer"] for x in resource["leases"]}) == len(resource["leases"]), "duplicate consumer lease")
        require(resource["state"] == "USING" or not resource["leases"], "sealed resource has active consumer")
        cert = resource["certificate"]
        require(resource["state"] != "GUARDED" or resource["guard"] is not None, "guarded state requires final evidence")
        if resource["state"] == "USING":
            require(resource["guard"] is None and cert is None, "active use must invalidate prior guard/certificate")
        if resource["state"] == "GUARDED":
            require(cert is None, "guarded state cannot retain previous certificate")
        if resource["state"] in {"CERTIFIED", "CLEANING", "CLEANED"}:
            require(cert is not None, "owner certificate required")
            require(cert == certificate_fields(ledger, resource, cert["id"]), "stale owner certificate")
            require(resource["guard"] is not None, "final guard required")
        if resource["guard"] is not None:
            _check_guard(ledger, resource, resource["guard"])
        require((resource["state"] == "CLEANED") == (resource["receipt"] is not None), "cleanup receipt/state mismatch")
        if resource["receipt"] is not None:
            require(resource["receipt"] == {"certificate_id": cert["id"], "resource_id": resource["id"],
                    "sha": resource["sha"], "generation": resource["generation"], "outcome": "cleaned"}, "cleanup receipt mismatch")
    require(len(ids) == len(set(ids)), "resource or lease identity reused")
    return ledger


def _resource(ledger, resource_id, owner):
    validate(ledger)
    require(owner == ledger["owner"], "wrong operational owner")
    item = next((r for r in ledger["resources"] if r["id"] == resource_id), None)
    require(item is not None, "unknown resource")
    require(item["generation"] == ledger["generation"] and item["sha"] == ledger["sha"], "stale resource generation/SHA; reconcile without cleanup")
    return item


def acquire(ledger, local, *, owner, kind, name, handle):
    validate(ledger)
    require(owner == ledger["owner"] and kind in KINDS, "wrong owner or resource kind")
    token(name)
    require(not any(r["name"] == name and r["state"] != "CLEANED" for r in ledger["resources"]), "resource name already owned; reconcile")
    require(isinstance(handle, dict) and handle, "observed private handle required")
    if kind == "qa-clone":
        require(set(handle) == {"path", "disposable_root", "device", "inode", "created", "root_identity", "marker_identity"}, "resolved clone boundary and filesystem identity required")
        require(observe_path(handle) == handle, "current resolved clone identity required")
    if kind in {"process", "server"}:
        require(type(handle.get("pid")) is int and handle["pid"] > 0 and bool(handle.get("start_identity")), "process identity needs PID plus observed start identity")
    if kind in {"port", "device", "tunnel"}:
        require(bool(handle.get("lease_identity")), "observed device/port/tunnel lease identity required")
        require(bool(handle.get({"port": "address", "device": "device_identity", "tunnel": "tunnel_identity"}[kind])), "resource address identity required")
    item = dict(id=uid(), cell_id=ledger["cell_id"], owner=owner, kind=kind, name=name,
                generation=ledger["generation"], sha=ledger["sha"], revision=0, state="USING",
                leases=[], guard=None, certificate=None, receipt=None)
    entry = {"handle": copy.deepcopy(handle), "binding": digest({"resource": item, "handle": handle})}
    candidate = {"ledger": copy.deepcopy(ledger), "local": copy.deepcopy(local)}
    candidate["ledger"]["resources"].append(item)
    candidate["local"][item["id"]] = entry
    _handle_keys(candidate)  # Check ancestor boundaries before recording the claim.
    ledger["resources"].append(item)
    local[item["id"]] = entry
    return item["id"]


def lease(ledger, resource_id, *, owner, consumer):
    item = _resource(ledger, resource_id, owner)
    require(item["state"] in {"USING", "GUARDED", "CERTIFIED"}, "cleanup has sealed resource use")
    token(consumer)
    require(not any(x["consumer"] == consumer for x in item["leases"]), "consumer already owns a lease")
    item.update(state="USING", revision=item["revision"] + 1, guard=None, certificate=None)
    record = {"id": uid(), "consumer": consumer}
    item["leases"].append(record)
    return record["id"]


def release(ledger, resource_id, *, owner, consumer, lease_id):
    item = _resource(ledger, resource_id, owner)
    record = {"id": lease_id, "consumer": consumer}
    require(record in item["leases"], "wrong consumer or lease identity")
    item["leases"].remove(record)
    item["revision"] += 1


def _check_guard(ledger, item, evidence):
    common = {"final", "passed"}
    required = CHECKS if item["kind"] == "qa-clone" else common
    require(set(evidence) == required | {"sha", "generation"}, "final guard evidence fields differ")
    require(all(evidence[key] is True for key in required), "failed/missing final guard blocks cleanup")
    require(evidence["sha"] == item["sha"] and evidence["generation"] == item["generation"], "guard generation/SHA mismatch")


def final_guard(ledger, resource_id, *, owner, evidence):
    item = _resource(ledger, resource_id, owner)
    require(item["state"] in {"USING", "GUARDED"} and not item["leases"], "final guard requires all consumers released")
    _check_guard(ledger, item, evidence)
    item.update(guard=copy.deepcopy(evidence), state="GUARDED", revision=item["revision"] + 1)


def certificate_fields(ledger, item, certificate_id):
    return dict(id=certificate_id, resource_id=item["id"], cell_id=ledger["cell_id"], owner=item["owner"],
                generation=item["generation"], sha=item["sha"], revision=item["revision"], state="GUARDED",
                guard_digest=digest(item["guard"]))


def certify(ledger, resource_id, *, owner):
    item = _resource(ledger, resource_id, owner)
    require(item["state"] == "GUARDED" and not item["leases"], "current final guard and no leases required")
    item["certificate"] = certificate_fields(ledger, item, uid())
    item["state"] = "CERTIFIED"
    return copy.deepcopy(item["certificate"])


def _entry(local, item):
    entry = local.get(item["id"])
    require(entry is not None, "missing local handle; reconcile, never infer a path/process")
    # Binding covers acquisition identity, excluding the evolving lifecycle fields.
    acquired = dict(item, revision=0, state="USING", leases=[], guard=None, certificate=None, receipt=None)
    require(entry.get("binding") == digest({"resource": acquired, "handle": entry.get("handle")}), "local ownership binding changed")
    return entry


def _owned(ledger, local, item, observe):
    entry = _entry(local, item)
    require(observe(copy.deepcopy(entry["handle"])) == entry["handle"], "owned handle unresolved or replaced; no cleanup")
    return copy.deepcopy(entry["handle"])


def reconcile(ledger, local, resource_id, *, owner, observe):
    """Read-only recovery check; never substitutes another path, PID or lease."""
    item = _resource(ledger, resource_id, owner)
    require(item["state"] != "CLEANED", "already cleaned; retain receipt")
    return _owned(ledger, local, item, observe)


def cleanup(ledger, local, resource_id, *, owner, certificate, observe, remove, absent, persist):
    """Host adapter; call inside LedgerStore.transaction, holding lock throughout.

    persist seals CLEANING before invoking the host's existing permission-controlled
    remove callback. Exception/unknown outcome keeps CLEANING and blocks replay.
    Recovery may record observed absence using complete_cleanup; never blindly retry.
    """
    item = _resource(ledger, resource_id, owner)
    require(item["state"] == "CERTIFIED" and not item["leases"], "cleanup requires certified idle resource")
    require(certificate == item["certificate"], "stale or foreign certificate")
    handle = _owned(ledger, local, item, observe)
    item["state"] = "CLEANING"
    persist()
    remove(copy.deepcopy(handle))
    return complete_cleanup(ledger, local, resource_id, owner=owner, certificate=certificate, absent=absent)


def complete_cleanup(ledger, local, resource_id, *, owner, certificate, absent):
    item = _resource(ledger, resource_id, owner)
    require(item["state"] == "CLEANING" and certificate == item["certificate"], "exact cleaning certificate required")
    entry = _entry(local, item)
    require(absent(copy.deepcopy(entry["handle"])) is True, "cleanup absence unresolved; preserve CLEANING")
    item["receipt"] = dict(certificate_id=certificate["id"], resource_id=resource_id,
                           sha=item["sha"], generation=item["generation"], outcome="cleaned")
    item["state"] = "CLEANED"
    return copy.deepcopy(item["receipt"])


def path_handle(path, disposable_root):
    """Resolve an existing strict child; reject Windows junction/reparse aliases.

    No recursive file operation is performed. Host must observe again immediately
    before native removal and retain its filesystem/approval controls.
    """
    raw, boundary = Path(path).absolute(), Path(disposable_root).absolute()
    for candidate in (raw, boundary):
        for part in (candidate, *candidate.parents):
            require(not part.is_symlink() and not (part.exists() and getattr(part.lstat(), "st_file_attributes", 0) & 0x400), "symlink/reparse path unresolved")
    root, target = boundary.resolve(strict=True), raw.resolve(strict=True)
    require(target != root and root in target.parents, "target must be a strict child of declared disposable root")
    require(target.is_dir(), "owned disposable directory required")
    stat = target.stat()
    root_stat = root.stat()
    marker = target / ".git" / "pleiad-resource-owner"
    marker_identity = None
    if marker.exists():
        require(not marker.is_symlink() and not marker.parent.is_symlink(), "ownership marker alias unresolved")
        require(not any(getattr(p.lstat(), "st_file_attributes", 0) & 0x400 for p in (marker, marker.parent)), "ownership marker reparse unresolved")
        UUID(marker.read_text(encoding="utf-8"))
        marker_stat = marker.stat()
        marker_identity = [marker_stat.st_dev, marker_stat.st_ino, marker_stat.st_ctime_ns, marker.read_text(encoding="utf-8")]
    return dict(path=str(target), disposable_root=str(root), device=stat.st_dev, inode=stat.st_ino,
                created=getattr(stat, "st_birthtime_ns", 0 if marker_identity else stat.st_ctime_ns),
                root_identity=[root_stat.st_dev, root_stat.st_ino], marker_identity=marker_identity)


def register_clone(path, disposable_root):
    """Host provisioning: exclusive private marker in a fresh clone's .git.

    Keeps POSIX directory output changes from looking like replacement while
    retaining marker/inode identity across restart. Never overwrite an old marker.
    """
    observed = path_handle(path, disposable_root)
    git_dir = Path(observed["path"]) / ".git"
    require(git_dir.is_dir() and not git_dir.is_symlink() and not getattr(git_dir.lstat(), "st_file_attributes", 0) & 0x400, "fresh clone needs a native .git directory")
    with (git_dir / "pleiad-resource-owner").open("x", encoding="utf-8") as stream:
        stream.write(uid())
    return path_handle(path, disposable_root)


def observe_path(handle):
    try:
        return path_handle(handle["path"], handle["disposable_root"])
    except (OSError, ResourceError, KeyError):
        return None


class LedgerStore:
    """Machine-local store. Caller supplies a Git common-dir/pleiad location.

    One file atomically stores logical records plus handles. Only public() may be
    persisted to GitHub. Interrupted locks need explicit host reconciliation;
    stale-lock timeout is deliberately unsupported.
    """
    def __init__(self, path, *, expected_identity=None, require_existing=False, legacy_path=None):
        self.path = Path(path)
        self.expected_identity = expected_identity
        self.require_existing = require_existing
        self.legacy_path = legacy_path

    @classmethod
    def for_repository(cls, repository, cell_id, generation, sha, *, legacy=False):
        UUID(cell_id)
        require(type(generation) is int and generation >= 0, "resource generation required")
        require(isinstance(sha, str) and re.fullmatch(r"[0-9a-f]{40}", sha), "exact resource SHA required")
        observed = subprocess.run(["git", "rev-parse", "--git-common-dir"], cwd=repository,
                                  text=True, capture_output=True, check=True).stdout.strip()
        common = Path(observed)
        if not common.is_absolute():
            common = Path(repository) / common
        directory = common.resolve() / "pleiad" / "resources"
        old = directory / f"{cell_id}-{generation}.json"
        return cls(old if legacy else directory / f"{cell_id}-{generation}-{sha}.json",
                   expected_identity=(cell_id, generation, sha), require_existing=legacy,
                   legacy_path=None if legacy else old)

    @contextmanager
    def transaction(self, initial=None):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        # All cell/generation stores under this repository share the same lock.
        lock = self.path.parent / "ownership.lock"
        try:
            fd = os.open(lock, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
        except FileExistsError as exc:
            raise ResourceError("ledger locked; reconcile active/interrupted host before retry") from exc
        try:
            os.close(fd)
            require(not self.require_existing or self.path.exists(), "legacy resource store missing; reconcile rather than creating it")
            expected = self.expected_identity
            initial_owner = None
            if initial is not None:
                _check_store(initial)
                initial_identity = tuple(initial["ledger"][k] for k in ("cell_id", "generation", "sha"))
                require(expected is None or initial_identity == expected, "initial resource identity differs from requested cell/generation/SHA")
                expected = expected or initial_identity
                initial_owner = initial["ledger"]["owner"]
            state = _read_store(self.path) if self.path.exists() else copy.deepcopy(initial)
            _check_store(state)

            def check_identity():
                actual = tuple(state["ledger"][k] for k in ("cell_id", "generation", "sha"))
                require(expected is None or actual == expected, "loaded resource identity differs from requested cell/generation/SHA")
                require(initial_owner is None or state["ledger"]["owner"] == initial_owner, "loaded resource owner differs from initial owner")

            check_identity()
            if self.legacy_path is not None and self.legacy_path.exists():
                historical = _read_store(self.legacy_path)["ledger"]
                require((historical["cell_id"], historical["generation"]) == expected[:2], "legacy resource identity mismatch; reconcile")
                require(historical["sha"] != expected[2], "matching legacy resource store exists; reopen with legacy=True and exact original SHA")

            def check_ownership():
                validate(state["ledger"])
                check_identity()
                keys = _handle_keys(state)
                for peer in self.path.parent.glob("*.json"):
                    if peer == self.path:
                        continue
                    previous = _read_store(peer)
                    require(not _overlapping_keys(keys, _handle_keys(previous)), "overlapping resource already owned by another cell/generation; reconcile")

            def persist():
                check_ownership()
                temp = self.path.with_suffix(self.path.suffix + ".tmp")
                with temp.open("w", encoding="utf-8") as stream:
                    json.dump(state, stream, indent=2)
                    stream.flush()
                    os.fsync(stream.fileno())
                os.replace(temp, self.path)

            # Save on exceptions too: cleanup uncertainty must survive interruption.
            check_ownership()  # Imported/restarted conflicting claims never reach callbacks.
            try:
                yield state["ledger"], state["local"], persist
            finally:
                persist()
        finally:
            lock.unlink()


def _check_store(state):
    require(isinstance(state, dict) and set(state) == {"ledger", "local"} and isinstance(state["local"], dict),
            "complete resource store required; keep nonledger sidecars outside resources and reconcile unknown files")
    validate(state["ledger"])


def _read_store(path):
    try:
        state = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ResourceError("unreadable resource store; reconcile before host operations") from exc
    _check_store(state)
    return state


def _handle_keys(state):
    """Local conflict keys reserve addresses even if a process/path was replaced."""
    validate(state["ledger"])
    keys = set()
    for item in state["ledger"]["resources"]:
        if item["state"] == "CLEANED":
            continue
        entry = _entry(state["local"], item)
        handle = entry["handle"]
        if item["kind"] == "qa-clone":
            # Registration has resolved the path. Preserve that reserved address
            # even if the path is absent or replaced by an alias after restart.
            key = ("path", os.path.normcase(os.path.abspath(handle["path"])))
        elif item["kind"] in {"process", "server"}:
            key = ("process", handle["pid"])
        else:
            key = (item["kind"], handle[{"port": "address", "device": "device_identity", "tunnel": "tunnel_identity"}[item["kind"]]])
        require(not _overlapping_keys({key}, keys), "overlapping resource address")
        keys.add(key)
    return keys


def _overlapping_keys(left, right):
    for first in left:
        for second in right:
            if first == second:
                return True
            if first[0] == second[0] == "path":
                try:
                    if os.path.commonpath([first[1], second[1]]) in {first[1], second[1]}:
                        return True
                except ValueError:  # Separate Windows drives cannot overlap.
                    continue
    return False


def public(ledger):
    """Validated allowlisted logical record; never export local bindings/handles."""
    return copy.deepcopy(validate(ledger))


def demo_exception(*, direct_owner, cell_id, sha, patch_digest, patch_uncommitted, checks, rollback_digest,
                   resources, expires_at, now, max_restarts):
    """Host must obtain direct_owner from the human channel, never assistant text.

    Patch and rollback stay local/uncommitted; durable records keep hashes only.
    """
    require(direct_owner is True, "temporary demo requires direct scoped owner exception")
    require(patch_uncommitted is True, "temporary demo patch must stay uncommitted")
    require(re.fullmatch(r"[0-9a-f]{40}", sha or ""), "exact demo SHA required")
    require(all(re.fullmatch(r"[0-9a-f]{64}", x or "") for x in (patch_digest, rollback_digest)), "uncommitted patch and rollback digests required")
    require(checks and all(type(x) is str and token(x) for x in checks), "demo check record required")
    require(type(max_restarts) is int and 0 <= max_restarts <= 3, "bounded owned restart limit required")
    require(type(now) is int and type(expires_at) is int and now < expires_at <= now + 3600, "demo expires within one hour")
    require(resources and len(set(resources)) == len(resources), "explicit owned demo resources required")
    for value in resources:
        UUID(value)
    UUID(cell_id)
    return dict(id=uid(), cell_id=cell_id, sha=sha, patch_digest=patch_digest,
                checks=list(checks), rollback_digest=rollback_digest, resources=list(resources),
                expires_at=expires_at, max_restarts=max_restarts, restarts=0, rolled_back=False,
                rollback_requested=False, rollback_checks=[],
                scope="temporary-local-demo", publication=False, deployment=False, public_exposure=False,
                merge=False, release=False)


def demo_action(record, ledger, *, action, resource_id, now, uncommitted_patch_digest, patch_uncommitted):
    require(patch_uncommitted is True, "temporary demo does not authorize a commit")
    require(record["cell_id"] == ledger["cell_id"] and record["sha"] == ledger["sha"], "stale demo cell/SHA")
    require(not record["rolled_back"] and (action == "rollback" or now < record["expires_at"]), "demo expired or rolled back")
    require(uncommitted_patch_digest == record["patch_digest"], "demo patch changed or committed; reauthorize")
    item = _resource(ledger, resource_id, ledger["owner"])
    require(resource_id in record["resources"] and item["state"] == "USING", "demo resource is not owned and active")
    require(item["kind"] != "tunnel", "local demo never authorizes public tunnel exposure")
    require(action in {"preview", "restart", "rollback"}, "demo grants no source publication/deploy/merge/release authority")
    if action == "restart":
        require(record["restarts"] < record["max_restarts"], "demo restart limit exhausted")
        record["restarts"] += 1
    if action == "rollback":
        record["rollback_requested"] = True
    return True


def demo_rollback_receipt(record, *, applied_rollback_digest, checks):
    require(record["rollback_requested"] and not record["rolled_back"], "pending demo rollback required")
    require(applied_rollback_digest == record["rollback_digest"], "exact demo rollback patch required")
    require(checks and all(type(x) is str and token(x) for x in checks), "passing rollback checks required")
    record.update(rolled_back=True, rollback_checks=list(checks))
