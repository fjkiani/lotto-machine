"""
Unit tests: PUBLIC AXLFI layers LIVE on HTTP 200 vs darkpools/insiders HARD_BLOCK.

Mocked HTTP only — never invents DP LIVE without Pro 200.
Folds #20 PUBLIC methods + themes/sectors into HF pack.
"""
from __future__ import annotations

import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from backend.app.signals.sources.public_enrichment import (
    darkpools_hard_block_layer,
    fetch_public_enrichment,
)
from live_monitoring.enrichment.apis.stockgrid_client import StockgridClient


def _json_resp(status: int, payload):
    mock_resp = MagicMock()
    mock_resp.status_code = status
    mock_resp.headers = {"content-type": "application/json"}
    mock_resp.json.return_value = payload
    mock_resp.text = json.dumps(payload)
    return mock_resp


PUBLIC_LAYER_NAMES = (
    "options_walls",
    "short_interest",
    "clusters",
    "market_update",
    "institutions",
    "events",
    "breadth",
    "contracts",
    "short_interest_fails",
    "market_themes",
    "market_sectors",
)


class TestPublicEnrichmentLive(unittest.TestCase):
    def tearDown(self):
        for key in ("AXLFI_SESSION_COOKIE", "AXLFI_PRO_COOKIE"):
            os.environ.pop(key, None)

    def _client(self):
        mock_session = MagicMock()
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

    def test_public_layers_live_on_200_including_recon_fold(self):
        client, session = self._client()

        def _route(url, *args, **kwargs):
            if "/options/walls" in url:
                return _json_resp(
                    200,
                    {
                        "ticker": "SPY",
                        "as_of": "2026-11-27",
                        "spot": 680.0,
                        "option_walls": {
                            "2026-11-28": {
                                "call_wall": 685,
                                "put_wall": 670,
                                "poc": 680,
                            }
                        },
                    },
                )
            if "/short-interest/fails/ticker" in url:
                return _json_resp(
                    200, {"ticker": "SPY", "as_of": "2026-11-27", "fails": [{"d": 1}]}
                )
            if "/short-interest/ticker" in url:
                return _json_resp(
                    200, {"ticker": "SPY", "as_of": "2026-11-27", "points": [1, 2]}
                )
            if "/clusters/scan" in url:
                return _json_resp(
                    200, {"as_of": "2026-11-27", "rows": [{"cluster": "tech"}], "count": 1}
                )
            if "/market/update" in url:
                return _json_resp(200, {"narrative": "ok", "recap": {}})
            if "/institutions/ticker" in url:
                return _json_resp(
                    200, {"ticker": "SPY", "as_of": "2026-11-27", "rows": [{"fund": "X"}]}
                )
            if "/events/overview" in url:
                return _json_resp(
                    200, {"as_of": "2026-11-27", "events": [{"name": "CPI"}], "rows": []}
                )
            if "/breadth/signals" in url:
                return _json_resp(200, {"as_of": "2026-11-27", "signals": [{"s": 1}]})
            if "/contracts/ticker" in url:
                return _json_resp(
                    200, {"ticker": "SPY", "contracts": [{"strike": 680}]}
                )
            if "/market/themes" in url:
                return _json_resp(200, [{"theme": "AI", "tickers": ["NVDA"]}])
            if "/market/sectors" in url:
                return _json_resp(200, [{"sector": "Technology", "chg": 1.2}])
            if "/insiders/" in url:
                return _json_resp(403, {"detail": "Pro subscription required"})
            return _json_resp(404, {"detail": "not found"})

        session.get.side_effect = _route
        out = fetch_public_enrichment(client, "SPY")

        self.assertTrue(out["public_live_ok"])
        self.assertEqual(out["public_live_count"], len(PUBLIC_LAYER_NAMES))
        self.assertFalse(out["darkpools_included"])
        self.assertFalse(out["insiders_public_live"])
        for name in PUBLIC_LAYER_NAMES:
            layer = out["layers"][name]
            self.assertTrue(layer["live_ok"], msg=name)
            self.assertEqual(layer["status"], "LIVE", msg=name)
            self.assertEqual(layer["freshness"], "LIVE", msg=name)
            self.assertEqual(layer["http_status"], 200, msg=name)

        # Existing #16 methods — not re-implemented walls
        self.assertEqual(out["layers"]["options_walls"]["method"], "get_option_walls")
        self.assertEqual(
            out["layers"]["short_interest"]["method"], "get_short_interest_ticker"
        )
        self.assertEqual(out["layers"]["clusters"]["method"], "get_clusters_scan")
        # #20 fold methods
        self.assertEqual(
            out["layers"]["institutions"]["method"], "get_institutions_ticker"
        )
        self.assertEqual(out["layers"]["events"]["method"], "get_events_overview")
        self.assertEqual(out["layers"]["breadth"]["method"], "get_breadth_signals")
        self.assertEqual(out["layers"]["contracts"]["method"], "get_contracts_ticker")
        self.assertEqual(
            out["layers"]["short_interest_fails"]["method"],
            "get_short_interest_fails_ticker",
        )
        self.assertEqual(out["layers"]["market_themes"]["method"], "get_market_themes")
        self.assertEqual(out["layers"]["market_sectors"]["method"], "get_market_sectors")
        self.assertEqual(out["layers"]["market_themes"]["row_count"], 1)
        self.assertEqual(out["layers"]["market_sectors"]["row_count"], 1)

        # Insiders fail-closed — not public LIVE
        insiders = out["fail_closed_layers"]["insiders"]
        self.assertFalse(insiders["live_ok"])
        self.assertTrue(insiders["pro_gated"])
        self.assertEqual(insiders["status"], "HARD_BLOCK")
        self.assertEqual(insiders["freshness"], "PAYWALL_FALLBACK")
        self.assertEqual(insiders["http_status"], 403)
        self.assertNotIn("insiders", out["live_layer_names"])

    def test_insiders_never_counted_as_public_live_even_on_200(self):
        """With allow_live=False, 200 Pro payload is PRO_GATED not public LIVE."""
        client, session = self._client()

        def _route(url, *args, **kwargs):
            if "/insiders/" in url:
                return _json_resp(200, {"ticker": "SPY", "trades": [{"x": 1}]})
            # Other public endpoints 404 → HARD_BLOCK (not under test)
            return _json_resp(404, {"detail": "not found"})

        session.get.side_effect = _route
        out = fetch_public_enrichment(client, "SPY")
        insiders = out["fail_closed_layers"]["insiders"]
        self.assertFalse(insiders["live_ok"])
        self.assertEqual(insiders["status"], "PRO_GATED")
        self.assertEqual(insiders["http_status"], 200)
        self.assertEqual(out["public_live_count"], 0)
        self.assertFalse(out["insiders_public_live"])

    def test_darkpools_hard_block_helper_never_live(self):
        layer = darkpools_hard_block_layer(reason="no cookie", http_status=None)
        self.assertEqual(layer["status"], "HARD_BLOCK")
        self.assertEqual(layer["freshness"], "PAYWALL_FALLBACK")
        self.assertFalse(layer["live_ok"])
        self.assertNotEqual(layer["status"], "LIVE")

    def test_darkpools_403_fail_closed_not_live(self):
        client, session = self._client()
        session.get.return_value = _json_resp(
            403, {"detail": "Pro subscription required"}
        )
        raw = client.get_ticker_detail_raw("SPY", window=10)
        # Fail-closed: may be None or cache miss — never invent LIVE series
        self.assertTrue(
            raw is None or client.last_fetch_meta.get("paywall") is True
        )
        self.assertEqual(client.last_fetch_meta.get("http_status"), 403)
        self.assertTrue(client.last_fetch_meta.get("paywall"))
        # Must NOT claim LIVE
        self.assertNotEqual(client.last_fetch_meta.get("source"), "live")


