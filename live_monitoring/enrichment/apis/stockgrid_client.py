"""
Stockgrid Dark Pool Client — Free Dark Pool Flow Intelligence

Source: stockgrid.io (public API, no auth, no rate limit encountered)
Data:   Daily dark pool positions, net short volume, short volume %
Tickers: All US equities with dark pool activity
Freshness: T+0 (updated daily after market close)

Endpoints:
  GET /get_dark_pool_data?top={metric}&minmax={sort}  → Top positions
  GET /get_dark_pool_individual_data?ticker={ticker}   → Per-ticker history

Discovery: aluay/Insight repo is a 361-byte Express wrapper around this API.
We call Stockgrid directly — no middleware needed.
"""
import logging
import time
import requests
from dataclasses import dataclass, field
from typing import Optional, Dict, List, Any

logger = logging.getLogger(__name__)


# ─── Data Models ────────────────────────────────────────────────────────────

@dataclass
class DarkPoolPosition:
    """A single ticker's dark pool summary."""
    ticker: str
    date: str = ""
    dp_position_shares: float = 0.0
    dp_position_dollars: float = 0.0
    net_short_volume: float = 0.0
    net_short_dollars: float = 0.0
    short_volume: float = 0.0
    short_volume_pct: float = 0.0


@dataclass
class DarkPoolSummary:
    """Combined dark pool intelligence."""
    top_positions: List[DarkPoolPosition] = field(default_factory=list)
    spy_detail: Optional[DarkPoolPosition] = None
    qqq_detail: Optional[DarkPoolPosition] = None
    timestamp: str = ""
    source: str = "stockgrid.io"


# ─── Stockgrid Client ──────────────────────────────────────────────────────

