"""
COT Client — CFTC Commitments of Traders Positioning Intelligence

Source: CFTC (Commodity Futures Trading Commission) via `cot_reports` package
Data:   Weekly specs/commercials long/short positions for futures contracts
Freshness: Weekly (data as of Tuesday, released Friday 3:30 PM ET)
Auth:   None required (public government data)

Key insight: When speculators (specs) and commercials diverge heavily,
it signals institutional positioning that hasn't hit mainstream yet.
"""
import logging
import time
from dataclasses import dataclass
from typing import Optional, Dict, Any

logger = logging.getLogger(__name__)

try:
    import cot_reports as cot
    COT_AVAILABLE = True
except ImportError:
    COT_AVAILABLE = False
    logger.warning("cot_reports not installed — pip install cot_reports")

try:
    import pandas as pd
    PANDAS_AVAILABLE = True
except ImportError:
    PANDAS_AVAILABLE = False


# ─── Data Models ────────────────────────────────────────────────────────────

@dataclass
class COTPosition:
    """A single contract's COT positioning."""
    contract_name: str = ""
    report_date: str = ""
    # Speculators (Non-Commercial)
    specs_long: int = 0
    specs_short: int = 0
    specs_net: int = 0
    # Commercials (Hedgers)
    comm_long: int = 0
    comm_short: int = 0
    comm_net: int = 0
    # Non-reportable (small players)
    nonrep_long: int = 0
    nonrep_short: int = 0
    nonrep_net: int = 0
    # Open Interest
    open_interest: int = 0
    # Derived
    specs_ratio: float = 0.0  # specs_net / open_interest


# ─── COT Client ─────────────────────────────────────────────────────────────