class TestProbePackPublicVsDarkpools(unittest.TestCase):
    """Probe pack: public LIVE + darkpools HARD_BLOCK when cookie absent."""

    def tearDown(self):
        for key in ("AXLFI_SESSION_COOKIE", "AXLFI_PRO_COOKIE", "GIT_BRANCH"):
            os.environ.pop(key, None)

    def test_hard_block_pack_includes_public_live_layers(self):
        from scripts import probe_axlfi_live_dp as probe

        public = {
            "symbol": "SPY",
            "layers": {
                name: {
                    "name": name,
                    "method": f"get_{name}",
                    "path": f"/{name}",
                    "status": "LIVE",
                    "freshness": "LIVE",
                    "http_status": 200,
                    "live_ok": True,
                }
                for name in PUBLIC_LAYER_NAMES
            },
            "fail_closed_layers": {
                "insiders": {
                    "name": "insiders",
                    "method": "get_insiders_ticker",
                    "path": "/insiders/ticker",
                    "status": "HARD_BLOCK",
                    "freshness": "PAYWALL_FALLBACK",
                    "http_status": 403,
                    "live_ok": False,
                    "pro_gated": True,
                }
            },
            "live_layer_names": list(PUBLIC_LAYER_NAMES),
            "public_live_count": len(PUBLIC_LAYER_NAMES),
            "public_live_ok": True,
            "all_public_live": True,
            "darkpools_included": False,
            "insiders_public_live": False,
        }
        flags = {
            "AXLFI_SESSION_COOKIE": False,
            "AXLFI_PRO_COOKIE": False,
            "cookie_env_present": False,
        }
        pack = probe._hard_block_pack(
            stamp="TEST",
            cookie_flags=flags,
            envfile_flags=flags,
            public_enrichment=public,
        )
        self.assertFalse(pack["sellable"])
        self.assertTrue(pack["hard_block"])
        self.assertEqual(pack["verdict"], "NOT_SELLABLE")
        self.assertEqual(pack["data_freshness"], "PAYWALL_FALLBACK")
        self.assertEqual(pack["layers"]["options_walls"]["status"], "LIVE")
        self.assertEqual(pack["layers"]["institutions"]["status"], "LIVE")
        self.assertEqual(pack["layers"]["events"]["status"], "LIVE")
        self.assertEqual(pack["layers"]["breadth"]["status"], "LIVE")
        self.assertEqual(pack["layers"]["contracts"]["status"], "LIVE")
        self.assertEqual(pack["layers"]["short_interest_fails"]["status"], "LIVE")
        self.assertEqual(pack["layers"]["market_themes"]["status"], "LIVE")
        self.assertEqual(pack["layers"]["market_sectors"]["status"], "LIVE")
        self.assertEqual(pack["layers"]["insiders"]["status"], "HARD_BLOCK")
        self.assertFalse(pack["layers"]["insiders"]["live_ok"])
        self.assertEqual(pack["layers"]["darkpools"]["status"], "HARD_BLOCK")
        self.assertFalse(pack["layers"]["darkpools"]["live_ok"])
        self.assertEqual(pack["universe"]["SPY"]["status"], "HARD_BLOCK")
        self.assertIn("get_institutions_ticker", pack["gate_A_stockgrid"]["public_methods"])
        self.assertIn("get_market_themes", pack["gate_A_stockgrid"]["public_methods"])
        self.assertIn("get_market_sectors", pack["gate_A_stockgrid"]["public_methods"])
        self.assertIn(
            "get_insiders_ticker", pack["gate_A_stockgrid"]["fail_closed_methods"]
        )

    def test_probe_main_cookie_absent_public_live_mocked(self):
        from scripts import probe_axlfi_live_dp as probe

        os.environ.pop("AXLFI_SESSION_COOKIE", None)
        os.environ.pop("AXLFI_PRO_COOKIE", None)
        os.environ["GIT_BRANCH"] = "cursor/hf-public-pack-fold-0041"

        public_ok = {
            "symbol": "SPY",
            "layers": {
                name: {
                    "status": "LIVE",
                    "freshness": "LIVE",
                    "http_status": 200,
                    "live_ok": True,
                    "method": f"get_{name}",
                    "path": f"/{name}",
                }
                for name in PUBLIC_LAYER_NAMES
            },
            "fail_closed_layers": {
                "insiders": {
                    "status": "HARD_BLOCK",
                    "freshness": "PAYWALL_FALLBACK",
                    "http_status": 403,
                    "live_ok": False,
                    "method": "get_insiders_ticker",
                    "path": "/insiders/ticker",
                    "pro_gated": True,
                }
            },
            "live_layer_names": list(PUBLIC_LAYER_NAMES),
            "public_live_count": len(PUBLIC_LAYER_NAMES),
            "public_live_ok": True,
            "all_public_live": True,
            "darkpools_included": False,
            "insiders_public_live": False,
        }

        with tempfile.TemporaryDirectory() as tmp:
            artifacts = Path(tmp)
            status_path = artifacts / "HF_SIGNAL_STATUS.md"
            with patch.object(probe, "ARTIFACTS_DIR", artifacts), patch.object(
                probe, "STATUS_PATH", status_path
            ), patch.object(
                probe, "_envfile_cookie_flags", return_value={
                    "AXLFI_SESSION_COOKIE": False,
                    "AXLFI_PRO_COOKIE": False,
                    "cookie_env_present": False,
                }
            ), patch(
                "live_monitoring.enrichment.apis.stockgrid_client.StockgridClient"
            ) as mock_cls, patch(
                "backend.app.signals.sources.public_enrichment.fetch_public_enrichment",
                return_value=public_ok,
            ):
                mock_cls.return_value = MagicMock()
                rc = probe.main()

            self.assertEqual(rc, 1)
            packs = list(artifacts.glob("HF_SIGNAL_PACK_*.json"))
            self.assertEqual(len(packs), 1)
            pack = json.loads(packs[0].read_text())
            self.assertFalse(pack["sellable"])
            self.assertEqual(pack["layers"]["darkpools"]["status"], "HARD_BLOCK")
            self.assertTrue(pack["layers"]["options_walls"]["live_ok"])
            self.assertTrue(pack["layers"]["institutions"]["live_ok"])
            self.assertTrue(pack["layers"]["market_themes"]["live_ok"])
            self.assertTrue(pack["layers"]["market_sectors"]["live_ok"])
            self.assertFalse(pack["layers"]["insiders"]["live_ok"])
            status = status_path.read_text()
            self.assertIn("PUBLIC options_walls", status)
            self.assertIn("PUBLIC institutions", status)
            self.assertIn("PUBLIC market_themes", status)
            self.assertIn("PUBLIC market_sectors", status)
            self.assertIn("LIVE", status)
            self.assertIn("HARD_BLOCK", status)
            self.assertIn("NOT SELLABLE", status)
            # Never print cookie values
            self.assertNotIn("Cookie=", status)
            self.assertNotIn("sessionid=", status.lower())


if __name__ == "__main__":
    unittest.main()
