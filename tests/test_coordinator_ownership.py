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
            text = (manage_repository.TEMPLATES / relative).read_text(encoding="utf-8")
            with self.subTest(path=relative):
                for phrase in ("host/tool permission", "plugin grants no permissions",
                               "human", "Coordinator", "copy/paste", "recovery"):
                    self.assertIn(phrase.lower(), text.lower())
                self.assertIn("native task messaging", text)
        for relative in ("skills/coordinate-pleiad/SKILL.md", "skills/bootstrap-pleiad/SKILL.md",
                         "skills/upgrade-pleiad/SKILL.md", "README.md", "docs/upgrading.md"):
            text = (ROOT / relative).read_text(encoding="utf-8")
            with self.subTest(path=relative):
                for phrase in ("persistent home task", "coordination chain", "one actionable human blocker",
                               "last-resort recovery artifact", "voluntary inspection",
                               "scoped internal peer coordination", "independent QA/review"):
                    self.assertIn(phrase, text)
        contracts = {}
        for role in ("coordinator", "implementation", "qa", "reviewer"):
            path = manage_repository.TEMPLATES / f".codex/agents/{role}.toml"
            contracts[role] = tomllib.loads(path.read_text(encoding="utf-8"))["developer_instructions"]
        self.assertIn("do not relay routine", contracts["coordinator"])
        self.assertIn("persistent home task", contracts["coordinator"])
        self.assertNotIn("Return control to the human owner when delivery is ready or blocked", contracts["coordinator"])
        self.assertIn("IMPLEMENTATION_READY directly", contracts["implementation"])
        self.assertIn("directly to the bound Reviewer and same Implementation", contracts["qa"])
        self.assertIn("CHANGES_REQUESTED directly to the same IM", contracts["reviewer"])
        for role in ("implementation", "qa", "reviewer"):
            self.assertIn("must not ask the human to copy prompts, open peer tasks", contracts[role])
            self.assertIn("Escalate unavailable task control", contracts[role])

    def test_fresh_and_pristine_previous_patch_receive_policy_idempotently(self):
        candidate_version = manage_repository.plugin_version()
        original_template = manage_repository.template_text
        previous_agents = manage_repository.desired_agents_text().replace("native task messaging", "native task transport")
        def previous_template(relative, project_name):
            text = original_template(relative, project_name)
            if relative == Path(".pleiad/config.yaml"):
                return text.replace(f"applied_plugin_version: {candidate_version}", "applied_plugin_version: 0.1.4")
            if relative in self.policy_paths:
                # Model a recognized pristine prior contract without the new instruction.
                return text.replace("native task messaging", "native task transport")
            return text

        for upgrade in (False, True):
            with self.subTest(upgrade=upgrade), tempfile.TemporaryDirectory() as directory:
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
                    self.assertIn("native task messaging", (target / relative).read_text(encoding="utf-8"))
                self.assertEqual(json.loads((target / ".pleiad/managed.json").read_text())["plugin_version"], candidate_version)
                final, _, _ = manage_repository.plan(target, "Policy Fixture")
                self.assertFalse([a for a in final if a.classification not in {"unchanged", "preserve"}])

    def test_upgrade_preserves_modified_contract_as_conflict(self):
        with tempfile.TemporaryDirectory() as directory:
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
