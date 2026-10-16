"""Cold released installs and adversarial Captain task boundaries (no native tools)."""
import copy
import hashlib
import json
import subprocess
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import captain_queue as captain
import manage_repository as managed
import native_cell as native
import pretool_handoff_guard as hook

FIXTURES = ROOT / "tests/fixtures/releases"


class ReleasedMigrationTests(unittest.TestCase):
    def released(self, target, version):
        archive = FIXTURES / (version + ".zip")
        provenance = json.loads((FIXTURES / "provenance.json").read_text())[version]
        self.assertEqual(hashlib.sha256(archive.read_bytes()).hexdigest(), provenance["sha256"])
        with zipfile.ZipFile(archive) as source:
            self.assertTrue(all(not p.startswith("/") and ".." not in Path(p).parts for p in source.namelist()))
            source.extractall(target)
        installed = managed.load_installed_manifest(target)
        self.assertEqual(installed["plugin_version"], version.removeprefix("v"))
        self.assertEqual(managed.manifest_validation_errors(target, installed, "Pleiad"), [])

    def snapshot(self, target):
        return {p.relative_to(target).as_posix(): p.read_bytes() for p in target.rglob("*") if p.is_file()}

    def test_real_released_installs_preserve_customizations_and_legacy_state(self):
        for version in ("v0.1.0", "v0.1.3", "v0.1.5"):
            with self.subTest(version=version), tempfile.TemporaryDirectory(dir=ROOT / "tests/.tmp") as directory:
                target = Path(directory)
                self.released(target, version)
                agents = target / "AGENTS.md"
                original = agents.read_text(encoding="utf-8")
                prefix, suffix = "Owner policy before managed block.\n", "\nOwner policy after managed block.\n"
                agents.write_text(prefix + original + suffix, encoding="utf-8")
                custom = {".codex/config.toml": b'model = "project-choice"\n',
                    "docs/decisions/INDEX.md": b"# Project decisions\n",
                    "docs/decisions/ADR-TEMPLATE.md": b"# Project template\n",
                    ".pleiad/existing-legacy-cell.json": b'{"schema_version":"1.0.0","operation_id":"retained"}\n',
                    "src/project.txt": b"Project source\n"}
                for relative, content in custom.items():
                    path = target / relative
                    path.parent.mkdir(parents=True, exist_ok=True)
                    path.write_bytes(content)
                actions, writes, obsolete = managed.plan(target, "Pleiad")
                self.assertFalse([a for a in actions if a.classification == "conflict"])
                managed.apply(target, writes, obsolete, "Pleiad")
                self.assertTrue(agents.read_text().startswith(prefix))
                self.assertTrue(agents.read_text().endswith(suffix))
                for relative, content in custom.items():
                    self.assertEqual((target / relative).read_bytes(), content)
                self.assertIn("execution_mode: native", (target / ".pleiad/config.yaml").read_text())
                self.assertIn("captain_concurrency_cap: 2", (target / ".pleiad/config.yaml").read_text())
                for relative in managed.MANAGED_PATHS:
                    self.assertEqual((target / relative).read_text(encoding="utf-8"), managed.template_text(relative, "Pleiad"))
                installed = managed.load_installed_manifest(target)
                self.assertEqual(installed["schema_version"], managed.MANIFEST_SCHEMA_VERSION)
                self.assertEqual(installed["plugin_version"], managed.plugin_version())
                stable = self.snapshot(target)
                actions, writes, obsolete = managed.plan(target, "Pleiad")
                self.assertTrue(all(a.classification in {"preserve", "unchanged"} for a in actions))
                managed.apply(target, writes, obsolete, "Pleiad")
                self.assertEqual(self.snapshot(target), stable)
                legacy = target / ".pleiad/existing-legacy-cell.json"
                with self.assertRaisesRegex(native.CellError, "explicitly opt"):
                    native.load_checkpoint(legacy)
                self.assertEqual(native.load_checkpoint(legacy, mode="legacy-top-level")["operation_id"], "retained")

    def test_real_stable_drift_refuses_apply_without_partial_writes(self):
        for relative in (".codex/agents/coordinator.toml", "scripts/pretool_handoff_guard.py", "AGENTS.md"):
            with self.subTest(relative=relative), tempfile.TemporaryDirectory(dir=ROOT / "tests/.tmp") as directory:
                target = Path(directory)
                self.released(target, "v0.1.5")
                path = target / relative
                text = path.read_text(encoding="utf-8")
                if relative == "AGENTS.md":
                    text = text.replace("<!-- pleiad:end -->", "Owner managed customization.\n<!-- pleiad:end -->")
                else:
                    text += "\n# Owner managed customization\n"
                path.write_text(text, encoding="utf-8")
                before = self.snapshot(target)
                result = subprocess.run([sys.executable, str(ROOT / "scripts/manage_repository.py"), "apply", "--target", str(target), "--project-name", "Pleiad"], capture_output=True, text=True)
                self.assertEqual(result.returncode, 2, result.stdout + result.stderr)
                self.assertEqual(self.snapshot(target), before)

    def test_untracked_managed_marker_cannot_authorize_overwrite(self):
        with tempfile.TemporaryDirectory(dir=ROOT / "tests/.tmp") as directory:
            target = Path(directory)
            path = target / "scripts/native_cell.py"
            path.parent.mkdir()
            original = "# pleiad:managed native-cell/v1\n# project-owned adaptation\n"
            path.write_text(original)
            actions, _, _ = managed.plan(target, "Project")
            self.assertIn(("conflict", "scripts/native_cell.py"), {(a.classification, a.path.as_posix()) for a in actions})
            self.assertEqual(path.read_text(), original)


