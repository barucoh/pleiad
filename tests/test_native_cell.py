"""Native execution behavior, recovery, and managed adoption boundaries for #26."""
import copy
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import manage_repository as managed
import native_cell as native

SHA = "a" * 40
NEXT = "b" * 40
PR = "https://github.com/o/r/pull/2"
EVIDENCE = PR + "#issuecomment-1"
(ROOT / "tests/.tmp").mkdir(exist_ok=True)
CHECKS = [{"name": "behavior", "status": "passed"}]


class NativeCellTests(unittest.TestCase):
    def setUp(self):
        self.cell = native.create("o/r", 1, "codex/1-example", SHA)
        self.cell["pr_url"] = PR
        self.local = {"coordinator": "native-co", "bindings": {}}

    def assign(self, role, source=None):
        model = "gpt-6-luna" if role == "implementation" else "gpt-6.1-sol"
        effort = "Low" if role == "implementation" else "Medium"
        a = native.assignment(self.cell, role, "Scoped issue work.", model, effort, "Scoped independent work.")
        native.bind(self.cell, self.local, a["id"], source or "native-" + role)
        return a

    def receive(self, a, status, sha=None, **kwargs):
        r = native.result(a, sha or self.cell["sha"], status, [EVIDENCE], checks=CHECKS, **kwargs)
        native.receive(self.cell, self.local, "native-" + a["role"], r)
        return r

    def ready_im(self, sha=None, **kwargs):
        a = self.assign("implementation")
        return self.receive(a, "ready", sha=sha, **kwargs)

    def pass_all(self):
        self.receive(self.assign("qa"), "passed", final_guard=True)
        self.receive(self.assign("reviewer"), "passed")
        self.cell["ci"] = "passed"
        native.local_review_ready(self.cell, self.local)

    def test_complete_native_correction_loop_and_exact_head_recheck(self):
        self.ready_im()
        qa = self.assign("qa")
        self.receive(qa, "changes_requested", findings=[{"id": "qa-1", "description": "Missing behavior."}])
        original_generation = self.cell["generation"]
        im = self.assign("implementation")
        self.assertEqual(self.cell["generation"], original_generation + 1)
        self.assertEqual(self.cell["state"], "CORRECTION_ACTIVE")
        with self.assertRaisesRegex(native.CellError, "map incomplete"):
            self.receive(im, "ready", sha=NEXT)
        self.receive(im, "ready", sha=NEXT, fixes=[{"finding_id": "qa-1", "evidence": EVIDENCE}])
        self.pass_all()
        self.assertEqual(self.cell["state"], "LOCAL_REVIEW_READY")
        self.assertEqual(self.cell["sha"], NEXT)
        self.assertEqual(self.cell["pending_findings"], [])
        native.rehydrate(self.cell, self.local, observed_sha=NEXT, observed_pr=PR, observed_issue_url=self.cell["issue_url"], observed_branch=self.cell["branch"])
        native.changed_head(self.cell, "c" * 40)
        self.assertEqual(self.cell["ci"], "pending")
        with self.assertRaises(native.CellError):
            native.local_review_ready(self.cell, self.local)
        self.ready_im()
        self.pass_all()
        self.assertEqual(self.cell["generation"], 2)

    def test_initial_co_and_im_assignments_include_standing_authorization(self):
        co = native.assignment(self.cell, "coordinator", "Deliver the issue.", "gpt-6-astra", "Medium", "Coordinate independent work.")
        im = self.assign("implementation")
        for a in (co, im):
            instructions = native.initial_instructions(self.cell, a)
            self.assertIn(native.AUTHORIZATION, instructions)
            self.assertIn("No additional routine publication consent", instructions)
            self.assertIn("Only merge to main waits for explicit owner approval", instructions)
        with self.assertRaisesRegex(native.CellError, "Coordinator cannot"):
            native.result(co, SHA, "passed", [EVIDENCE])

    def test_assignment_routing_is_explicit_and_mutation_atomic(self):
        original = copy.deepcopy(self.cell)
        for model, effort, rationale in [("gpt-6-luna", "High", "Routine."), ("gpt-6.1-sol", "High", "Routine."), ("other", "Low", "Routine.")]:
            with self.assertRaises(native.CellError):
                native.assignment(self.cell, "implementation", "Implement.", model, effort, rationale)
            self.assertEqual(self.cell, original)
        with self.assertRaises(native.CellError):
            self.assign("qa")

    def test_coordinator_and_one_agent_cannot_impersonate_independent_roles(self):
        self.ready_im()
        qa = self.assign("qa")
        rv = native.assignment(self.cell, "reviewer", "Review.", "gpt-6.1-sol", "Medium", "Independent review.")
        for source in ("native-co", "native-implementation", "native-qa"):
            with self.assertRaises(native.CellError):
                native.bind(self.cell, self.local, rv["id"], source)
        r = native.result(qa, SHA, "passed", [EVIDENCE], checks=CHECKS, final_guard=True)
        for source in ("native-co", "native-reviewer", "unbound"):
            with self.assertRaises(native.CellError):
                native.receive(self.cell, self.local, source, r)
        r["role"] = "reviewer"
        with self.assertRaisesRegex(native.CellError, "role mismatch"):
            native.receive(self.cell, self.local, "native-qa", r)

    def test_same_im_owns_corrections_and_same_sha_advances_generation(self):
        self.ready_im()
        qa = self.assign("qa")
        self.receive(qa, "changes_requested", findings=[{"id": "q1", "description": "Fix."}])
        im = native.assignment(self.cell, "implementation", "Correct.", "gpt-6-luna", "Low", "Scoped correction.")
        with self.assertRaisesRegex(native.CellError, "same IM"):
            native.bind(self.cell, self.local, im["id"], "new-im")
        native.bind(self.cell, self.local, im["id"], "native-implementation")
        self.receive(im, "ready", fixes=[{"finding_id": "q1", "evidence": EVIDENCE}])
        self.cell["ci"] = "passed"
        with self.assertRaises(native.CellError):
            native.local_review_ready(self.cell, self.local)

    def test_stale_result_replay_and_missing_final_guard_are_rejected(self):
        self.ready_im()
        qa = self.assign("qa")
        rv = self.assign("reviewer")
        with self.assertRaisesRegex(native.CellError, "final guard"):
            self.receive(qa, "passed")
        r = self.receive(qa, "passed", final_guard=True)
        with self.assertRaisesRegex(native.CellError, "already applied"):
            native.receive(self.cell, self.local, "native-qa", r)
        native.changed_head(self.cell, NEXT)
        with self.assertRaisesRegex(native.CellError, "stale assignment generation"):
            self.receive(rv, "passed", sha=NEXT)

    def test_resume_detects_altered_results_and_observed_identity(self):
        self.ready_im()
        self.pass_all()
        for sha, pr in ((NEXT, PR), (SHA, PR + "0")):
            with self.assertRaisesRegex(native.CellError, "head/PR"):
                native.rehydrate(self.cell, self.local, observed_sha=sha, observed_pr=pr, observed_issue_url=self.cell["issue_url"], observed_branch=self.cell["branch"])
        altered = copy.deepcopy(self.cell)
        altered["results"][-1]["evidence"] = [PR + "#issuecomment-999"]
        with self.assertRaisesRegex(native.CellError, "receipt"):
            native.rehydrate(altered, self.local, observed_sha=SHA, observed_pr=PR, observed_issue_url=self.cell["issue_url"], observed_branch=self.cell["branch"])
        with self.assertRaises(native.CellError):
            native.rehydrate(self.cell, {"bindings": {}}, observed_sha=SHA, observed_pr=PR, observed_issue_url=self.cell["issue_url"], observed_branch=self.cell["branch"])
        altered = copy.deepcopy(self.cell)
        altered["results"][-1]["sha"] = NEXT
        with self.assertRaisesRegex(native.CellError, "stale"):
            native.validate(altered)

    def test_unknown_recipient_never_replays_applied_event_or_clears_denial(self):
        self.ready_im()
        qa = self.assign("qa")
        rv = self.assign("reviewer")
        parent = self.cell["events"][-1]
        q = native.delivery(self.cell, parent["id"], qa["id"])
        r = native.delivery(self.cell, parent["id"], rv["id"])
        native.reconcile(self.cell, q["id"], "applied")
        denied = native.denial(self.cell, "Native permission denied.")
        native.reconcile(self.cell, r["id"], "absent")
        self.assertEqual(len(self.cell["events"]), 1)
        self.assertEqual(self.cell["denials"][-1]["status"], "unresolved")
        with self.assertRaisesRegex(native.CellError, "supported resolution"):
            self.receive(qa, "passed", final_guard=True)
        native.resolve_denial(self.cell, denied["id"], EVIDENCE)
        self.receive(qa, "passed", final_guard=True)
        self.receive(rv, "passed")
        self.cell["ci"] = "passed"
        native.local_review_ready(self.cell, self.local)
        with self.assertRaises(native.CellError):
            native.reconcile(self.cell, r["id"], "applied")
        altered = copy.deepcopy(self.cell)
        altered["events"].append(parent)
        with self.assertRaisesRegex(native.CellError, "replay"):
            native.validate(altered)

    def test_rv2_readiness_idempotence_unknown_retry_and_terminal_notification(self):
        self.ready_im()
        qa = self.assign("qa")
        d = native.delivery(self.cell, self.cell["events"][-1]["id"], qa["id"])
        with self.assertRaisesRegex(native.CellError, "unknown recipient"):
            native.delivery(self.cell, d["event_id"], qa["id"])
        native.reconcile(self.cell, d["id"], "absent")
        retry = native.delivery(self.cell, d["event_id"], qa["id"])
        self.assertNotEqual(d["id"], retry["id"])
        native.reconcile(self.cell, retry["id"], "applied")
        self.assertEqual(native.delivery(self.cell, d["event_id"], qa["id"])["id"], retry["id"])
        self.receive(qa, "passed", final_guard=True)
        self.receive(self.assign("reviewer"), "passed")
        self.cell["ci"] = "passed"
        native.local_review_ready(self.cell, self.local)
        before = copy.deepcopy(self.cell)
        native.local_review_ready(self.cell, self.local)
        self.assertEqual(self.cell, before)
        terminal = self.cell["events"][-1]
        native.delivery(self.cell, terminal["id"], qa["id"])
        self.assertEqual(self.cell["state"], "LOCAL_REVIEW_READY")
        native.validate(self.cell)

    def test_rv3_resume_seals_identity_assignments_and_pending_sources(self):
        im = self.assign("implementation")
        observations = dict(observed_sha=SHA, observed_pr=PR,
            observed_issue_url=self.cell["issue_url"], observed_branch=self.cell["branch"])
        native.rehydrate(self.cell, self.local, **observations)
        for mutation in (lambda c: c.update(branch="codex/unrelated"),
                lambda c: c.update(issue_number=2, issue_url="https://github.com/o/r/issues/2"),
                lambda c: c["assignments"][0].update(objective="Changed objective.")):
            altered = copy.deepcopy(self.cell)
            mutation(altered)
            changed_observations = {**observations, "observed_issue_url": altered["issue_url"], "observed_branch": altered["branch"]}
            with self.assertRaises(native.CellError):
                native.rehydrate(altered, self.local, **changed_observations)
        missing = copy.deepcopy(self.local)
        missing["bindings"] = {}
        with self.assertRaisesRegex(native.CellError, "pending specialist"):
            native.rehydrate(self.cell, missing, **observations)

    def test_rv4_first_pr_is_sealed_and_modified_checkpoint_cannot_reuse_verification(self):
        # IM can be assigned before publication; the first nonempty PR seals once.
        self.cell["pr_url"] = ""
        im = self.assign("implementation")
        self.assertEqual(self.local["pr_url"], "")
        self.cell["pr_url"] = PR
        self.receive(im, "ready")
        self.assertEqual(self.local["pr_url"], PR)
        self.pass_all()
        changed = copy.deepcopy(self.cell)
        changed["pr_url"] = "https://github.com/o/r/pull/999"
        observations = dict(observed_sha=SHA, observed_pr=changed["pr_url"],
            observed_issue_url=changed["issue_url"], observed_branch=changed["branch"])
        with self.assertRaisesRegex(native.CellError, "sealed PR"):
            native.rehydrate(changed, self.local, **observations)
        with self.assertRaisesRegex(native.CellError, "sealed PR"):
            native.local_review_ready(changed, self.local)
        # Even replacing the local PR label cannot reuse the original result receipts.
        altered_local = copy.deepcopy(self.local)
        altered_local["pr_url"] = changed["pr_url"]
        with self.assertRaisesRegex(native.CellError, "receipt"):
            native.rehydrate(changed, altered_local, **observations)
        with self.assertRaisesRegex(native.CellError, "receipt"):
            native.local_review_ready(changed, altered_local)
        native.changed_head(changed, NEXT)
        new_im = native.assignment(changed, "implementation", "Recheck.", "gpt-6-luna", "Low", "Scoped recheck.")
        with self.assertRaisesRegex(native.CellError, "sealed PR"):
            native.bind(changed, self.local, new_im["id"], "native-implementation")
        pending = native.result(im, SHA, "ready", [EVIDENCE], checks=CHECKS)
        with self.assertRaisesRegex(native.CellError, "sealed PR"):
            native.receive(changed, self.local, "native-implementation", pending)

    def test_proven_lost_agent_recovery_requires_absent_results_and_keeps_applied_work(self):
        im = self.assign("implementation")
        args = dict(observed_status="lost-confirmed", pending_observations={im["id"]: "absent"}, evidence=[EVIDENCE])
        with self.assertRaises(native.CellError):
            native.recover_agent(self.cell, self.local, "native-implementation", "replacement-im", **{**args, "pending_observations": {}})
        with self.assertRaises(native.CellError):
            native.recover_agent(self.cell, self.local, "native-implementation", "replacement-im", **{**args, "observed_status": "timeout"})
        native.recover_agent(self.cell, self.local, "native-implementation", "replacement-im", **args)
        record = native.result(im, SHA, "ready", [EVIDENCE], checks=CHECKS)
        with self.assertRaises(native.CellError):
            native.receive(self.cell, self.local, "native-implementation", record)
        native.receive(self.cell, self.local, "replacement-im", record)
        self.assertEqual(len(self.cell["results"]), 1)
        with self.assertRaises(native.CellError):
            native.receive(self.cell, self.local, "replacement-im", record)

    def test_rv1_https_urls_and_private_windows_paths(self):
        native.validate(self.cell)  # https:// must not match a Windows drive.
        for path in ("C:/Users/private/file", "C:\\Users\\private\\file", "\\\\server\\private", "/home/private/file"):
            with self.assertRaisesRegex(native.CellError, "private absolute"):
                native._portable({"objective": path})

    def test_private_or_malformed_result_rejected_without_state_change(self):
        self.ready_im()
        qa = self.assign("qa")
        original = copy.deepcopy(self.cell)
        base = native.result(qa, SHA, "passed", [EVIDENCE], checks=CHECKS, final_guard=True)
        mutations = [lambda r: r.update(agent_id="private-handle"),
            lambda r: r.update(evidence=["C:/Users/private/evidence.json"]),
            lambda r: r.update(findings=[{"id": "p", "description": "C:/Users/private/data"}]),
            lambda r: r.update(sha=NEXT), lambda r: r.update(role="coordinator"),
            lambda r: r.update(status="ready"), lambda r: r.update(checks=[])]
        for mutate in mutations:
            r = copy.deepcopy(base)
            mutate(r)
            with self.assertRaises(native.CellError):
                native.receive(self.cell, self.local, "native-qa", r)
            self.assertEqual(self.cell, original)
        for malformed in (None, [], {}, {"assignment_id": qa["id"]}):
            with self.assertRaises(native.CellError):
                native.receive(self.cell, self.local, "native-qa", malformed)
            self.assertEqual(self.cell, original)
        self.cell["assignments"][-1]["objective"] = "Altered assignment."
        with self.assertRaisesRegex(native.CellError, "context changed"):
            native.receive(self.cell, self.local, "native-qa", base)

    def test_checkpoint_roundtrip_and_explicit_legacy_opt_in(self):
        with tempfile.TemporaryDirectory(dir=ROOT / "tests/.tmp") as directory:
            path = Path(directory) / "checkpoint.json"
            native.save_checkpoint(self.cell, path)
            self.assertEqual(native.load_checkpoint(path), self.cell)
            path.write_text(json.dumps({"schema_version": "1.0.0", "operation_id": "old"}))
            with self.assertRaisesRegex(native.CellError, "explicitly opt"):
                native.load_checkpoint(path)
            original = path.read_bytes()
            self.assertEqual(native.load_checkpoint(path, mode="legacy-top-level")["operation_id"], "old")
            self.assertEqual(path.read_bytes(), original)
            path.write_text('{"schema_version":"native-cell/v1"}')
            with self.assertRaises(native.CellError):
                native.load_checkpoint(path)

    def test_cli_mechanically_generates_instructions_and_prevents_duplicate_init(self):
        with tempfile.TemporaryDirectory(dir=ROOT / "tests/.tmp") as directory:
            path = Path(directory) / "checkpoint.json"
            base = [sys.executable, str(ROOT / "scripts/native_cell.py"), "--checkpoint", str(path)]
            init = ["init", "--repository", "o/r", "--issue-number", "1", "--branch", "codex/1-change", "--sha", SHA]
            self.assertEqual(subprocess.run(base + init, capture_output=True).returncode, 0)
            self.assertEqual(subprocess.run(base + init, capture_output=True).returncode, 2)
            run = subprocess.run(base + ["assign", "--role", "implementation", "--objective", "Implement.", "--model", "gpt-6-luna", "--effort", "Low", "--rationale", "Routine work.", "--instructions"], capture_output=True, text=True)
            self.assertEqual(run.returncode, 0, run.stderr)
            self.assertIn(native.AUTHORIZATION, run.stdout)
            self.assertNotIn("source_task_key", run.stdout)