class COTClient:
    """
    CFTC Commitments of Traders data client.
    
    Pulls weekly positioning data for futures contracts. Focuses on
    E-mini S&P 500 (contract code 13874A) for equity positioning analysis.
    
    Key contracts tracked:
      - E-mini S&P 500 (ES)
      - E-mini Nasdaq 100 (NQ)
      - 10-Year T-Note
      - Gold
      - Crude Oil WTI
    """

    # Contract market codes for CFTC legacy reports
    CONTRACTS = {
        "ES": {"name": "E-MINI S&P 500", "code": "13874A", "exchange": "CHICAGO MERCANTILE EXCHANGE"},
        "NQ": {"name": "E-MINI NASDAQ-100", "code": "209742", "exchange": "CHICAGO MERCANTILE EXCHANGE"},
        "TY": {"name": "10-YEAR", "code": "043602", "exchange": "BOARD OF TRADE"},
        "GC": {"name": "GOLD", "code": "088691", "exchange": "COMMODITY EXCHANGE"},
        "CL": {"name": "CRUDE OIL", "code": "067651", "exchange": "NEW YORK MERCANTILE EXCHANGE"},
        "VX": {"name": "VIX FUTURES", "code": "1170E1", "exchange": "CBOE FUTURES EXCHANGE"},
    }

    def __init__(self, cache_ttl: int = 3600):
        """
        Args:
            cache_ttl: Cache TTL in seconds (default 1 hour — COT is weekly).
        """
        self._cache: Dict[str, Any] = {}
        self._cache_ts: Dict[str, float] = {}
        self._cache_ttl = cache_ttl
        self._df_cache: Optional[Any] = None
        self._df_cache_ts: float = 0
        logger.info(f"📊 COTClient initialized (cot_reports available: {COT_AVAILABLE})")

    def _is_cached(self, key: str) -> bool:
        return key in self._cache and (time.time() - self._cache_ts.get(key, 0)) < self._cache_ttl

    def _fetch_cot_data(self):
        """Fetch the latest COT legacy futures report."""
        if not COT_AVAILABLE:
            raise ImportError("cot_reports not installed")
        
        if self._df_cache is not None and (time.time() - self._df_cache_ts) < self._cache_ttl:
            return self._df_cache
        
        try:
            # cot_reports downloads annual.txt to CWD — use /tmp/ so it works on Render
            import os
            original_cwd = os.getcwd()
            os.makedirs("/tmp/cot_data", exist_ok=True)
            os.chdir("/tmp/cot_data")
            try:
                df = cot.cot_year(2026, cot_report_type="legacy_fut")
                if df is None or (hasattr(df, 'empty') and df.empty):
                    logger.warning("⚠️ 2026 COT data empty, trying 2025")
                    df = cot.cot_year(2025, cot_report_type="legacy_fut")
            finally:
                os.chdir(original_cwd)
            
            self._df_cache = df
            self._df_cache_ts = time.time()
            logger.info(f"✅ Fetched COT data: {len(df)} rows")
            return df
        except Exception as e:
            logger.error(f"❌ COT fetch error: {e}")
            if self._df_cache is not None:
                return self._df_cache
            raise

    # ── Contract Positioning ─────────────────────────────────────────────

    def get_position(self, contract_key: str = "ES") -> Optional[COTPosition]:
        """
        Get latest COT positioning for a contract.
        
        Args:
            contract_key: One of "ES", "NQ", "TY", "GC", "CL", "VX"
        
        Returns:
            COTPosition with specs/commercials net positions, or None.
        """
        cache_key = f"pos_{contract_key}"
        if self._is_cached(cache_key):
            return self._cache[cache_key]
        
        if contract_key not in self.CONTRACTS:
            logger.error(f"❌ Unknown contract: {contract_key}. Use: {list(self.CONTRACTS.keys())}")
            return None
        
        contract = self.CONTRACTS[contract_key]
        
        try:
            df = self._fetch_cot_data()
            
            # Filter to this contract by CFTC market code OR exact name match
            market_col = "Market and Exchange Names"
            code_col = "CFTC Contract Market Code"
            
            contract_rows = None
            
            # Try by CFTC market code first (most precise)
            if code_col in df.columns:
                contract_rows = df[df[code_col].astype(str).str.strip() == contract["code"]]
            
            # Fallback to name matching (requires BOTH name AND exchange)
            if contract_rows is None or contract_rows.empty:
                if market_col in df.columns:
                    mask = df[market_col].str.contains(contract["name"], case=False, na=False)
                    if "exchange" in contract:
                        mask = mask & df[market_col].str.contains(contract["exchange"], case=False, na=False)
                    contract_rows = df[mask]
            
            if contract_rows is None or contract_rows.empty:
                logger.warning(f"⚠️ No COT data for {contract['name']}")
                return None
            
            # Sort by date (newest first)
            date_col = "As of Date in Form YYYY-MM-DD"
            if date_col not in df.columns:
                date_col = "As of Date in Form YYMMDD"
            
            if date_col in contract_rows.columns:
                contract_rows = contract_rows.sort_values(date_col, ascending=False)
            
            latest = contract_rows.iloc[0]
            
            # Extract positioning — use exact CFTC column names
            specs_long = int(latest.get("Noncommercial Positions-Long (All)", 0) or 0)
            specs_short = int(latest.get("Noncommercial Positions-Short (All)", 0) or 0)
            comm_long = int(latest.get("Commercial Positions-Long (All)", 0) or 0)
            comm_short = int(latest.get("Commercial Positions-Short (All)", 0) or 0)
            oi = int(latest.get("Open Interest (All)", 0) or 0)
            nonrep_long = int(latest.get("Nonreportable Positions-Long (All)", 0) or 0)
            nonrep_short = int(latest.get("Nonreportable Positions-Short (All)", 0) or 0)
            
            specs_net = specs_long - specs_short
            comm_net = comm_long - comm_short
            nonrep_net = nonrep_long - nonrep_short
            
            report_date = str(latest.get("As of Date in Form YYYY-MM-DD", latest.get("As of Date in Form YYMMDD", "")))
            if "T" in report_date:
                report_date = report_date.split("T")[0]
            
            pos = COTPosition(
                contract_name=contract["name"],
                report_date=report_date,
                specs_long=specs_long,
                specs_short=specs_short,
                specs_net=specs_net,
                comm_long=comm_long,
                comm_short=comm_short,
                comm_net=comm_net,
                nonrep_long=nonrep_long,
                nonrep_short=nonrep_short,
                nonrep_net=nonrep_net,
                open_interest=oi,
                specs_ratio=specs_net / oi if oi else 0,
            )
            
            self._cache[cache_key] = pos
            self._cache_ts[cache_key] = time.time()
            logger.info(f"✅ {contract['name']}: Specs NET {specs_net:+,} | Comm NET {comm_net:+,}")
            return pos
            
        except Exception as e:
            logger.error(f"❌ COT position error for {contract_key}: {e}")
            return self._cache.get(cache_key)

    # ── Divergence Detection ─────────────────────────────────────────────

    def get_divergence_signal(self, contract_key: str = "ES") -> Dict[str, Any]:
        """
        Detect specs vs commercials divergence.
        
        Returns:
            Dict with: divergent (bool), magnitude, direction, description
        """
        pos = self.get_position(contract_key)
        if not pos:
            return {"divergent": False, "magnitude": 0, "direction": "unknown", "description": "No COT data"}
        
        # Divergence = specs and commercials on opposite sides
        divergent = (pos.specs_net > 0 and pos.comm_net < 0) or (pos.specs_net < 0 and pos.comm_net > 0)
        magnitude = abs(pos.specs_net) + abs(pos.comm_net)
        
        if pos.specs_net < 0 and pos.comm_net > 0:
            direction = "specs_bearish_comm_bullish"
            desc = f"Specs NET SHORT ({pos.specs_net:+,}), Commercials NET LONG ({pos.comm_net:+,}) — smart money divergence"
        elif pos.specs_net > 0 and pos.comm_net < 0:
            direction = "specs_bullish_comm_bearish"
            desc = f"Specs NET LONG ({pos.specs_net:+,}), Commercials NET SHORT ({pos.comm_net:+,}) — potential top signal"
        else:
            direction = "aligned"
            desc = f"Specs and Commercials aligned ({pos.specs_net:+,} / {pos.comm_net:+,})"
        
        return {
            "divergent": divergent,
            "magnitude": magnitude,
            "direction": direction,
            "description": desc,
            "specs_net": pos.specs_net,
            "comm_net": pos.comm_net,
            "report_date": pos.report_date,
        }

    # ── Narrative ────────────────────────────────────────────────────────

    def get_narrative(self, contract_key: str = "ES") -> str:
        """Generate narrative-ready text for SavageAgents."""
        try:
            pos = self.get_position(contract_key)
            if not pos:
                return "COT positioning data unavailable"
            
            div = self.get_divergence_signal(contract_key)
            
            parts = [
                f"COT {pos.contract_name} ({pos.report_date}):",
                f"Specs {pos.specs_net:+,} ({'SHORT 🔴' if pos.specs_net < 0 else 'LONG 🟢'})",
                f"Commercials {pos.comm_net:+,} ({'LONG 🟢' if pos.comm_net > 0 else 'SHORT 🔴'})",
                f"OI: {pos.open_interest:,}",
            ]
            
            if div["divergent"]:
                parts.append(f"⚠️ DIVERGENCE: {div['direction']}")
            
            return " | ".join(parts)
        except Exception as e:
            logger.error(f"❌ COT narrative error: {e}")
            return "COT positioning data unavailable"


# ─── Standalone Test ────────────────────────────────────────────────────────

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    client = COTClient()
    
    print("=" * 60)
    print("🐺 COT Client — Live Test")
    print("=" * 60)
    
    for key in ["ES", "NQ", "GC"]:
        print(f"\n--- {key} ---")
        pos = client.get_position(key)
        if pos:
            print(f"  Contract: {pos.contract_name}")
            print(f"  Report Date: {pos.report_date}")
            print(f"  Specs: Long {pos.specs_long:,} | Short {pos.specs_short:,} | NET {pos.specs_net:+,}")
            print(f"  Comm:  Long {pos.comm_long:,} | Short {pos.comm_short:,} | NET {pos.comm_net:+,}")
            print(f"  OI: {pos.open_interest:,}")
            
            div = client.get_divergence_signal(key)
            if div["divergent"]:
                print(f"  ⚠️ DIVERGENCE: {div['description']}")
    
    print(f"\n--- Narrative ---")
    print(client.get_narrative("ES"))
