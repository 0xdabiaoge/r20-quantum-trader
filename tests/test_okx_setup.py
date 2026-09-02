from __future__ import annotations

import unittest
from unittest.mock import patch

from r20_backend.okx_setup import diagnose_okx_runtime


class OkxSetupTests(unittest.TestCase):
    def test_missing_cli_is_not_ready(self):
        with patch("r20_backend.okx_setup.shutil.which", return_value=None):
            status = diagnose_okx_runtime("demo", False)
        self.assertFalse(status["ready"])
        self.assertEqual(status["credential_source"], "none")
        self.assertTrue(any("CLI" in item for item in status["issues"]))

    def test_demo_oauth_requires_scopes_and_private_probe(self):
        calls = {
            "--version": {"ok": True, "returncode": 0, "stdout": "1.4.5", "stderr": ""},
            "config": {"ok": True, "returncode": 0, "stdout": '{"profiles":{}}', "stderr": ""},
            "auth": {"ok": True, "returncode": 0, "stdout": '{"status":"logged_in","site":"global","scopes":["market:read","demo:read","demo:trade"]}', "stderr": ""},
            "--demo": {"ok": True, "returncode": 0, "stdout": "[]", "stderr": ""},
        }
        def fake_run(command, timeout=12, env=None):
            return calls[command[1]]
        with patch("r20_backend.okx_setup.shutil.which", return_value="/usr/local/bin/okx"), patch("r20_backend.okx_setup._run", side_effect=fake_run):
            status = diagnose_okx_runtime("demo", False)
        self.assertTrue(status["ready"])
        self.assertEqual(status["credential_source"], "cli-oauth")
        self.assertTrue(status["oauth"]["ready_for_selected_mode"])

    def test_live_oauth_with_demo_only_scope_is_rejected(self):
        responses = [
            {"ok": True, "returncode": 0, "stdout": "1.4.5", "stderr": ""},
            {"ok": True, "returncode": 0, "stdout": '{"profiles":{}}', "stderr": ""},
            {"ok": True, "returncode": 0, "stdout": '{"status":"logged_in","site":"global","scopes":["market:read","demo:read","demo:trade"]}', "stderr": ""},
        ]
        with patch("r20_backend.okx_setup.shutil.which", return_value="/usr/local/bin/okx"), patch("r20_backend.okx_setup._run", side_effect=responses):
            status = diagnose_okx_runtime("live", False)
        self.assertFalse(status["ready"])
        self.assertFalse(status["oauth"]["ready_for_selected_mode"])
        self.assertTrue(any("LIVE" in item for item in status["issues"]))

    def test_static_key_source_still_requires_cli_and_probe(self):
        responses = [
            {"ok": True, "returncode": 0, "stdout": "1.4.5", "stderr": ""},
            {"ok": True, "returncode": 0, "stdout": '{"profiles":{}}', "stderr": ""},
            {"ok": False, "returncode": 1, "stdout": "", "stderr": "not logged in"},
            {"ok": True, "returncode": 0, "stdout": "[]", "stderr": ""},
        ]
        seen=[]
        def fake_run(command, timeout=12, env=None):
            seen.append((command,env)); return responses.pop(0)
        values={"PATH":"/usr/local/bin:/usr/bin","OKX_DEMO_API_KEY":"demo-ak","OKX_DEMO_SECRET_KEY":"demo-sk","OKX_DEMO_PASSPHRASE":"demo-pp"}
        with patch("r20_backend.okx_setup.shutil.which", return_value="/usr/local/bin/okx"), patch("r20_backend.okx_setup._run", side_effect=fake_run):
            status = diagnose_okx_runtime("demo", True, env=values)
        self.assertTrue(status["ready"])
        self.assertEqual(status["credential_source"], "static-v5-key")
        self.assertEqual(seen[-1][1]["OKX_API_KEY"],"demo-ak")
        self.assertEqual(seen[-1][1]["OKX_DEMO"],"1")


if __name__ == "__main__":
    unittest.main()