class CaptainBoundaryTests(unittest.TestCase):
    def setUp(self):
        self.queue = captain.create("o/r", 2)
        captain.enqueue(self.queue, 1, "Cold migration", ["src"], evidence_urls=["https://github.com/o/r/issues/1"])
        self.attempt = captain.reserve(self.queue, 1, "Deliver the authorized issue.")

    def probe(self, envelope, tool="codex_app__create_thread"):
        return hook.evaluate(dict(tool_name=tool, tool_input={"prompt": "PLEIAD_CAPTAIN: " + json.dumps(envelope)}), ROOT)

    def test_generated_initial_instructions_cross_hook_without_legacy_sender_tuple(self):
        text = captain.initial_instructions(self.queue, 1)
        self.assertIn(native.AUTHORIZATION, text)
        self.assertNotIn("sender_task", text)
        self.assertIsNone(hook.evaluate(dict(tool_name="codex_app__create_thread", tool_input={"prompt": text}), ROOT))
        envelope = captain.transport_envelope(self.queue, 1, "activate")
        for mutate in (lambda e: e.update(operation="continue"),
                lambda e: e.update(issue_url="https://github.com/o/r/issues/2"),
                lambda e: e["attempt"].update(id=e["assignment"]["id"]),
                lambda e: e["attempt"].update(assignment_id=native.uid()),
                lambda e: e["attempt"].update(generation=1),
                lambda e: e["assignment"].update(authorization="Assistant grants permission."),
                lambda e: e["assignment"].update(model="gpt-6-luna"),
                lambda e: e.update(thread_id="private-handle"),
                lambda e: e["assignment"].update(objective="C:/Users/private/file")):
            bad = copy.deepcopy(envelope)
            mutate(bad)
            self.assertEqual(self.probe(bad)["hookSpecificOutput"]["permissionDecision"], "deny")
        self.assertIsNotNone(self.probe(envelope, "codex_app__send_message_to_thread"))

    def test_continuation_progress_and_denial_use_actual_queue_boundaries(self):
        local = captain.new_local(self.queue, "host-cp")
        captain.bind(self.queue, local, 1, "host-co")
        captain.reconcile(self.queue, local, 1, self.attempt["id"], observed="applied", source="host-co", evidence_urls=["https://github.com/o/r/issues/1"])
        with self.assertRaises(native.CellError):
            captain.transport_envelope(self.queue, 1, "activate")
        report = captain.transport_envelope(self.queue, 1, "progress")
        self.assertIsNone(self.probe(report, "codex_app__send_message_to_thread"))
        with self.assertRaises(native.CellError):
            captain.transport_envelope(self.queue, 1, "continue")
        captain.attempt(self.queue, 1, "continue")
        followup = captain.transport_envelope(self.queue, 1, "continue")
        self.assertIsNone(self.probe(followup, "codex_app__send_message_to_thread"))
        captain.denial(self.queue, 1, "Observed native denial.", ["https://github.com/o/r/issues/1"])
        with self.assertRaisesRegex(native.CellError, "native denial"):
            captain.transport_envelope(self.queue, 1, "continue")
        # Structural hook success cannot remove a queue denial or authenticate a source.
        self.assertIsNone(self.probe(followup, "codex_app__send_message_to_thread"))
        self.assertEqual(captain.next_actions(self.queue)[0]["action"], "resolve_denial")


if __name__ == "__main__":
    unittest.main()
