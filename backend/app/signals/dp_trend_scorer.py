from datetime import datetime
import logging
from .signal_schema import SignalResult

logger = logging.getLogger(__name__)

class DpTrendScorer:
    """
    Computes Dark Pool SV% trajectory using real 2-day delta.
    Rising SV% = institutions increasing short exposure (distribution or hedging).
    Falling SV% = institutions reducing shorts (accumulation signal).
    """
    def evaluate(self) -> SignalResult:
        now_iso = datetime.now().isoformat()
        today_str = datetime.now().strftime("%Y-%m-%d")

        boost = 0
        reasons = []
        raw_data = {"sv_pct_today": None, "sv_pct_prev": None, "sv_2d_delta": None}

        try:
            from live_monitoring.enrichment.apis.stockgrid_client import StockgridClient
            client = StockgridClient(cache_ttl=300)

            # Get 2-day SV history for real delta
            raw = client.get_ticker_detail_raw("SPY", window=5)
            if raw:
                sv_table = raw.get("individual_short_volume_table", {})
                items = sv_table.get("data", []) if isinstance(sv_table, dict) else sv_table if isinstance(sv_table, list) else []
                sorted_items = sorted(items, key=lambda x: x.get("date", ""))
                if len(sorted_items) >= 2:
                    def _sv_val(row):
                        v = float(row.get("short_volume_pct", row.get("short_volume%", row.get("short_volume_percent", 0))) or 0)
                        return v if v > 1.0 else v * 100.0
                    sv_today = round(_sv_val(sorted_items[-1]), 1)
                    sv_prev = round(_sv_val(sorted_items[-2]), 1)
                    sv_delta = round(sv_today - sv_prev, 1)

                    raw_data["sv_pct_today"] = sv_today
                    raw_data["sv_pct_prev"] = sv_prev
                    raw_data["sv_2d_delta"] = sv_delta

                    # Rising SV% = distribution (bearish for longs)
                    # Falling SV% = accumulation (bullish)
                    if sv_delta < -5 and sv_today < 50:
                        boost = 1
                        reasons.append(
                            f"DP trend FALLING: SPY SV {sv_today:.1f}% ({sv_delta:+.1f}pp) — "
                            f"institutions reducing shorts = accumulation signal"
                        )
                    elif sv_delta > 5 and sv_today > 55:
                        boost = -1
                        reasons.append(
                            f"DP trend RISING: SPY SV {sv_today:.1f}% ({sv_delta:+.1f}pp) — "
                            f"institutions increasing shorts = distribution signal"
                        )
                    else:
                        raw_data["dp_trend_signal"] = "NEUTRAL"

        except Exception as e:
            logger.warning(f"DP Trend fetch failed: {e}")

        slug = f"dp-trend-{boost}-{today_str}"

        return SignalResult(
            name="DP_TREND",
            slug=slug,
            boost=boost,
            active=(boost != 0),
            timestamp=now_iso,
            source_date=today_str,
            raw=raw_data,
            reasons=reasons
        )
