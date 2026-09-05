import unittest
from unittest.mock import patch, MagicMock
from r20_backend.council_manager import (
    load_council_config,
    save_council_config,
    reset_role_template,
    DEFAULT_PRESET_TEMPLATES,
    execute_council_debate,
)


class TestCouncilManager(unittest.TestCase):
    def test_load_and_save_council_config(self):
        cfg = load_council_config()
        self.assertIn("enabled", cfg)
        self.assertIn("roles", cfg)
        self.assertIn("alpha", cfg["roles"])
        self.assertIn("risk", cfg["roles"])
        self.assertIn("quant", cfg["roles"])
        self.assertIn("arbitrator", cfg["roles"])

        original_enabled = cfg["enabled"]
        cfg["enabled"] = not original_enabled
        saved = save_council_config(cfg)
        self.assertEqual(saved["enabled"], not original_enabled)

        # Restore original
        cfg["enabled"] = original_enabled
        save_council_config(cfg)

    def test_reset_role_template(self):
        cfg = reset_role_template("alpha")
        self.assertEqual(
            cfg["roles"]["alpha"]["prompt"],
            DEFAULT_PRESET_TEMPLATES["alpha"]["prompt"]
        )

    def test_consensus_mode_and_suites(self):
        from r20_backend.council_manager import get_preset_suites, apply_preset_suite
        suites = get_preset_suites()
        self.assertGreaterEqual(len(suites), 1)
        suite_ids = [s["id"] for s in suites]
        self.assertIn("full_spectrum", suite_ids)

        # Apply full spectrum suite
        updated = apply_preset_suite("full_spectrum")
        self.assertEqual(updated["consensus_mode"], "weighted")
        self.assertIn("alpha", updated["roles"])
        self.assertIn("risk", updated["roles"])
        self.assertIn("arbitrator", updated["roles"])

    def test_council_debate_execution_mocked(self):
        # Mock execute_llm_request to avoid making external HTTP calls
        mock_advisor_return = ("BUY_LONG 80% 置信度，动能良好", "", {}, 120)
        mock_arbitrator_json = (
            '{"macro_assessment": "宏观强势突破", "decisions": {"ETH-USDT-SWAP": {"action": "BUY_LONG", "confidence": 85}}, "position_management": []}',
            "",
            {},
            250
        )

        with patch("r20_backend.llm_manager.execute_llm_request") as mock_exec:
            # Set side effect: 3 advisors calls + 1 arbitrator call
            mock_exec.side_effect = [
                mock_advisor_return,
                mock_advisor_return,
                mock_advisor_return,
                mock_arbitrator_json,
            ]

            brain_output, transcript = execute_council_debate(
                market_prompt="BTC: 77000, ETH: 2400",
                original_system_prompt="system prompt",
                timeout=15.0,
            )

            self.assertIn("decisions", brain_output)
            self.assertEqual(brain_output["macro_assessment"], "宏观强势突破")
            self.assertIn("council_transcript", brain_output)
            self.assertTrue(transcript["council_mode"])
            self.assertIn("advisors", transcript)
            self.assertIn("alpha", transcript["advisors"])
            self.assertIn("risk", transcript["advisors"])
            self.assertIn("quant", transcript["advisors"])
            self.assertIn("arbitrator", transcript)


if __name__ == "__main__":
    unittest.main()
