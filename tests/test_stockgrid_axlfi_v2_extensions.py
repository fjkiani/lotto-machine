"""
Mocked HTTP coverage for AXLFI v2 public + Pro-gated wrappers.
Never invents LIVE dark-pool numbers; 403 darkpools stay fail-closed.
"""

from __future__ import annotations

import os
import unittest
from unittest.mock import MagicMock, patch

from live_monitoring.enrichment.apis.stockgrid_client import StockgridClient


def _json_resp(status: int, payload):
    mock_resp = MagicMock()
    mock_resp.status_code = status
    mock_resp.headers = {"content-type": "application/json"}
    mock_resp.json.return_value = payload
    return mock_resp


class TestAxlfiV2Extensions(unittest.TestCase):
    def tearDown(self):
        for key in ("AXLFI_SESSION_COOKIE", "AXLFI_PRO_COOKIE"):
            os.environ.pop(key, None)

    def _client_with_response(self, status: int, payload, path_contains: str = ""):
        mock_session = MagicMock()
        mock_session.get.return_value = _json_resp(status, payload)
        client = StockgridClient(max_retries=1, cache_ttl=0)
        patches = [
            patch(
                "live_monitoring.enrichment.apis.stockgrid_client.get_session",
                return_value=mock_session,
            ),
            patch.object(client, "_browser_get", return_value=None),
            patch.object(client, "_read_disk_cache", return_value=None),
            patch.object(client, "_repo_cache_lookup", return_value=None),
            patch.object(client, "_legacy_live_file_lookup", return_value=None),
            patch.object(client, "_write_disk_cache", return_value=None),
        ]
        for p in patches:
            p.start()
            self.addCleanup(p.stop)
        return client, mock_session

    def test_base_is_live_api_not_dead_backend(self):
        self.assertEqual(StockgridClient.BASE, "https://axlfi.com/api")
        self.assertNotIn("axlfi-app-backend", StockgridClient.BASE)

    def test_public_short_interest_ticker_200(self):
        client, session = self._client_with_response(
            200, {"ticker": "SPY", "as_of": "2026-11-27", "points": []}
        )
        out = client.get_short_interest_ticker("SPY")
        self.assertIsNotNone(out)
        self.assertEqual(out.get("ticker"), "SPY")
        url = session.get.call_args[0][0]
        self.assertIn("/short-interest/ticker", url)

    def test_public_option_walls_and_market_helpers_200(self):
        client, session = self._client_with_response(
            200,
            {
                "ticker": "SPY",
                "as_of": "2026-11-27",
                "spot": 680.0,
                "scopes": {},
                "expiries": [],
                "strikes": [],
            },
        )
        walls = client.get_option_walls("SPY")
        self.assertIsNotNone(walls)
        url = session.get.call_args[0][0]
        self.assertIn("/options/walls", url)

        client2, session2 = self._client_with_response(
            200, {"as_of": "2026-11-27", "vol_21d": 0.12, "series": []}
        )
        vol = client2.get_market_volatility("SPY")
        self.assertEqual(vol.get("vol_21d"), 0.12)
        self.assertIn("/market/volatility", session2.get.call_args[0][0])

        client3, session3 = self._client_with_response(
            200, {"narrative": "test", "recap": {}}
        )
        upd = client3.get_market_update()
        self.assertEqual(upd.get("narrative"), "test")
        self.assertIn("/market/update", session3.get.call_args[0][0])

    def test_public_clusters_congress_earnings_200(self):
        client, session = self._client_with_response(
            200, {"as_of": "2026-11-27", "rows": [], "count": 0}
        )
        scan = client.get_clusters_scan()
        self.assertIsNotNone(scan)
        self.assertIn("/clusters/scan", session.get.call_args[0][0])

        client2, session2 = self._client_with_response(
            200, {"ticker": "SPY", "effective_clusters": []}
        )
        stock = client2.get_cluster_stock("SPY")
        self.assertEqual(stock.get("ticker"), "SPY")
        self.assertIn("/clusters/stock/SPY", session2.get.call_args[0][0])

        client3, session3 = self._client_with_response(200, {"trades": []})
        trades = client3.get_congress_trades()
        self.assertIn("trades", trades)
        self.assertIn("/congress/trades", session3.get.call_args[0][0])

        client4, session4 = self._client_with_response(
            200, {"universe": "us", "days": 7, "rows": []}
        )
        earn = client4.get_earnings_upcoming()
        self.assertIsNotNone(earn)
        self.assertIn("/earnings/upcoming", session4.get.call_args[0][0])

    def test_darkpool_sectors_403_fail_closed(self):
        client, session = self._client_with_response(
            403, {"detail": "Pro subscription required"}
        )
        out = client.get_darkpool_sectors()
        self.assertIsNone(out)
        self.assertTrue(client.last_fetch_meta.get("paywall"))
        self.assertEqual(client.last_fetch_meta.get("http_status"), 403)
        self.assertIn("/darkpools/sectors", session.get.call_args[0][0])

    def test_darkpool_leaderboard_403_returns_empty_not_fake(self):
        client, _ = self._client_with_response(
            403, {"detail": "Pro subscription required"}
        )
        rows = client.get_top_positions(limit=10)
        self.assertEqual(rows, [])
        self.assertTrue(client.last_fetch_meta.get("paywall"))


if __name__ == "__main__":
    unittest.main()
