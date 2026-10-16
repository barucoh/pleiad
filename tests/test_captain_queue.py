"""Captain skill behavior scenarios exercise actual admission/transport/cell runtime."""
import copy
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import captain_queue as cp
import native_cell as native
import manage_repository as managed
from coordination_protocol import format_session_title, validate_routing

SHA = "a" * 40
CHECKS = [{"name": "behavior", "status": "passed"}]
(ROOT / "tests/.tmp").mkdir(exist_ok=True)


class CaptainScenarios(unittest.TestCase):
    def setUp(self):
        self.queue = cp.create("o/r", 2)
        self.local = cp.new_local(self.queue, "host-observed-cp")

    def add(self, issue, paths=None, deps=(), state="open"):
        cp.enqueue(self.queue, issue, f"Issue {issue}", paths or [f"src/issue{issue}"], dependencies=deps, issue_state=state, evidence_urls=[f"https://github.com/o/r/issues/{issue}"])

    def activate(self, issue):
        a = cp.reserve(self.queue, issue, "Deliver authorized issue.")
        source = f"host-co-{issue}"
        cp.bind(self.queue, self.local, issue, source)
        cp.reconcile(self.queue, self.local, issue, a["id"], observed="applied", source=source, evidence_urls=[f"https://github.com/o/r/issues/{issue}"])
        return source

    def cell(self, issue, *, ready=False):
        cell = native.create("o/r", issue, f"codex/{issue}-work", SHA)
        cell["pr_url"] = f"https://github.com/o/r/pull/{issue}"
        local = {"coordinator": f"host-co-{issue}", "bindings": {}, "contexts": {}, "receipts": {}, "identity": native.digest(native.identity(cell)), "pr_url": cell["pr_url"]}
        if ready:
            self.finish_cell(cell, local)
        return cell, local

    def finish_cell(self, cell, local):
        for role in ("implementation", "qa", "reviewer"):
            a = native.assignment(cell, role, "Scoped independent work.", "gpt-6-luna" if role == "implementation" else "gpt-6.1-sol", "Low" if role == "implementation" else "Medium", "Scoped independent work.")
            source = f"host-{cell['issue_number']}-{role}"
            native.bind(cell, local, a["id"], source)
            r = native.result(a, cell["sha"], "ready" if role == "implementation" else "passed", [cell["pr_url"]], checks=CHECKS, final_guard=role == "qa")
            native.receive(cell, local, source, r)
        cell["ci"] = "passed"
        native.local_review_ready(cell, local)

    def observations(self):
        return {str(c["issue_number"]): dict(issue_url=c["issue_url"], issue_state=c["issue_state"], source=f"host-co-{c['issue_number']}", branch=c["branch"], pr_url=c["pr_url"], sha=c["sha"], cell_digest=c["progress"]["cell_digest"] if c["progress"] else "") for c in self.queue["cells"]}

    def observe(self, issue, cell, local, *, next_action="Activate independent QA and RV.", quiescent=False, blocker=""):
        cp.progress(self.queue, self.local, issue, f"host-co-{issue}", cell, cell_local=local, observed_sha=cell["sha"], observed_pr=cell["pr_url"], next_action=next_action, quiescent=quiescent, blocker=blocker, evidence_urls=[cell["issue_url"]])

    def test_two_independent_ready_cells_under_cap_and_completion_drives_owner_action(self):
        self.add(1)
        self.add(2)
        self.assertEqual([a["action"] for a in cp.next_actions(self.queue)], ["activate", "activate"])
        self.activate(1)
        self.activate(2)
        for issue in (1, 2):
            cell, local = self.cell(issue, ready=True)
            self.observe(issue, cell, local, next_action="Owner local review of PR and exact SHA.", quiescent=True)
        self.assertEqual([c["state"] for c in self.queue["cells"]], ["local_review_ready"] * 2)
        self.assertEqual([a["action"] for a in cp.next_actions(self.queue)], ["report", "report"])
        self.assertTrue(all(not c["lease"] and c["issue_state"] == "open" for c in self.queue["cells"]))
        for issue in (1, 2):
            with self.assertRaises(native.CellError):
                cp.reserve(self.queue, issue, "Duplicate completed cell.")

    def test_sequential_reservation_enforces_cap_even_if_candidate_list_had_two_ready(self):
        self.queue["cap"] = 1
        self.add(1)
        self.add(2)
        self.activate(1)
        with self.assertRaisesRegex(native.CellError, "cap reached"):
            cp.reserve(self.queue, 2, "Must wait.")
        self.assertIn("concurrency", cp.next_actions(self.queue)[1]["reason"])

    def test_ownership_overlap_ancestor_case_and_repository_wide(self):
        for paths in ((["src"], ["src/a.py"]), (["SRC/A.py"], ["src/a.py"]), (["."], ["docs/a.md"])):
            with self.subTest(paths=paths):
                self.setUp()
                self.add(1, paths[0])
                self.add(2, paths[1])
                self.activate(1)
                with self.assertRaisesRegex(native.CellError, "overlaps"):
                    cp.reserve(self.queue, 2, "Must wait.")
        for path in ("../src", "src/../a", "/tmp/a", "src//a", "C:/src", "src\\a", "src/*"):
            with self.subTest(path=path), self.assertRaises(native.CellError):
                cp.enqueue(cp.create("o/r"), 9, "Invalid claim", [path], evidence_urls=["https://github.com/o/r/issues/9"])

    def test_dependencies_distinguish_closed_from_local_review_and_reject_cycles(self):
        self.add(1)
        self.add(2, deps=[dict(issue_number=1, requires="closed")])
        self.add(3, deps=[dict(issue_number=1, requires="local_review_ready")])
        self.activate(1)
        cell, local = self.cell(1, ready=True)
        self.observe(1, cell, local, quiescent=False)
        with self.assertRaises(native.CellError):
            cp.reserve(self.queue, 3, "Needs quiescent certificate.")
        self.observe(1, cell, local, quiescent=True)
        with self.assertRaisesRegex(native.CellError, "requires closed"):
            cp.reserve(self.queue, 2, "Needs issue closure.")
        self.activate(3)
        self.add(1, state="closed")
        self.activate(2)
        q = cp.create("o/r")
        cp.enqueue(q, 1, "First", ["a"], dependencies=[dict(issue_number=2, requires="closed")], evidence_urls=["https://github.com/o/r/issues/1"])
        before = copy.deepcopy(q)
        with self.assertRaisesRegex(native.CellError, "cycle"):
            cp.enqueue(q, 2, "Second", ["b"], dependencies=[dict(issue_number=1, requires="closed")], evidence_urls=["https://github.com/o/r/issues/2"])
        self.assertEqual(q, before)

    def test_unknown_activation_restart_never_duplicates_or_frees_cap(self):
        self.queue["cap"] = 1
        self.add(1)
        self.add(2)
        a = cp.reserve(self.queue, 1, "Activation may have succeeded.")
        restored = json.loads(json.dumps(self.queue))
        self.assertEqual(cp.rehydrate(restored, self.local, self.observations())[0]["action"], "reconcile")
        for issue in (1, 2):
            with self.assertRaises(native.CellError):
                cp.reserve(restored, issue, "No duplicate or excess admission.")
        with self.assertRaises(native.CellError):
            cp.attempt(restored, 1, "activate")
        cp.bind(restored, self.local, 1, "actual-created-co")
        with self.assertRaisesRegex(native.CellError, "binding proves activation"):
            cp.reconcile(restored, self.local, 1, a["id"], observed="absent", evidence_urls=["https://github.com/o/r/issues/1"])
        cp.reconcile(restored, self.local, 1, a["id"], observed="applied", source="actual-created-co", evidence_urls=["https://github.com/o/r/issues/1"])
        with self.assertRaisesRegex(native.CellError, "successful activation"):
            cp.attempt(restored, 1, "activate")

    def test_failed_activation_needs_exact_attempt_reconciliation_before_retry(self):
        self.add(1)
        a = cp.reserve(self.queue, 1, "Create durable CO.")
        cp.reconcile(self.queue, self.local, 1, a["id"], observed="failed", evidence_urls=["https://github.com/o/r/issues/1"])
        with self.assertRaisesRegex(native.CellError, "reconcile failed/unknown"):
            cp.attempt(self.queue, 1, "activate")
        for identifier, urls in ((native.uid(), ["https://github.com/o/r/issues/1"]), (a["id"], ["https://github.com/other/repo/issues/1"])):
            with self.assertRaises(native.CellError):
                cp.reconcile(self.queue, self.local, 1, identifier, observed="absent", evidence_urls=urls)
        cp.reconcile(self.queue, self.local, 1, a["id"], observed="absent", evidence_urls=["https://github.com/o/r/issues/1"])
        retry = cp.attempt(self.queue, 1, "activate")
        self.assertNotEqual(retry["id"], a["id"])
        self.assertEqual(retry["assignment_id"], a["assignment_id"])

    def test_active_progress_directs_next_action_and_closure_does_not_drop_lease(self):
        self.add(1)
        self.activate(1)
        cell, local = self.cell(1)
        self.observe(1, cell, local, next_action="Recover missing QA after proven stopped execution.")
        self.assertEqual(cp.next_actions(self.queue)[0]["reason"], "Recover missing QA after proven stopped execution.")
        self.add(1, state="closed")
        self.assertTrue(cp.entry(self.queue, 1)["lease"])
        self.assertEqual(cp.next_actions(self.queue)[0]["action"], "reconcile_closed")
        self.observe(1, cell, local, quiescent=True)
        self.assertEqual(cp.entry(self.queue, 1)["state"], "closed")

    def test_bound_sources_current_head_and_native_receipts_required(self):
        self.add(1)
        self.activate(1)
        cell, local = self.cell(1, ready=True)
        bad = copy.deepcopy(local)
        bad["receipts"] = {}
        with self.assertRaisesRegex(native.CellError, "receipt"):
            self.observe(1, cell, bad, quiescent=True)
        with self.assertRaisesRegex(native.CellError, "head/PR"):
            cp.progress(self.queue, self.local, 1, "host-co-1", cell, cell_local=local, observed_sha="b" * 40, observed_pr=cell["pr_url"], next_action="Review.", evidence_urls=[cell["issue_url"]], quiescent=True)
        with self.assertRaisesRegex(native.CellError, "bound CO"):
            cp.progress(self.queue, self.local, 1, "host-observed-cp", cell, cell_local=local, observed_sha=SHA, observed_pr=cell["pr_url"], next_action="Review.", evidence_urls=[cell["issue_url"]])
        self.observe(1, cell, local, quiescent=True)
        observations = self.observations()
        cp.rehydrate(self.queue, self.local, observations)
        altered = copy.deepcopy(self.queue)
        altered["cells"][0]["ownership"] = ["elsewhere"]
        with self.assertRaisesRegex(native.CellError, "bound CO"):
            cp.rehydrate(altered, self.local, observations)
        observations["1"]["cell_digest"] = "edited"
        with self.assertRaisesRegex(native.CellError, "progress/head"):
            cp.rehydrate(self.queue, self.local, observations)
        with self.assertRaises(native.CellError):
            cp.rehydrate(self.queue, cp.new_local(self.queue, "host-observed-cp"), observations)

    def test_unknown_followup_preserves_applied_work_and_blocks_recovery(self):
        self.add(1)
        self.activate(1)
        cell, local = self.cell(1)
        self.observe(1, cell, local)
        before = copy.deepcopy(cp.entry(self.queue, 1)["progress"])
        a = cp.attempt(self.queue, 1)
        with self.assertRaisesRegex(native.CellError, "pending transport"):
            cp.recover(self.queue, self.local, 1, observed_status="stopped", evidence_urls=[cell["issue_url"]])
        cp.reconcile(self.queue, self.local, 1, a["id"], observed="absent", evidence_urls=[cell["issue_url"]])
        self.assertEqual(cp.entry(self.queue, 1)["progress"], before)
        cp.attempt(self.queue, 1)

    def test_recovery_preserves_cell_pr_assignment_and_retires_old_source(self):
        self.add(1)
        source = self.activate(1)
        cell, local = self.cell(1)
        self.observe(1, cell, local)
        original = cp.entry(self.queue, 1)["assignment"]["id"]
        with self.assertRaises(native.CellError):
            cp.recover(self.queue, self.local, 1, observed_status="timeout", evidence_urls=[cell["issue_url"]])
        recovery = cp.recover(self.queue, self.local, 1, observed_status="stopped", evidence_urls=[cell["issue_url"]])
        c = cp.entry(self.queue, 1)
        self.assertEqual(c["assignment"]["id"], original)
        self.assertEqual(c["assignment"]["generation"], 1)
        self.assertEqual(c["cell_id"], cell["cell_id"])
        with self.assertRaises(native.CellError):
            cp.bind(self.queue, self.local, 1, source)
        cp.bind(self.queue, self.local, 1, "observed-replacement-co")
        cp.reconcile(self.queue, self.local, 1, recovery["id"], observed="applied", source="observed-replacement-co", evidence_urls=[cell["issue_url"]])
        self.assertEqual(cp.next_actions(self.queue)[0]["action"], "inspect_co")

    def test_rv1_fully_ready_changed_sha_rechecks_cap_and_overlapping_ownership(self):
        for cap, claim in ((1, ["src/issue1"]), (2, ["src/issue1/nested.py"])):
            with self.subTest(cap=cap):
                self.setUp()
                self.queue["cap"] = cap
                self.add(1)
                self.add(2, claim)
                self.activate(1)
                cell, local = self.cell(1, ready=True)
                self.observe(1, cell, local, quiescent=True)
                self.activate(2)
                native.changed_head(cell, "b" * 40)
                self.finish_cell(cell, local)
                with self.assertRaisesRegex(native.CellError, "capacity/ownership"):
                    self.observe(1, cell, local, quiescent=True)
                c = cp.entry(self.queue, 1)
                self.assertEqual(c["sha"], SHA)
                self.assertTrue(c["reconciliation_required"])
                self.assertEqual(cp.next_actions(self.queue)[0]["action"], "reconcile")
                # Once the other owner is quiescent, the fully verified new head
                # can be admitted against the same CO/cell/PR identity.
                other, other_local = self.cell(2, ready=True)
                self.observe(2, other, other_local, quiescent=True)
                self.observe(1, cell, local, quiescent=True)
                self.assertEqual(cp.entry(self.queue, 1)["sha"], "b" * 40)
                self.assertFalse(cp.entry(self.queue, 1)["reconciliation_required"])

    def test_rv2_absent_replacement_cannot_continue_historical_activation(self):
        self.add(1)
        self.activate(1)
        cell, local = self.cell(1)
        self.observe(1, cell, local)
        a = cp.recover(self.queue, self.local, 1, observed_status="stopped", evidence_urls=[cell["issue_url"]])
        cp.reconcile(self.queue, self.local, 1, a["id"], observed="absent", evidence_urls=[cell["issue_url"]])
        before = copy.deepcopy(self.queue)
        with self.assertRaisesRegex(native.CellError, "current-generation"):
            cp.attempt(self.queue, 1, "continue")
        self.assertEqual(self.queue, before)
        self.assertEqual(cp.next_actions(self.queue)[0]["action"], "retry_activation")
        retry = cp.attempt(self.queue, 1, "activate")
        self.assertEqual(retry["generation"], 1)
        cp.bind(self.queue, self.local, 1, "replacement-co")
        cp.reconcile(self.queue, self.local, 1, retry["id"], observed="applied", source="replacement-co", evidence_urls=[cell["issue_url"]])
        self.assertEqual(cp.next_actions(self.queue)[0]["action"], "inspect_co")
        cp.attempt(self.queue, 1, "continue")

    def test_rv3_qa1_restart_requires_fresh_github_identity_before_ready_reuse(self):
        self.add(1)
        self.activate(1)
        cell, local = self.cell(1, ready=True)
        self.observe(1, cell, local, quiescent=True)
        observed = self.observations()
        cp.rehydrate(self.queue, self.local, observed)
        self.assertEqual(cp.next_actions(self.queue)[0]["action"], "report")
        for field, wrong in (("issue_url", "https://github.com/o/r/issues/9"), ("issue_state", "closed"), ("branch", "codex/other"), ("pr_url", "https://github.com/o/r/pull/9"), ("sha", "b" * 40)):
            for missing in (True, False):
                with self.subTest(field=field, missing=missing):
                    q = copy.deepcopy(self.queue)
                    evidence = copy.deepcopy(observed)
                    if missing:
                        evidence["1"].pop(field)
                    else:
                        evidence["1"][field] = wrong
                    with self.assertRaises(native.CellError):
                        cp.rehydrate(q, self.local, evidence)
                    self.assertTrue(cp.entry(q, 1)["reconciliation_required"])
                    self.assertEqual(cp.next_actions(q)[0]["action"], "reconcile")
                    # Fresh matching native/GitHub observations restore reuse.
                    cp.rehydrate(q, self.local, observed)
                    self.assertEqual(cp.next_actions(q)[0]["action"], "report")

    def test_rv3_qa1_changed_head_invalidates_dependency_until_reverified_progress(self):
        self.add(1)
        self.add(2, deps=[dict(issue_number=1, requires="local_review_ready")])
        self.activate(1)
        cell, local = self.cell(1, ready=True)
        self.observe(1, cell, local, quiescent=True)
        observed = self.observations()
        observed["1"]["sha"] = "b" * 40
        with self.assertRaisesRegex(native.CellError, "head changed"):
            cp.rehydrate(self.queue, self.local, observed)
        self.add(2, deps=[dict(issue_number=1, requires="local_review_ready")])
        with self.assertRaisesRegex(native.CellError, "requires local_review_ready"):
            cp.reserve(self.queue, 2, "Cannot consume stale readiness.")
        # Updating only the issue record must not clear stale cell evidence.
        self.add(1)
        self.assertTrue(cp.entry(self.queue, 1)["reconciliation_required"])
        native.changed_head(cell, "b" * 40)
        self.finish_cell(cell, local)
        self.observe(1, cell, local, quiescent=True)
        cp.rehydrate(self.queue, self.local, self.observations())
        self.activate(2)

    def test_native_denial_not_resolved_by_absent_dispatch(self):
        self.add(1)
        a = cp.reserve(self.queue, 1, "Create.")
        d = cp.denial(self.queue, 1, "Host denied activation.", ["https://github.com/o/r/issues/1"])
        cp.reconcile(self.queue, self.local, 1, a["id"], observed="absent", evidence_urls=["https://github.com/o/r/issues/1"])
        self.assertEqual(cp.next_actions(self.queue)[0]["action"], "resolve_denial")
        with self.assertRaisesRegex(native.CellError, "native denial"):
            cp.attempt(self.queue, 1, "activate")
        cp.resolve_denial(self.queue, 1, d["id"], ["https://github.com/o/r/issues/1#issuecomment-2"])
        cp.attempt(self.queue, 1, "activate")

    def test_initial_dispatch_authority_routing_naming_and_private_handle_boundary(self):
        self.add(1)
        cp.reserve(self.queue, 1, "Deliver issue.")
        text = cp.initial_instructions(self.queue, 1)
        self.assertIn(native.AUTHORIZATION, text)
        self.assertIn("scoped CP/CO native task messaging", text)
        self.assertIn("grants no platform permission", text)
        self.assertLessEqual(len(format_session_title(1, "CP", "Long project issue title " * 4)), 36)
        for model, effort, rationale, valid in (("gpt-6-astra", "Medium", "Supervise project.", True), ("gpt-6-astra", "High", "High concurrency risk.", True), ("gpt-6.1-sol", "Medium", "Supervise.", False), ("gpt-6-astra", "High", "Ordinary supervision.", False)):
            self.assertEqual(not validate_routing(dict(to_role="captain", target_model=model, effort=effort, rationale=rationale, execution_mode="durable", sandbox_mode="read-only")), valid)
        for key, value in (("thread_id", "private-thread"), ("workspace_path", "C:/private")):
            altered = copy.deepcopy(self.queue)
            altered[key] = value
            with self.assertRaises(native.CellError):
                cp.validate(altered)


