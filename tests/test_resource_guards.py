"""Adversarial operational ownership tests; all host side effects use fixtures."""
import copy
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch
from uuid import uuid4

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import resource_guards as rg
import manage_repository as managed
from qa_workspace import WorkspaceSnapshot, cleanup_evidence, verify_qa_workspace

ROOT = Path(__file__).resolve().parents[1]
TEMP_ROOT = ROOT / "tests/.tmp"
TEMP_ROOT.mkdir(exist_ok=True)
SHA = "a" * 40


class ResourceTests(unittest.TestCase):
    def setUp(self):
        self.ledger = rg.create(str(uuid4()), "issue-28-co", 0, SHA)
        self.local = {}
        self.handle = {"pid": 123, "start_identity": "process-start-1"}
        self.rid = rg.acquire(self.ledger, self.local, owner="issue-28-co", kind="process", name="preview", handle=self.handle)
        self.calls = []

    def guard(self, rid=None):
        rid = rid or self.rid
        item = next(x for x in self.ledger["resources"] if x["id"] == rid)
        evidence = dict(final=True, passed=True, sha=SHA, generation=0)
        if item["kind"] == "qa-clone":
            evidence.update(exact_sha=True, clone_boundary=True, source_unchanged=True, refs_unchanged=True)
        rg.final_guard(self.ledger, rid, owner="issue-28-co", evidence=evidence)
        return rg.certify(self.ledger, rid, owner="issue-28-co")

    def cleanup(self, certificate, **kwargs):
        return rg.cleanup(self.ledger, self.local, self.rid, owner="issue-28-co", certificate=certificate,
            observe=kwargs.get("observe", lambda h: h), remove=kwargs.get("remove", lambda h: self.calls.append(h)),
            absent=kwargs.get("absent", lambda h: True), persist=lambda: None)

    def test_missing_failed_guard_or_active_verifier_never_cleans(self):
        for certificate in (None, {}):
            with self.assertRaises(rg.ResourceError):
                self.cleanup(certificate)
        with self.assertRaises(rg.ResourceError):
            rg.final_guard(self.ledger, self.rid, owner="issue-28-co", evidence=dict(final=True, passed=False, sha=SHA, generation=0))
        lease = rg.lease(self.ledger, self.rid, owner="issue-28-co", consumer="qa")
        with self.assertRaises(rg.ResourceError):
            self.guard()
        for consumer, lease_id in (("rv", lease), ("qa", str(uuid4()))):
            with self.assertRaises(rg.ResourceError):
                rg.release(self.ledger, self.rid, owner="issue-28-co", consumer=consumer, lease_id=lease_id)
        self.assertFalse(self.calls)

    def test_acquisition_invalidates_certificate_even_after_consumer_release(self):
        old = self.guard()
        lease = rg.lease(self.ledger, self.rid, owner="issue-28-co", consumer="late-qa")
        with self.assertRaises(rg.ResourceError):
            self.cleanup(old)
        rg.release(self.ledger, self.rid, owner="issue-28-co", consumer="late-qa", lease_id=lease)
        new = self.guard()
        with self.assertRaises(rg.ResourceError):
            self.cleanup(old)
        receipt = self.cleanup(new)
        self.assertEqual(receipt["certificate_id"], new["id"])
        self.assertEqual(receipt["sha"], SHA)
        self.assertEqual(len(self.calls), 1)
        with self.assertRaises(rg.ResourceError):
            rg.lease(self.ledger, self.rid, owner="issue-28-co", consumer="late")

    def test_wrong_owner_resource_generation_sha_and_forged_state_rejected(self):
        cert = self.guard()
        for field, value in (("owner", "issue-29-co"), ("resource_id", str(uuid4())), ("sha", "b" * 40), ("generation", 1), ("state", "USING")):
            wrong = dict(cert, **{field: value})
            with self.subTest(field=field), self.assertRaises(rg.ResourceError):
                self.cleanup(wrong)
        with self.assertRaises(rg.ResourceError):
            rg.reconcile(self.ledger, self.local, self.rid, owner="issue-29-co", observe=lambda h: h)
        self.ledger["generation"] += 1
        with self.assertRaises(rg.ResourceError):
            self.cleanup(cert)
        self.assertFalse(self.calls)

    def test_process_restart_pid_reuse_and_missing_local_state_block_recovery(self):
        cert = self.guard()
        with self.assertRaises(rg.ResourceError):
            self.cleanup(cert, observe=lambda h: dict(h, start_identity="process-start-2"))
        with self.assertRaises(rg.ResourceError):
            rg.reconcile(self.ledger, {}, self.rid, owner="issue-28-co", observe=lambda h: h)
        self.assertEqual(rg.reconcile(self.ledger, self.local, self.rid, owner="issue-28-co", observe=lambda h: h), self.handle)
        self.assertFalse(self.calls)

    def test_uncertain_cleanup_seals_use_and_never_replays(self):
        cert = self.guard()
        def failed(_):
            raise OSError("host outcome unknown")
        with self.assertRaises(OSError):
            self.cleanup(cert, remove=failed)
        self.assertEqual(self.ledger["resources"][0]["state"], "CLEANING")
        with self.assertRaises(rg.ResourceError):
            self.cleanup(cert)
        with self.assertRaises(rg.ResourceError):
            rg.complete_cleanup(self.ledger, self.local, self.rid, owner="issue-28-co", certificate=cert, absent=lambda _: False)
        receipt = rg.complete_cleanup(self.ledger, self.local, self.rid, owner="issue-28-co", certificate=cert, absent=lambda _: True)
        self.assertEqual(receipt["outcome"], "cleaned")

    def test_cleanup_race_is_serialized_and_uncertainty_persisted(self):
        with tempfile.TemporaryDirectory(dir=TEMP_ROOT) as tmp:
            store = rg.LedgerStore(Path(tmp) / "resources.json")
            initial = {"ledger": self.ledger, "local": self.local}
            with store.transaction(initial) as (ledger, local, persist):
                with self.assertRaises(rg.ResourceError):
                    with store.transaction():
                        self.fail("second verifier entered while cleanup lock held")
                rg.final_guard(ledger, self.rid, owner="issue-28-co", evidence=dict(final=True, passed=True, sha=SHA, generation=0))
                cert = rg.certify(ledger, self.rid, owner="issue-28-co")
                def interrupted(_):
                    snapshot = json.loads(store.path.read_text())
                    self.assertEqual(snapshot["ledger"]["resources"][0]["state"], "CLEANING")
                    with self.assertRaises(rg.ResourceError):
                        with store.transaction():
                            self.fail("consumer raced cleanup")
                    raise OSError("interrupted")
                with self.assertRaises(OSError):
                    rg.cleanup(ledger, local, self.rid, owner="issue-28-co", certificate=cert, observe=lambda h: h,
                               remove=interrupted, absent=lambda h: True, persist=persist)
            with store.transaction() as (ledger, local, persist):
                self.assertEqual(ledger["resources"][0]["state"], "CLEANING")
                with self.assertRaises(rg.ResourceError):
                    rg.lease(ledger, self.rid, owner="issue-28-co", consumer="qa")

    def test_recovery_never_unlinks_stale_lock(self):
        with tempfile.TemporaryDirectory(dir=TEMP_ROOT) as tmp:
            store = rg.LedgerStore(Path(tmp) / "resources.json")
            lock = store.path.parent / "ownership.lock"
            lock.write_text("interrupted host")
            with self.assertRaises(rg.ResourceError):
                with store.transaction():
                    pass
            self.assertTrue(lock.exists())

    def test_resolved_clone_boundary_and_replacement_guard(self):
        with tempfile.TemporaryDirectory(dir=TEMP_ROOT) as tmp:
            root = Path(tmp)
            target = root / "qa-clone"
            target.mkdir()
            with self.assertRaises(rg.ResourceError):
                rg.path_handle(root, root)
            with self.assertRaises(rg.ResourceError):
                rg.path_handle(root, target)
            handle = rg.path_handle(target, root)
            rid = rg.acquire(self.ledger, self.local, owner="issue-28-co", kind="qa-clone", name="qa", handle=handle)
            cert = self.guard(rid)
            # Replace the fixture while retaining the original; avoids inode reuse.
            target.rename(root / "old-clone")
            target.mkdir()
            with self.assertRaises(rg.ResourceError):
                rg.cleanup(self.ledger, self.local, rid, owner="issue-28-co", certificate=cert, observe=rg.observe_path,
                           remove=lambda _: self.fail("replacement deletion"), absent=lambda _: True, persist=lambda: None)
            self.assertTrue(target.exists())

    def test_alias_path_never_accepted(self):
        with tempfile.TemporaryDirectory(dir=TEMP_ROOT) as tmp:
            root = Path(tmp)
            (root / "actual").mkdir()
            try:
                (root / "alias").symlink_to(root / "actual", target_is_directory=True)
            except OSError:
                self.skipTest("host cannot create symlinks")
            with self.assertRaises(rg.ResourceError):
                rg.path_handle(root / "alias", root)

    def test_reparse_or_symlink_guard_is_deterministic_without_host_privileges(self):
        with tempfile.TemporaryDirectory(dir=TEMP_ROOT) as tmp:
            with patch.object(Path, "is_symlink", return_value=True):
                with self.assertRaises(rg.ResourceError):
                    rg.path_handle(tmp, tmp)

    def test_private_clone_marker_survives_legitimate_directory_outputs(self):
        with tempfile.TemporaryDirectory(dir=TEMP_ROOT) as tmp:
            root = Path(tmp)
            target = root / "clone"
            (target / ".git").mkdir(parents=True)
            handle = rg.register_clone(target, root)
            (target / "build-output").mkdir()
            self.assertEqual(rg.observe_path(handle), handle)
            with self.assertRaises(FileExistsError):
                rg.register_clone(target, root)
            (target / ".git/pleiad-resource-owner").write_text(str(uuid4()))
            self.assertNotEqual(rg.observe_path(handle), handle)

    def test_shared_store_rejects_another_cells_same_process_or_address(self):
        with tempfile.TemporaryDirectory(dir=TEMP_ROOT) as tmp:
            store = rg.LedgerStore(Path(tmp) / "first.json")
            with store.transaction({"ledger": self.ledger, "local": self.local}):
                pass
            other = rg.create(str(uuid4()), "issue-29-co", 0, SHA)
            other_local = {}
            rg.acquire(other, other_local, owner="issue-29-co", kind="server", name="other", handle=dict(self.handle, start_identity="reused"))
            with self.assertRaises(rg.ResourceError):
                with rg.LedgerStore(Path(tmp) / "second.json").transaction({"ledger": other, "local": other_local}):
                    pass

    def test_port_device_tunnel_need_actual_lease_and_replacement_blocks_cleanup(self):
        for kind, address in (("port", "address"), ("device", "device_identity"), ("tunnel", "tunnel_identity")):
            with self.subTest(kind=kind):
                handle = {address: "local-resource", "lease_identity": "lease-1"}
                rid = rg.acquire(self.ledger, self.local, owner="issue-28-co", kind=kind, name=kind, handle=handle)
                cert = self.guard(rid)
                with self.assertRaises(rg.ResourceError):
                    rg.cleanup(self.ledger, self.local, rid, owner="issue-28-co", certificate=cert,
                               observe=lambda h: dict(h, lease_identity="lease-2"), remove=lambda _: self.fail("foreign lease cleanup"),
                               absent=lambda _: True, persist=lambda: None)

    def test_public_allowlist_rejects_nested_handles_and_free_text(self):
        for mutation in (lambda x: x.update(workspace_path="C:/private"),
                         lambda x: x["resources"][0].update(notes={"pid": 123}),
                         lambda x: x["resources"][0].update(name="C:/private/clone"),
                         lambda x: x["resources"][0].update(name="device /tmp/private"),
                         lambda x: x["resources"][0].update(guard={"pid": 123})):
            bad = copy.deepcopy(self.ledger)
            mutation(bad)
            with self.assertRaises(rg.ResourceError):
                rg.public(bad)
        safe = json.dumps(rg.public(self.ledger))
        self.assertNotIn("123", safe)
        self.assertNotIn("start_identity", safe)

    def test_qa_final_receipt_requires_exact_boundary_source_and_ref_checks(self):
        clean = WorkspaceSnapshot(head=SHA, branch="", status=(), source_diff="", branch_refs=(("refs/heads/issue", SHA),),
                                  implementation_ref=("refs/heads/issue", SHA), git_common_dir="private-qa")
        result = verify_qa_workspace(clean, clean, expected_sha=SHA, implementation_branch="issue", implementation_repository_common_dir="private-im")
        evidence = cleanup_evidence(result, generation=0, final=True)
        self.assertEqual(evidence["sha"], SHA)
        self.assertTrue(all(evidence[k] is True for k in rg.CHECKS))
        self.assertNotIn("private", json.dumps(evidence))
        with tempfile.TemporaryDirectory(dir=TEMP_ROOT) as tmp:
            root = Path(tmp)
            (root / "qa").mkdir()
            rid = rg.acquire(self.ledger, self.local, owner="issue-28-co", kind="qa-clone", name="qa", handle=rg.path_handle(root / "qa", root))
            for key in rg.CHECKS:
                bad = dict(evidence, **{key: False})
                with self.subTest(key=key), self.assertRaises(rg.ResourceError):
                    rg.final_guard(self.ledger, rid, owner="issue-28-co", evidence=bad)
            rg.final_guard(self.ledger, rid, owner="issue-28-co", evidence=evidence)
            self.assertEqual(rg.certify(self.ledger, rid, owner="issue-28-co")["sha"], SHA)

    def demo(self, **kwargs):
        return rg.demo_exception(direct_owner=kwargs.pop("direct_owner", True), cell_id=self.ledger["cell_id"], sha=SHA,
                                 patch_digest="c" * 64, patch_uncommitted=True, rollback_digest="d" * 64, checks=["preview-checked"],
                                 resources=[self.rid], expires_at=1200, now=1000, max_restarts=1, **kwargs)

    def test_demo_has_no_inferred_publication_or_hosting_authority(self):
        with self.assertRaises(rg.ResourceError):
            self.demo(direct_owner=False)
        demo = self.demo()
        def action(kind, **kwargs):
            return rg.demo_action(demo, self.ledger, action=kind, resource_id=self.rid, now=kwargs.get("now", 1001),
                                  uncommitted_patch_digest=kwargs.get("patch", "c" * 64), patch_uncommitted=kwargs.get("uncommitted", True))
        self.assertTrue(action("preview"))  # No tunnel/hosting prerequisite.
        for kind in ("commit", "push", "publish", "merge", "release", "deploy", "tunnel"):
            with self.subTest(kind=kind), self.assertRaises(rg.ResourceError):
                action(kind)
        with self.assertRaises(rg.ResourceError):
            action("preview", uncommitted=False)
        self.assertTrue(action("restart"))
        with self.assertRaises(rg.ResourceError):
            action("restart")
        with self.assertRaises(rg.ResourceError):
            action("preview", patch="e" * 64)
        with self.assertRaises(rg.ResourceError):
            action("preview", now=1201)
        self.assertTrue(action("rollback", now=1201))
        self.assertFalse(demo["rolled_back"])
        with self.assertRaises(rg.ResourceError):
            rg.demo_rollback_receipt(demo, applied_rollback_digest="e" * 64, checks=["rollback-checked"])
        rg.demo_rollback_receipt(demo, applied_rollback_digest="d" * 64, checks=["rollback-checked"])
        self.assertTrue(demo["rolled_back"])

    def test_demo_rejects_wrong_cell_unowned_tunnel_and_oversized_scope(self):
        demo = self.demo()
        other = rg.create(str(uuid4()), "issue-29-co", 0, SHA)
        with self.assertRaises(rg.ResourceError):
            rg.demo_action(demo, other, action="preview", resource_id=self.rid, now=1001,
                           uncommitted_patch_digest="c" * 64, patch_uncommitted=True)
        tunnel = rg.acquire(self.ledger, self.local, owner="issue-28-co", kind="tunnel", name="unrelated-tunnel",
                            handle={"tunnel_identity": "private", "lease_identity": "lease-1"})
        demo["resources"].append(tunnel)
        with self.assertRaises(rg.ResourceError):
            rg.demo_action(demo, self.ledger, action="preview", resource_id=tunnel, now=1001,
                           uncommitted_patch_digest="c" * 64, patch_uncommitted=True)
        for options in ({"max_restarts": 4}, {"expires_at": 5000}, {"patch_uncommitted": False}, {"checks": []}):
            base = dict(direct_owner=True, cell_id=self.ledger["cell_id"], sha=SHA, patch_digest="c" * 64,
                        patch_uncommitted=True, rollback_digest="d" * 64, checks=["checked"], resources=[self.rid],
                        expires_at=1200, now=1000, max_restarts=1)
            with self.subTest(options=options), self.assertRaises(rg.ResourceError):
                rg.demo_exception(**dict(base, **options))


