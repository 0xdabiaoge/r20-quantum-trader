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

    def test_enriches_stale_positions_with_margin_and_tracker_stop(self):
        positions=[{"instId":"ETH-USDT-SWAP","side":"short","pos":3,"avgPx":2370,"markPx":2372,"lever":"5","protectionStatus":"unknown_stale"}]
        trackers={"ETH-USDT-SWAP_short":{"trailingStopPx":2410.31,"takeProfitPx":2290.59,"stage_desc":"持有监控中","strategy_tag":"阻力抛压","cloudProtection":{"verifiedAt":"2026-09-02 18:15:00","detail":"cloud OCO coverage verified (3/3)"}}}
        enriched=dashboard.enrich_position_risk_fields(positions,trackers)[0]
        self.assertEqual(enriched["notional_usdt"],711.6)
        self.assertEqual(enriched["margin_usdt"],142.32)
        self.assertEqual(enriched["marginSource"],"notional_div_leverage")
        self.assertEqual(enriched["displayStop"],2410.31)
        self.assertEqual(enriched["stopSource"],"local_tracker")
        self.assertEqual(enriched["protectionStatus"],"verification_stale")

    def test_exchange_margin_and_cloud_stop_take_priority(self):
        positions=[{"instId":"SOL-USDT-SWAP","posSide":"short","pos":6,"avgPx":98.4,"markPx":98.5,"lever":"3","imr":"201.25","exchangeSl":"100.06","protectionStatus":"fully_protected"}]
        trackers={"SOL-USDT-SWAP_short":{"trailingStopPx":101.0}}
        enriched=dashboard.enrich_position_risk_fields(positions,trackers)[0]
        self.assertEqual(enriched["margin_usdt"],201.25)
        self.assertEqual(enriched["marginSource"],"exchange_imr")
        self.assertEqual(enriched["displayStop"],100.06)
        self.assertEqual(enriched["stopSource"],"exchange_cloud")

    def test_meaningful_snapshot_predicate(self):
        self.assertFalse(dashboard._is_meaningful_dashboard_snapshot({}))
        self.assertFalse(dashboard._is_meaningful_dashboard_snapshot({"account": {}}))
        self.assertTrue(dashboard._is_meaningful_dashboard_snapshot({"account": {"total_eq": 0.0}}))


if __name__ == "__main__":
    unittest.main()
