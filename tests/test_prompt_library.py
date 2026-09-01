"""Prompt library style and Python direct-rendering tests."""
from __future__ import annotations
import tempfile
import unittest
from pathlib import Path

import scripts.prompt_library as library


class PromptLibraryTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.original = library.LIBRARY_FILE
        library.LIBRARY_FILE = Path(self.temp.name) / "prompt_library.json"

    def tearDown(self):
        library.LIBRARY_FILE = self.original
        self.temp.cleanup()

    def test_default_is_stable_and_presets_have_four_templates(self):
        self.assertEqual(library.load_library()["active_style"], "stable")
        for profile in library.all_profiles():
            for key in ("trading_system", "trading_user", "evolution_system", "evolution_user"):
                self.assertIn(key, profile)

    def test_custom_profile_round_trip(self):
        payload = library.load_library()
        payload["active_style"] = "custom"
        payload["custom"]["trading_system"] = "CUSTOM_STYLE"
        library.save_library(payload)
        self.assertEqual(library.active_profile()["trading_system"], "CUSTOM_STYLE")

    def test_append_layer_preserves_base(self):
        rendered = library.append_layer("HARD_RISK_RULES", "STYLE_LAYER", "风格")
        self.assertTrue(rendered.startswith("HARD_RISK_RULES"))
        self.assertIn("STYLE_LAYER", rendered)


if __name__ == "__main__":
    unittest.main()
