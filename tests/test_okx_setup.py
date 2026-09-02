"""Tests for OKX CLI install and runtime diagnostic endpoints."""
from __future__ import annotations

import unittest
from unittest.mock import patch

import sys
sys.path.insert(0, str(__import__("pathlib").Path(__file__).resolve().parents[1]))

from r20_backend.okx_setup import (
    diagnose_okx_runtime,
    install_okx_cli,
    check_node_npm,
    LATEST_VERSION,
)


class OkxInstallTests(unittest.TestCase):
    def test_check_node_npm_returns_paths_without_secrets(self):
        with patch("r20_backend.okx_setup.shutil.which", side_effect=["/usr/bin/node", "/usr/bin/npm", "/usr/local/bin/okx"]), \
             patch("r20_backend.okx_setup._run", side_effect=[
                 {"ok": True, "returncode": 0, "stdout": "v20.10.0", "stderr": ""},
                 {"ok": True, "returncode": 0, "stdout": "10.2.3", "stderr": ""},
                 {"ok": True, "returncode": 0, "stdout": "1.4.5", "stderr": ""},
             ]):
            result = check_node_npm()
        self.assertTrue(result["ready"])
        self.assertEqual(result["node_path"], "/usr/bin/node")
        self.assertEqual(result["node_version"], "20.10.0")
        self.assertEqual(result["npm_version"], "10.2.3")
        self.assertTrue(result["okx_installed"])
        self.assertTrue(result["okx_supported"])

    def test_check_node_npm_when_missing(self):
        with patch("r20_backend.okx_setup.shutil.which", return_value=None):
            result = check_node_npm()
        self.assertFalse(result["ready"])
        self.assertFalse(result["node_installed"])
        self.assertFalse(result["npm_installed"])

    def test_install_aborts_when_node_npm_missing(self):
        with patch("r20_backend.okx_setup.check_node_npm", return_value={
            "ready": False, "node_installed": False, "node_path": "",
            "node_version": "", "npm_installed": False, "npm_path": "", "npm_version": "",
        }):
            result = install_okx_cli()
        self.assertFalse(result["ok"])
        self.assertIn("Node.js/npm", result["detail"])

    def test_install_success_verifies_binary_and_version(self):
        responses = [
            {"ok": True, "returncode": 0, "stdout": "1.4.4", "stderr": ""},  # existing okx --version
            {"ok": True, "returncode": 0, "stdout": "", "stderr": ""},  # npm install
            {"ok": True, "returncode": 0, "stdout": "1.4.5", "stderr": ""},  # okx --version
        ]
        with patch("r20_backend.okx_setup.check_node_npm", return_value={
            "ready": True, "node_installed": True, "node_path": "/usr/bin/node",
            "node_version": "20.10.0", "npm_installed": True, "npm_path": "/usr/bin/npm",
            "npm_version": "10.2.3",
        }), patch("r20_backend.okx_setup._run", side_effect=responses), \
             patch("r20_backend.okx_setup.shutil.which", return_value="/usr/local/bin/okx"):
            result = install_okx_cli()
        self.assertTrue(result["ok"])
        self.assertEqual(result["version"], "1.4.5")
        self.assertEqual(result["path"], "/usr/local/bin/okx")
        self.assertEqual(result["previous_version"], "1.4.4")
        self.assertTrue(result["restart_gateway_recommended"])

    def test_transient_okx_503_is_reported_as_upstream_not_auth_failure(self):
        responses = [
            {"ok": True, "returncode": 0, "stdout": "1.4.5", "stderr": ""},
            {"ok": True, "returncode": 0, "stdout": '{"profiles":{}}', "stderr": ""},
            {"ok": True, "returncode": 0, "stdout": '{"status":"logged_in","site":"global","scopes":["market:read","demo:read","demo:trade"]}', "stderr": ""},
            {"ok": False, "returncode": 1, "stdout": "", "stderr": "HTTP 503 Service temporarily unavailable"},
        ]
        with patch("r20_backend.okx_setup.shutil.which", return_value="/usr/local/bin/okx"), patch("r20_backend.okx_setup._run", side_effect=responses):
            status=diagnose_okx_runtime("demo",False)
        self.assertFalse(status["ready"])
        self.assertTrue(any("上游" in item for item in status["issues"]))
        self.assertTrue(any("无需重新安装" in item for item in status["steps"]))

    def test_install_fails_when_npm_returns_error(self):
        with patch("r20_backend.okx_setup.check_node_npm", return_value={
            "ready": True, "node_installed": True, "node_path": "/usr/bin/node",
            "node_version": "20.10.0", "npm_installed": True, "npm_path": "/usr/bin/npm",
            "npm_version": "10.2.3",
        }), patch("r20_backend.okx_setup._run", return_value={
            "ok": False, "returncode": 1, "stdout": "", "stderr": "EACCES: permission denied",
        }):
            result = install_okx_cli()
        self.assertFalse(result["ok"])
        self.assertIn("EACCES", result["detail"])


if __name__ == "__main__":
    unittest.main()