class NativeAdoptionTests(unittest.TestCase):
    def test_previous_schema2_015_path_set_upgrades_without_converting_legacy_checkpoint(self):
        with tempfile.TemporaryDirectory(dir=ROOT / "tests/.tmp") as directory:
            target = Path(directory)
            # Build a pristine previous path-set fixture without depending on Git history
            # (CI uses a shallow checkout). Version and hashes are recorded as installed.
            _, writes, obsolete = managed.plan(target, "Pleiad")
            managed.apply(target, writes, obsolete, "Pleiad")
            manifest = json.loads((target / ".pleiad/managed.json").read_text())
            manifest["schema_version"] = 2
            manifest["files"] = {p: h for p, h in manifest["files"].items() if Path(p) in managed.MANIFEST_V2_MANAGED_PATHS}
            for relative in set(managed.MANAGED_PATHS) - managed.MANIFEST_V2_MANAGED_PATHS:
                (target / relative).unlink()
            (target / ".pleiad/managed.json").write_text(json.dumps(manifest))
            checkpoint = target / ".pleiad/existing-cell.json"
            checkpoint.write_text('{"schema_version":"1.0.0","operation_id":"keep"}')
            before = checkpoint.read_bytes()
            actions, writes, obsolete = managed.plan(target, "Pleiad")
            self.assertFalse([a for a in actions if a.classification == "conflict"])
            managed.apply(target, writes, obsolete, "Pleiad")
            self.assertIn("execution_mode: native", (target / ".pleiad/config.yaml").read_text())
            self.assertEqual(checkpoint.read_bytes(), before)
            self.assertEqual(json.loads((target / ".pleiad/managed.json").read_text())["schema_version"], 3)
            self.assertFalse([a for a in managed.plan(target, "Pleiad")[0] if a.classification not in {"unchanged", "preserve"}])

    def test_native_managed_files_appear_in_fresh_bootstrap_and_modified_owner_file_conflicts(self):
        with tempfile.TemporaryDirectory(dir=ROOT / "tests/.tmp") as directory:
            target = Path(directory)
            actions, writes, obsolete = managed.plan(target, "Fixture")
            self.assertFalse([a for a in actions if a.classification == "conflict"])
            managed.apply(target, writes, obsolete, "Fixture")
            for relative in ("scripts/native_cell.py", ".pleiad/native-cell.schema.json", "docs/pleiad/legacy-coordination.md"):
                self.assertTrue((target / relative).is_file())
            path = target / "scripts/native_cell.py"
            original = path.read_text() + "\n# owner customization\n"
            path.write_text(original)
            self.assertTrue([a for a in managed.plan(target, "Fixture")[0] if a.classification == "conflict"])
            self.assertEqual(path.read_text(), original)


if __name__ == "__main__":
    unittest.main()
