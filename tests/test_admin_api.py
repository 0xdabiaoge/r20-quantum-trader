"""Administrator API RBAC tests using an isolated auth database."""
from __future__ import annotations
import tempfile
import unittest
from pathlib import Path

from fastapi.testclient import TestClient
import r20_backend.app as app_module
from r20_backend.admin_auth import AdminAuthStore


class AdminApiTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.original = app_module.admin_auth
        app_module.admin_auth = AdminAuthStore(Path(self.temp.name) / "admin.db")
        app_module.admin_auth.initialize_from_legacy("InitialAdmin123456")
        self.client = TestClient(app_module.app)

    def tearDown(self):
        app_module.admin_auth = self.original
        self.temp.cleanup()

    def login(self, username: str, password: str) -> dict[str, str]:
        response = self.client.post("/api/v1/admin/auth/login", json={"username": username, "password": password})
        self.assertEqual(response.status_code, 200, response.text)
        return {"X-R20-Session": response.json()["session_token"]}

    def test_login_session_and_logout(self):
        headers = self.login("admin", "InitialAdmin123456")
        self.assertEqual(self.client.get("/api/v1/admin/auth/me", headers=headers).status_code, 200)
        self.assertEqual(self.client.post("/api/v1/admin/auth/logout", headers=headers).status_code, 200)
        self.assertEqual(self.client.get("/api/v1/admin/auth/me", headers=headers).status_code, 401)

    def test_superadmin_only_user_management(self):
        root = self.login("admin", "InitialAdmin123456")
        created = self.client.post("/api/v1/admin/users", headers=root, json={"username": "operator", "password": "OperatorPassword123", "role": "admin"})
        self.assertEqual(created.status_code, 200, created.text)
        operator = self.login("operator", "OperatorPassword123")
        self.assertEqual(self.client.get("/api/v1/admin/users", headers=operator).status_code, 403)
        self.assertEqual(self.client.get("/api/v1/admin/about", headers=operator).status_code, 200)

    def test_health_and_about_report_610_preview(self):
        health=self.client.get("/api/v1/health")
        self.assertEqual(health.status_code,200,health.text)
        self.assertEqual(health.json()["version"],"6.1.0-preview")
        headers=self.login("admin","InitialAdmin123456")
        about=self.client.get("/api/v1/admin/about",headers=headers)
        self.assertEqual(about.status_code,200,about.text)
        self.assertEqual(about.json()["product"]["version"],"6.1.0-preview")
        versions={item["name"]:item["version"] for item in about.json()["components"]}
        self.assertEqual(versions["FastAPI Control Plane"],"6.1.0-preview")

    def test_legacy_header_disabled_after_initialization(self):
        response = self.client.get("/api/v1/admin/overview", headers={"X-R20-Admin-Token": "InitialAdmin123456"})
        self.assertEqual(response.status_code, 401)

    def test_okx_cli_check_and_install_require_valid_session_and_confirmation(self):
        self.assertEqual(self.client.get("/api/v1/admin/okx/cli-check").status_code, 401)
        self.assertEqual(self.client.post("/api/v1/admin/okx/install-cli", json={"confirmation":"INSTALL OKX CLI"}).status_code, 401)
        root = self.login("admin", "InitialAdmin123456")
        from unittest.mock import patch
        with patch.object(app_module, "check_node_npm", return_value={"ready":True,"node_installed":True,"node_path":"/usr/bin/node","node_version":"20","npm_installed":True,"npm_path":"/usr/bin/npm","npm_version":"10"}):
            checked=self.client.get("/api/v1/admin/okx/cli-check",headers=root)
        self.assertEqual(checked.status_code,200,checked.text)
        self.assertTrue(checked.json()["ready"])
        bad=self.client.post("/api/v1/admin/okx/install-cli",headers=root,json={"confirmation":"YES"})
        self.assertEqual(bad.status_code,422)
        wrong=self.client.post("/api/v1/admin/okx/install-cli",headers=root,json={"confirmation":"INSTALL SOMETHING"})
        self.assertEqual(wrong.status_code,400)
        installed={"ok":True,"detail":"OKX CLI 安装成功","path":"/usr/local/bin/okx","version":"1.4.5"}
        with patch.object(app_module,"install_okx_cli",return_value=installed):
            response=self.client.post("/api/v1/admin/okx/install-cli",headers=root,json={"confirmation":"INSTALL OKX CLI"})
        self.assertEqual(response.status_code,200,response.text)
        self.assertEqual(response.json()["version"],"1.4.5")

    def test_okx_runtime_diagnostic_requires_session_and_never_returns_secrets(self):
        self.assertEqual(self.client.get("/api/v1/admin/okx/runtime").status_code, 401)
        headers = self.login("admin", "InitialAdmin123456")
        fake = {
            "selected_mode": "demo", "ready": True, "credential_source": "cli-oauth",
            "cli": {"installed": True, "path": "/usr/local/bin/okx", "version": "1.4.5", "supported": True},
            "oauth": {"status": "logged_in", "site": "global", "scopes": ["market:read", "demo:read", "demo:trade"], "ready_for_selected_mode": True},
            "api_key_profiles": [], "static_credentials_configured": False,
            "read_probe": {"ok": True, "detail": "OKX 私有只读探针通过"},
            "issues": [], "steps": [], "install_command": "npm install -g @okx_ai/okx-trade-cli@^1.4.4",
        }
        from unittest.mock import patch
        with patch.object(app_module, "diagnose_okx_runtime", return_value=fake):
            response = self.client.get("/api/v1/admin/okx/runtime", headers=headers)
        self.assertEqual(response.status_code, 200, response.text)
        text = response.text.lower()
        self.assertNotIn("secret_key", text)
        self.assertNotIn("passphrase", text)
        self.assertEqual(response.json()["credential_source"], "cli-oauth")


if __name__ == "__main__":
    unittest.main()
