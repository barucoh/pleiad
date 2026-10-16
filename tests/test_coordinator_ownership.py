"""Issue #24 instruction boundaries and managed adoption regression coverage."""

import json
import sys
import tempfile
import tomllib
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import manage_repository


class CoordinatorOwnershipTests(unittest.TestCase):
    policy_paths = (
        Path("AGENTS.md"),
        Path("docs/pleiad/coordination.md"),
        Path("docs/pleiad/role-contracts.md"),
        *(Path(f".codex/agents/{role}.toml") for role in
          ("coordinator", "implementation", "qa", "reviewer")),
    )

    def test_instruction_contract_preserves_authority_and_recovery(self):
        for relative in self.policy_paths:
            text = (manage_repository.TEMPLATES / relative).read_text(encoding="utf-8").lower()
            with self.subTest(path=relative):
                for phrase in ("host/tool permission", "plugin grants no permissions", "human", "coordinator", "recovery", "native"):
                    self.assertIn(phrase, text)
                self.assertNotIn("never as an ephemeral subagent", text)
        for relative in ("skills/coordinate-pleiad/SKILL.md", "skills/bootstrap-pleiad/SKILL.md",
                         "skills/upgrade-pleiad/SKILL.md", "README.md", "docs/upgrading.md"):
            text = (ROOT / relative).read_text(encoding="utf-8").lower()
            with self.subTest(path=relative):
                for phrase in ("coordination chain", "one actionable human blocker", "last-resort recovery artifact",
                               "voluntary inspection", "scoped internal peer coordination", "independent qa/review"):
                    self.assertIn(phrase, text)
        for role in ("coordinator", "implementation", "qa", "reviewer"):
            path = manage_repository.TEMPLATES / f".codex/agents/{role}.toml"
            contract = tomllib.loads(path.read_text(encoding="utf-8"))
            self.assertNotIn("sandbox_mode", contract)
            text = contract["developer_instructions"].lower()
            self.assertIn("subagents inherit parent sandbox", text)
            self.assertIn("only im writes project files or commits", text)
            self.assertIn("explicit legacy-top-level opt-in", text)
        co = (manage_repository.TEMPLATES / ".codex/agents/coordinator.toml").read_text().lower()
        self.assertIn("never author qa/rv verdicts", co)
        self.assertIn("standing authorization", co)

    def test_fresh_and_pristine_previous_patch_receive_policy_idempotently(self):
        candidate_version = manage_repository.plugin_version()
        original_template = manage_repository.template_text
        previous_agents = manage_repository.desired_agents_text().replace("Native task messaging", "Native task transport")
        def previous_template(relative, project_name):
            text = original_template(relative, project_name)
            if relative == Path(".pleiad/config.yaml"):
                return text.replace(f"applied_plugin_version: {candidate_version}", "applied_plugin_version: 0.1.4")
            if relative in self.policy_paths:
                # Model a recognized pristine prior contract without the new instruction.
                return text + "\n# Previous pristine policy\n"
            return text

        for upgrade in (False, True):
            with self.subTest(upgrade=upgrade), tempfile.TemporaryDirectory(dir=ROOT / "tests/.tmp") as directory:
                target = Path(directory)
                if upgrade:
                    with patch.object(manage_repository, "plugin_version", return_value="0.1.4"), \
                         patch.object(manage_repository, "template_text", side_effect=previous_template), \
                         patch.object(manage_repository, "desired_agents_text", return_value=previous_agents):
                        _, writes, obsolete = manage_repository.plan(target, "Policy Fixture")
                        manage_repository.apply(target, writes, obsolete, "Policy Fixture")
                    self.assertEqual(json.loads((target / ".pleiad/managed.json").read_text())["plugin_version"], "0.1.4")
                actions, writes, obsolete = manage_repository.plan(target, "Policy Fixture")
                self.assertFalse([a for a in actions if a.classification == "conflict"])
                if upgrade:
                    changed = {a.path for a in actions if a.classification in {"update", "managed-block-update"}}
                    self.assertTrue(set(self.policy_paths).issubset(changed))
                manage_repository.apply(target, writes, obsolete, "Policy Fixture")
                for relative in self.policy_paths:
                    self.assertIn("native task messaging", (target / relative).read_text(encoding="utf-8").lower())
                self.assertEqual(json.loads((target / ".pleiad/managed.json").read_text())["plugin_version"], candidate_version)
                final, _, _ = manage_repository.plan(target, "Policy Fixture")
                self.assertFalse([a for a in final if a.classification not in {"unchanged", "preserve"}])

    def test_upgrade_preserves_modified_contract_as_conflict(self):
        with tempfile.TemporaryDirectory(dir=ROOT / "tests/.tmp") as directory:
            target = Path(directory)
            _, writes, obsolete = manage_repository.plan(target, "Policy Fixture")
            manage_repository.apply(target, writes, obsolete, "Policy Fixture")
            relative = Path(".codex/agents/coordinator.toml")
            path = target / relative
            customized = path.read_text(encoding="utf-8") + "\n# Project customization\n"
            path.write_text(customized, encoding="utf-8")
            actions, _, _ = manage_repository.plan(target, "Policy Fixture")
            self.assertIn(("conflict", relative), {(a.classification, a.path) for a in actions})
            self.assertEqual(path.read_text(encoding="utf-8"), customized)