class CaptainAdoption(unittest.TestCase):
    def test_verified_schema3_upgrade_adds_captain_and_preserves_native_checkpoint(self):
        with tempfile.TemporaryDirectory(dir=ROOT / "tests/.tmp") as directory:
            target = Path(directory)
            _, writes, obsolete = managed.plan(target, "Example")
            managed.apply(target, writes, obsolete, "Example")
            manifest = json.loads((target / ".pleiad/managed.json").read_text())
            manifest["schema_version"] = 3
            manifest["files"] = {p: h for p, h in manifest["files"].items() if Path(p) in managed.MANIFEST_V3_MANAGED_PATHS}
            for p in set(managed.MANAGED_PATHS) - managed.MANIFEST_V3_MANAGED_PATHS:
                (target / p).unlink()
            (target / ".pleiad/managed.json").write_text(json.dumps(manifest))
            checkpoint = target / ".pleiad/current-cell.json"
            checkpoint.write_text(json.dumps(native.create("o/r", 1, "codex/1", SHA)))
            before = checkpoint.read_bytes()
            actions, writes, obsolete = managed.plan(target, "Example")
            self.assertFalse([a for a in actions if a.classification == "conflict"])
            managed.apply(target, writes, obsolete, "Example")
            self.assertEqual(checkpoint.read_bytes(), before)
            self.assertEqual(cp.configured_cap(target), 2)
            self.assertTrue((target / "scripts/captain_queue.py").exists())
            self.assertEqual(managed.plan(target, "Example")[1], {})

    def test_cli_persists_reservation_and_rejects_reinitialization(self):
        with tempfile.TemporaryDirectory(dir=ROOT / "tests/.tmp") as directory:
            checkpoint = Path(directory) / "queue.json"
            spec = Path(directory) / "issue.json"
            spec.write_text(json.dumps(dict(issue_number=1, title="Work", ownership_paths=["src"], evidence_urls=["https://github.com/o/r/issues/1"])))
            base = [sys.executable, str(ROOT / "scripts/captain_queue.py"), "--checkpoint", str(checkpoint)]
            for args in (["init", "--repository", "o/r", "--cap", "1"], ["enqueue", "--spec", str(spec)], ["reserve", "--issue", "1", "--objective", "Deliver."]):
                run = subprocess.run(base + args, capture_output=True, text=True)
                self.assertEqual(run.returncode, 0, run.stderr)
            for args in (["init", "--repository", "o/r"], ["reserve", "--issue", "1", "--objective", "Duplicate."]):
                self.assertEqual(subprocess.run(base + args, capture_output=True).returncode, 2)
            self.assertEqual(json.loads(checkpoint.read_text())["cells"][0]["attempts"][0]["status"], "unknown")


if __name__ == "__main__":
    unittest.main()
