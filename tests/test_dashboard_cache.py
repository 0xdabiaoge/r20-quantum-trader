from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import dashboard.app as dashboard


class DashboardPersistentCacheTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.cache = Path(self.temp.name) / "dashboard_last_good.json"
        self.patch = patch.object(dashboard, "DASHBOARD_CACHE_FILE", str(self.cache))
        self.patch.start()

    def tearDown(self):
        self.patch.stop()
        self.temp.cleanup()

    def test_persist_and_reload_meaningful_snapshot(self):
        payload = {"timestamp": "2026-09-02 20:00:00", "account": {"total_eq": 4100.0}, "factors": [{"name": "BTC"}]}
        dashboard.persist_dashboard_cache(payload)
        self.assertEqual(dashboard.load_persisted_dashboard_cache(), payload)
        self.assertEqual(self.cache.stat().st_mode & 0o777, 0o600)

    def test_empty_account_is_never_saved_or_used_as_last_good(self):
        dashboard.persist_dashboard_cache({"account": {}})
        self.assertFalse(self.cache.exists())
        self.cache.write_text(json.dumps({"account": {}}), encoding="utf-8")
        self.assertEqual(dashboard.load_persisted_dashboard_cache(), {})

    def test_meaningful_snapshot_predicate(self):
        self.assertFalse(dashboard._is_meaningful_dashboard_snapshot({}))
        self.assertFalse(dashboard._is_meaningful_dashboard_snapshot({"account": {}}))
        self.assertTrue(dashboard._is_meaningful_dashboard_snapshot({"account": {"total_eq": 0.0}}))


if __name__ == "__main__":
    unittest.main()