class ResourceAdoption(unittest.TestCase):
    def test_verified_schema4_upgrade_adds_resources_and_preserves_checkpoint(self):
        with tempfile.TemporaryDirectory(dir=TEMP_ROOT) as tmp:
            target = Path(tmp)
            _, writes, obsolete = managed.plan(target, "Example")
            managed.apply(target, writes, obsolete, "Example")
            manifest = json.loads((target / ".pleiad/managed.json").read_text())
            manifest["schema_version"] = 4
            manifest["files"] = {p: h for p, h in manifest["files"].items() if Path(p) in managed.MANIFEST_V4_MANAGED_PATHS}
            for p in set(managed.MANAGED_PATHS) - managed.MANIFEST_V4_MANAGED_PATHS:
                (target / p).unlink()
            (target / ".pleiad/managed.json").write_text(json.dumps(manifest))
            checkpoint = target / ".pleiad/current-cell.json"
            checkpoint.write_text('{"immutable":"preserve"}')
            before = checkpoint.read_bytes()
            actions, writes, obsolete = managed.plan(target, "Example")
            self.assertFalse([a for a in actions if a.classification == "conflict"])
            managed.apply(target, writes, obsolete, "Example")
            self.assertEqual(checkpoint.read_bytes(), before)
            self.assertEqual(managed.plan(target, "Example")[1], {})
            self.assertEqual(json.loads((target / ".pleiad/managed.json").read_text())["schema_version"], 5)
            (target / "scripts/resource_guards.py").write_text("project customization")
            actions, _, _ = managed.plan(target, "Example")
            self.assertIn(("conflict", "scripts/resource_guards.py"), {(a.classification, a.path.as_posix()) for a in actions})


if __name__ == "__main__":
    unittest.main()
