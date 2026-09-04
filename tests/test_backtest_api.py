import json
import unittest
from pathlib import Path
from unittest.mock import patch
from fastapi.testclient import TestClient

import r20_backend.app as app_module
from r20_backend.app import app


class BacktestApiTests(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(app)

    def login(self, u="admin", p="InitialAdmin123456"):
        r = self.client.post("/api/v1/admin/auth/login", json={"username": u, "password": p})
        return {"X-R20-Session": r.json()["session_token"]}

    def test_backtest_endpoints_require_admin_session(self):
        self.assertEqual(self.client.get("/api/v1/admin/backtest/report").status_code, 401)
        self.assertEqual(self.client.post("/api/v1/admin/backtest/run", json={}).status_code, 401)

    def test_backtest_report_and_execution_success(self):
        root = self.login()
        # Test get report
        res = self.client.get("/api/v1/admin/backtest/report", headers=root)
        self.assertEqual(res.status_code, 200)
        self.assertIn("has_report", res.json())

        # Test execute backtest
        run_res = self.client.post(
            "/api/v1/admin/backtest/run",
            headers=root,
            json={"symbol": "BTC-USDT-SWAP", "bar": "1H", "limit": 20, "capital": 10000.0},
        )
        self.assertEqual(run_res.status_code, 200)
        self.assertTrue(run_res.json()["ok"])
        self.assertIn("report", run_res.json())


if __name__ == "__main__":
    unittest.main()