class StockgridClient:
    """
    Dark pool flow data from Stockgrid.io.
    
    Free, no auth, no API key. Returns daily dark pool positions,
    net short volume, and short volume % for all US equities.
    """

    BASE_URL = "https://www.stockgrid.io"
    HEADERS = {"User-Agent": "Mozilla/5.0", "Accept": "application/json"}
    
    def __init__(self, cache_ttl: int = 300):
        """
        Args:
            cache_ttl: Cache time-to-live in seconds (default 5 min).
        """
        self._cache: Dict[str, Any] = {}
        self._cache_ts: Dict[str, float] = {}
        self._cache_ttl = cache_ttl
        logger.info("📊 StockgridClient initialized (no auth needed)")

    def _is_cached(self, key: str) -> bool:
        return key in self._cache and (time.time() - self._cache_ts.get(key, 0)) < self._cache_ttl

    # ── Top Dark Pool Positions ──────────────────────────────────────────

    def get_top_positions(self, limit: int = 20, sort_by: str = "Dark Pools Position $") -> List[DarkPoolPosition]:
        """
        Get top tickers by dark pool position.
        
        Args:
            limit: Number of results (API returns up to ~200).
            sort_by: Sort metric. Options:
                - "Dark Pools Position $" (default, total dollar position)
                - "Dark Pools Position" (shares)
                - "Net Short Volume $"
                - "Short Volume %"
        
        Returns:
            List of DarkPoolPosition objects.
        """
        cache_key = f"top_{sort_by}_{limit}"
        if self._is_cached(cache_key):
            return self._cache[cache_key]

        try:
            url = f"{self.BASE_URL}/get_dark_pool_data"
            params = {"top": sort_by, "minmax": "desc"}
            r = requests.get(url, params=params, headers=self.HEADERS, timeout=15)
            r.raise_for_status()
            
            raw = r.json()
            # API returns {"data": [...], "schema": [...]}
            items = raw.get("data", raw) if isinstance(raw, dict) else raw
            if not isinstance(items, list):
                items = []
            
            positions = []
            
            for item in items[:limit]:
                pos = DarkPoolPosition(
                    ticker=item.get("Ticker", ""),
                    date=item.get("Date", ""),
                    dp_position_shares=float(item.get("Dark Pools Position", 0) or 0),
                    dp_position_dollars=float(item.get("Dark Pools Position $", 0) or 0),
                    net_short_volume=float(item.get("Net Short Volume", 0) or 0),
                    net_short_dollars=float(item.get("Net Short Volume $", 0) or 0),
                    short_volume=float(item.get("Short Volume", 0) or 0),
                    short_volume_pct=float(item.get("Short Volume %", 0) or 0),
                )
                positions.append(pos)
            
            self._cache[cache_key] = positions
            self._cache_ts[cache_key] = time.time()
            logger.info(f"✅ Fetched {len(positions)} dark pool positions from Stockgrid")
            return positions
            
        except Exception as e:
            logger.error(f"❌ Stockgrid top positions error: {e}")
            return self._cache.get(cache_key, [])

    # ── Individual Ticker Detail ─────────────────────────────────────────

    def get_ticker_detail(self, ticker: str = "SPY") -> Optional[DarkPoolPosition]:
        """
        Get dark pool detail for a specific ticker (latest day).
        
        Args:
            ticker: Stock ticker symbol (e.g., "SPY", "QQQ").
        
        Returns:
            DarkPoolPosition with latest data, or None.
        """
        cache_key = f"detail_{ticker}"
        if self._is_cached(cache_key):
            return self._cache[cache_key]

        try:
            url = f"{self.BASE_URL}/get_dark_pool_individual_data"
            r = requests.get(url, params={"ticker": ticker}, headers=self.HEADERS, timeout=15)
            r.raise_for_status()
            
            raw = r.json()
            if not raw:
                logger.warning(f"⚠️ No Stockgrid data for {ticker}")
                return None
            
            # Individual endpoint returns:
            # {"individual_dark_pool_position_data": {"data": [...], ...},
            #  "individual_short_volume": {"data": [...], ...},
            #  "individual_short_volume_table": {"data": [...], ...},
            #  "prices": {"data": [...], ...}}
            latest = None
            
            if isinstance(raw, dict):
                # Extract from nested structure
                dp_data = raw.get("individual_dark_pool_position_data", {})
                sv_table = raw.get("individual_short_volume_table", {})
                
                # DP position data
                dp_items = dp_data.get("data", []) if isinstance(dp_data, dict) else []
                sv_items = sv_table.get("data", []) if isinstance(sv_table, dict) else []
                
                if dp_items and isinstance(dp_items, list):
                    item = dp_items[-1]  # Most recent
                    latest = DarkPoolPosition(
                        ticker=ticker,
                        date=item.get("Date", item.get("date", "")),
                        dp_position_shares=float(item.get("Net Volume", item.get("Dark Pools Position", 0)) or 0),
                        dp_position_dollars=float(item.get("Position", item.get("Dark Pools Position $", 0)) or 0),
                    )
                
                # Enrich with short volume data
                if sv_items and isinstance(sv_items, list) and latest:
                    sv_item = sv_items[-1]  # Most recent
                    latest.short_volume = float(sv_item.get("Short Volume", 0) or 0)
                    latest.short_volume_pct = float(sv_item.get("Short Volume %", sv_item.get("Short Exempt Volume %", 0)) or 0)
                    latest.net_short_volume = float(sv_item.get("Net Short Volume", 0) or 0)
                    latest.net_short_dollars = float(sv_item.get("Net Short Volume $", 0) or 0)
                    if not latest.date:
                        latest.date = sv_item.get("Date", sv_item.get("date", ""))
                
                # Fallback: try flat data/schema format
                if not latest:
                    flat_data = raw.get("data", [])
                    if isinstance(flat_data, list) and flat_data:
                        item = flat_data[-1]
                        latest = DarkPoolPosition(
                            ticker=ticker,
                            date=item.get("Date", ""),
                            dp_position_dollars=float(item.get("Dark Pools Position $", 0) or 0),
                            net_short_dollars=float(item.get("Net Short Volume $", 0) or 0),
                            short_volume=float(item.get("Short Volume", 0) or 0),
                            short_volume_pct=float(item.get("Short Volume %", 0) or 0),
                        )
            
            if latest:
                self._cache[cache_key] = latest
                self._cache_ts[cache_key] = time.time()
                logger.info(f"✅ Fetched {ticker} dark pool detail: ${latest.dp_position_dollars/1e9:.1f}B")
            
            return latest
            
        except Exception as e:
            logger.error(f"❌ Stockgrid {ticker} detail error: {e}")
            return self._cache.get(cache_key)

    # ── Summary & Narrative ──────────────────────────────────────────────

    def get_summary(self) -> DarkPoolSummary:
        """Get combined dark pool summary with SPY + QQQ detail."""
        top = self.get_top_positions(limit=10)
        spy = self.get_ticker_detail("SPY")
        qqq = self.get_ticker_detail("QQQ")

        return DarkPoolSummary(
            top_positions=top,
            spy_detail=spy,
            qqq_detail=qqq,
            timestamp=top[0].date if top else "",
        )

    def get_narrative(self) -> str:
        """Generate narrative-ready text for SavageAgents."""
        try:
            summary = self.get_summary()
            parts = []

            if summary.spy_detail:
                s = summary.spy_detail
                parts.append(
                    f"SPY dark pool position: ${s.dp_position_dollars/1e9:.1f}B, "
                    f"net short ${s.net_short_dollars/1e9:.1f}B, "
                    f"short vol {s.short_volume_pct:.1f}%"
                )
            
            if summary.qqq_detail:
                q = summary.qqq_detail
                parts.append(
                    f"QQQ dark pool position: ${q.dp_position_dollars/1e9:.1f}B, "
                    f"net short ${q.net_short_dollars/1e9:.1f}B"
                )
            
            if summary.top_positions:
                top3 = [f"{p.ticker} (${p.dp_position_dollars/1e9:.1f}B)" for p in summary.top_positions[:3]]
                parts.append(f"Top dark pool positions: {', '.join(top3)}")
            
            return " | ".join(parts) if parts else "Dark pool data unavailable"
            
        except Exception as e:
            logger.error(f"❌ Dark pool narrative error: {e}")
            return "Dark pool data unavailable"


# ─── Standalone Test ────────────────────────────────────────────────────────

if __name__ == "__main__":
    import json

    logging.basicConfig(level=logging.INFO)
    client = StockgridClient()
    
    print("=" * 60)
    print("🐺 Stockgrid Dark Pool Client — Live Test")
    print("=" * 60)
    
    # Top positions
    top = client.get_top_positions(limit=5)
    print("\nTop 5 Dark Pool Positions:")
    for p in top:
        print(f"  {p.ticker:>5}: ${p.dp_position_dollars/1e9:.1f}B  "
              f"Net Short: ${p.net_short_dollars/1e9:.1f}B  "
              f"Short Vol: {p.short_volume_pct:.1f}%")
    
    # SPY detail
    spy = client.get_ticker_detail("SPY")
    if spy:
        print(f"\nSPY Detail ({spy.date}):")
        print(f"  DP Position: ${spy.dp_position_dollars/1e9:.1f}B")
        print(f"  Net Short: ${spy.net_short_dollars/1e9:.1f}B")
        print(f"  Short Vol %: {spy.short_volume_pct:.1f}%")
    
    # Narrative
    print(f"\n--- Narrative ---")
    print(client.get_narrative())
