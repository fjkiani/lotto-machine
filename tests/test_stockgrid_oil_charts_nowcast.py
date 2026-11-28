"""
Mocked coverage for unused PUBLIC AXLFI recon wrappers:
  /oil/overview, /oil/prices, /charts/{t}/markers, /nowcast/gdp, /watchlists/quotes

Probe honesty (live, no cookie print): oil/overview 200, oil/prices 200,
charts/SPY/markers 200, nowcast/gdp 200, watchlists/quotes?tickers= 200
(422 without tickers). Never invents LIVE darkpools. No Bearer wiring.
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


class TestOilChartsNowcastWatchlists(unittest.TestCase):
    def tearDown(self):
        for key in ("AXLFI_SESSION_COOKIE", "AXLFI_PRO_COOKIE"):
            os.environ.pop(key, None)

    def _client_with_response(self, status: int, payload):
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

    def test_oil_overview_and_prices_200(self):
        client, session = self._client_with_response(
            200, {"brent": 80.0, "wti": 75.0, "steo_release": "2026-11"}
        )
        out = client.get_oil_overview()
        self.assertIsNotNone(out)
        self.assertIn("/oil/overview", session.get.call_args[0][0])
        self.assertEqual(client.last_fetch_meta.get("http_status"), 200)
        self.assertEqual(client.last_fetch_meta.get("source"), "live")
        self.assertFalse(client.last_fetch_meta.get("paywall"))

        c2, s2 = self._client_with_response(
            200, {"brent": 80.0, "wti": 75.0, "conflict_start": None}
        )
        out2 = c2.get_oil_prices()
        self.assertIsNotNone(out2)
        self.assertIn("/oil/prices", s2.get.call_args[0][0])
        self.assertEqual(c2.last_fetch_meta.get("http_status"), 200)

    def test_chart_markers_200(self):
        client, session = self._client_with_response(
            200, {"ticker": "SPY", "markers": [{"type": "earnings"}]}
        )
        out = client.get_chart_markers("SPY")
        self.assertEqual(out.get("ticker"), "SPY")
        self.assertIn("/charts/SPY/markers", session.get.call_args[0][0])
        self.assertEqual(client.last_fetch_meta.get("http_status"), 200)
        self.assertEqual(client.last_fetch_meta.get("source"), "live")

    def test_nowcast_gdp_200(self):
        client, session = self._client_with_response(
            200, {"as_of": "2026-11-27", "quarters": [], "published": True}
        )
        out = client.get_nowcast_gdp()
        self.assertIsNotNone(out)
        self.assertIn("/nowcast/gdp", session.get.call_args[0][0])
        self.assertEqual(client.last_fetch_meta.get("http_status"), 200)

    def test_watchlists_quotes_200_with_tickers(self):
        client, session = self._client_with_response(
            200, {"quotes": [{"ticker": "SPY", "last": 680.0}]}
        )
        out = client.get_watchlists_quotes(["SPY", "QQQ"])
        self.assertIsNotNone(out)
        url = session.get.call_args[0][0]
        self.assertIn("/watchlists/quotes", url)
        params = session.get.call_args[1].get("params") or {}
        self.assertEqual(params.get("tickers"), "SPY,QQQ")
        self.assertEqual(client.last_fetch_meta.get("http_status"), 200)

    def test_watchlists_quotes_422_fail_closed_empty(self):
        """Without valid tickers AXLFI returns 422 — wrapper must not invent quotes."""
        client, session = self._client_with_response(
            422,
            [
                {
                    "type": "missing",
                    "loc": ["query", "tickers"],
                    "msg": "Field required",
                }
            ],
        )
        # Force empty tickers path still sends default SPY,QQQ — simulate 422 anyway
        out = client.get_watchlists_quotes(["SPY"])
        # 422 → _get returns None / no live source
        self.assertTrue(out is None or client.last_fetch_meta.get("http_status") == 422)
        self.assertNotEqual(client.last_fetch_meta.get("source"), "live")

    def test_leadership_still_present_thin(self):
        """get_leadership already exists — thin smoke, do not duplicate."""
        client, session = self._client_with_response(
            200, {"universe": "us", "as_of": "2026-11-27", "count": 10}
        )
        out = client.get_leadership()
        self.assertIsNotNone(out)
        self.assertIn("/leadership", session.get.call_args[0][0])

    def test_no_bearer_and_no_fake_darkpools_live(self):
        src_path = os.path.join(
            os.path.dirname(__file__),
            "..",
            "live_monitoring",
            "enrichment",
            "apis",
            "stockgrid_client.py",
        )
        with open(src_path, "r", encoding="utf-8") as f:
            src = f.read()
        self.assertIn("get_oil_overview", src)
        self.assertIn("get_chart_markers", src)
        self.assertIn("get_nowcast_gdp", src)
        self.assertIn("get_watchlists_quotes", src)
        self.assertIn("AXLFI_SESSION_COOKIE", src)
        self.assertNotIn('headers["Authorization"]', src)
        self.assertNotIn("Authorization: Bearer", src)

        # Cookie absent — darkpools stay fail-closed (not LIVE)
        client, session = self._client_with_response(
            403, {"detail": "Pro subscription required"}
        )
        raw = client.get_ticker_detail_raw("SPY", window=10)
        self.assertTrue(raw is None or client.last_fetch_meta.get("paywall") is True)
        self.assertEqual(client.last_fetch_meta.get("http_status"), 403)
        self.assertNotEqual(client.last_fetch_meta.get("source"), "live")


if __name__ == "__main__":
    unittest.main()
