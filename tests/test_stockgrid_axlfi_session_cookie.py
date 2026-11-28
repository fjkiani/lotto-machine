"""
Prove StockgridClient attaches AXLFI Pro session Cookie when env is set.
Does not invent live DP numbers.
"""

import os
import unittest
from unittest.mock import MagicMock, patch

from live_monitoring.enrichment.apis.stockgrid_client import StockgridClient


class TestAxlfiSessionCookie(unittest.TestCase):
    def tearDown(self):
        for key in ("AXLFI_SESSION_COOKIE", "AXLFI_PRO_COOKIE"):
            os.environ.pop(key, None)

    def test_no_cookie_when_env_unset(self):
        for key in ("AXLFI_SESSION_COOKIE", "AXLFI_PRO_COOKIE"):
            os.environ.pop(key, None)
        headers = StockgridClient()._request_headers()
        self.assertNotIn("Cookie", headers)

    def test_session_cookie_preferred_over_pro(self):
        os.environ["AXLFI_SESSION_COOKIE"] = "pro_dummy=1"
        os.environ["AXLFI_PRO_COOKIE"] = "pro_other=2"
        headers = StockgridClient()._request_headers()
        self.assertEqual(headers.get("Cookie"), "pro_dummy=1")

    def test_pro_cookie_fallback(self):
        os.environ.pop("AXLFI_SESSION_COOKIE", None)
        os.environ["AXLFI_PRO_COOKIE"] = "pro_dummy=1"
        headers = StockgridClient()._request_headers()
        self.assertEqual(headers.get("Cookie"), "pro_dummy=1")

    @patch("live_monitoring.enrichment.apis.stockgrid_client.get_session")
    def test_outgoing_get_includes_cookie_header(self, mock_get_session):
        os.environ["AXLFI_SESSION_COOKIE"] = "pro_dummy=1"
        mock_resp = MagicMock()
        mock_resp.status_code = 403
        mock_resp.headers = {"content-type": "application/json"}
        mock_resp.json.return_value = {"detail": "Pro subscription required"}
        mock_session = MagicMock()
        mock_session.get.return_value = mock_resp
        mock_get_session.return_value = mock_session

        client = StockgridClient(max_retries=1)
        # Avoid Playwright / disk side-effects for this header assert
        with patch.object(client, "_browser_get", return_value=None), patch.object(
            client, "_read_disk_cache", return_value=None
        ), patch.object(client, "_repo_cache_lookup", return_value=None), patch.object(
            client, "_legacy_live_file_lookup", return_value=None
        ):
            client._get("/darkpools/ticker", {"ticker": "SPY", "window": "252"})

        self.assertTrue(mock_session.get.called)
        _, kwargs = mock_session.get.call_args
        self.assertEqual(kwargs["headers"].get("Cookie"), "pro_dummy=1")


if __name__ == "__main__":
    unittest.main()
