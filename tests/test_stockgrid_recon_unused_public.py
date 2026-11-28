"""
Mocked coverage for recon-unused public + Pro-fail-closed StockgridClient wrappers.
Stacked on #17 tip. Never invents LIVE dark-pool numbers.
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


class TestReconUnusedPublic(unittest.TestCase):
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

    def test_institutions_events_breadth_contracts_200(self):
        client, session = self._client_with_response(200, {"as_of": "2026-11-27", "rows": []})
        self.assertIsNotNone(client.get_institutions_overview())
        self.assertIn("/institutions/overview", session.get.call_args[0][0])

        c2, s2 = self._client_with_response(200, {"ticker": "SPY"})
        self.assertEqual(c2.get_institutions_ticker("SPY").get("ticker"), "SPY")
        self.assertIn("/institutions/ticker", s2.get.call_args[0][0])

        c3, s3 = self._client_with_response(200, {"events": []})
        self.assertIsNotNone(c3.get_events_overview())
        self.assertIn("/events/overview", s3.get.call_args[0][0])

        c4, s4 = self._client_with_response(200, {"signals": []})
        self.assertIsNotNone(c4.get_breadth_signals())
        self.assertIn("/breadth/signals", s4.get.call_args[0][0])

        c5, s5 = self._client_with_response(200, {"contracts": []})
        self.assertIsNotNone(c5.get_contracts_overview())
        self.assertIn("/contracts/overview", s5.get.call_args[0][0])

        c6, s6 = self._client_with_response(200, {"ticker": "QQQ"})
        self.assertEqual(c6.get_contracts_ticker("QQQ").get("ticker"), "QQQ")
        self.assertIn("/contracts/ticker", s6.get.call_args[0][0])

    def test_short_interest_fails_200(self):
        client, session = self._client_with_response(200, {"fails": []})
        out = client.get_short_interest_fails()
        self.assertIsNotNone(out)
        self.assertIn("/short-interest/fails", session.get.call_args[0][0])

        c2, s2 = self._client_with_response(200, {"ticker": "SPY", "fails": []})
        out2 = c2.get_short_interest_fails_ticker("SPY")
        self.assertIsNotNone(out2)
        self.assertIn("/short-interest/fails/ticker", s2.get.call_args[0][0])

    def test_insiders_403_fail_closed(self):
        client, session = self._client_with_response(
            403, {"detail": "Pro subscription required"}
        )
        self.assertIsNone(client.get_insiders_overview())
        self.assertTrue(client.last_fetch_meta.get("paywall"))
        self.assertEqual(client.last_fetch_meta.get("http_status"), 403)
        self.assertIn("/insiders/overview", session.get.call_args[0][0])

        c2, s2 = self._client_with_response(
            403, {"detail": "Pro subscription required"}
        )
        self.assertIsNone(c2.get_insiders_ticker("SPY"))
        self.assertTrue(c2.last_fetch_meta.get("paywall"))
        self.assertIn("/insiders/ticker", s2.get.call_args[0][0])

    def test_no_bearer_env_wired(self):
        """Auth probe closed: Cookie-header only — no Authorization Bearer wiring."""
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
        self.assertIn("AXLFI_SESSION_COOKIE", src)
        self.assertNotIn('headers["Authorization"]', src)
        self.assertNotIn("Authorization: Bearer", src)
        self.assertNotIn("X-Access-Token", src)


if __name__ == "__main__":
    unittest.main()
