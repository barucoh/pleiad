"""Envelope aliases preserve source precedence, even with conflicting inputs."""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from pretool_handoff_guard import extract_envelope


class EnvelopeTests(unittest.TestCase):
    aliases = ("captain_transport", "handoff", "envelope", "pleiad_handoff", "agentic_sdlc_handoff")

    def test_all_aliases_and_collisions_preserve_source_then_alias_order(self):
        for index, alias in enumerate(self.aliases):
            chosen = {"chosen": alias}
            with self.subTest(alias=alias):
                self.assertIs(extract_envelope({alias: chosen}), chosen)
                self.assertIs(extract_envelope({"metadata": {alias: chosen}}), chosen)
                # Any top-level alias wins over even the first metadata alias.
                payload = {alias: chosen, "metadata": {self.aliases[0]: {"wrong": True}}}
                self.assertIs(extract_envelope(payload), chosen)
                for later in self.aliases[index + 1:]:
                    for nested in (False, True):
                        source = {later: {"wrong": True}, alias: chosen}
                        payload = {"metadata": source} if nested else source
                        self.assertIs(extract_envelope(payload), chosen)

    def test_malformed_aliases_metadata_and_prompt_fallback(self):
        for invalid in (None, [], "text", 0, False):
            with self.subTest(invalid=invalid):
                self.assertEqual(extract_envelope({"handoff": invalid, "metadata": {"envelope": {}}}), {})
                self.assertEqual(extract_envelope({"metadata": invalid, "prompt": 'PLEIAD_HANDOFF: {"fallback": true}'}),
                                 {"fallback": True})
                self.assertIsNone(extract_envelope({"metadata": invalid, "prompt": invalid}))
        self.assertIsNone(extract_envelope(None))
        self.assertIsNone(extract_envelope([]))
        # Empty dictionaries are valid candidates, not missing values.
        chosen = {}
        self.assertIs(extract_envelope({"handoff": chosen, "prompt": '{"wrong": true}'}), chosen)
