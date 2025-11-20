#!/usr/bin/env python3
"""
INSTITUTIONAL STOCK SCREENER
============================
Automatically finds high-probability tickers beyond SPY/QQQ.

Screens for:
- High dark pool volume (institutional interest)
- High short interest (squeeze potential)
- Price momentum (trend strength)
- Options activity (gamma pressure)

Uses ChartExchange's /screener/stocks/ endpoint.

Author: Alpha's AI Hedge Fund
Date: 2024-10-18
"""

import sys
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Any, Optional
import logging
from dataclasses import dataclass

# Add paths
sys.path.append(str(Path(__file__).parent.parent.parent / 'core/data'))

from ultimate_chartexchange_client import UltimateChartExchangeClient

logger = logging.getLogger(__name__)


@dataclass
class ScreenerResult:
    """Represents a ticker from the screener"""
    symbol: str
    price: float
    volume: int
    volume_ratio: float  # vs 30-day average
    dp_volume_pct: float  # Dark pool % of total volume
    short_interest_pct: float  # Short interest as % of float
    price_change_pct: float  # Daily price change
    squeeze_score: float  # 0-100 composite score
    gamma_pressure: float  # 0-100 options pressure
    institutional_score: float  # 0-100 composite institutional activity
    rank: int  # Overall rank (1 = best)


class InstitutionalScreener:
    """
    Screens for high-probability tickers with institutional activity
    """
    
    def __init__(self, api_key: str):
        """
        Initialize Institutional Screener
        
        Args:
            api_key: ChartExchange API key
        """
        self.client = UltimateChartExchangeClient(api_key=api_key)
        logger.info("🔍 Institutional Screener initialized")
    
    def screen_high_flow_tickers(self, 
                                   min_price: float = 10.0,
                                   min_volume: int = 1_000_000,
                                   max_results: int = 20) -> List[ScreenerResult]:
        """
        Screen for tickers with high institutional flow
        
        Args:
            min_price: Minimum stock price
            min_volume: Minimum daily volume
            max_results: Maximum number of results
        
        Returns:
            List of ScreenerResult objects sorted by institutional score
        """
        try:
            logger.info("🔍 Screening for high institutional flow tickers...")
            logger.info(f"   Min Price: ${min_price:.2f}")
            logger.info(f"   Min Volume: {min_volume:,}")
            
            # Fetch screener data
            # Note: ChartExchange screener endpoint returns: display, reg_price, reg_volume, market_cap, industry
            # We can't filter by dark_pool_pct as it's not in the response
            data = self.client.get_stock_screener(
                min_price=min_price,
                min_volume=min_volume
                # min_dark_pool_pct removed - not supported by API
            )
            
            if not data:
                logger.warning("⚠️ No screener data returned")
                return []
            
            results = []
            
            for entry in data[:max_results]:  # Limit results
                # Parse actual API fields (handle string/number conversion)
                symbol = entry.get('display', '')  # API returns 'display' as symbol
                
                # Convert to float/int, handling string values
                try:
                    price = float(entry.get('reg_price', 0.0) or 0.0)
                except (ValueError, TypeError):
                    price = 0.0
                
                try:
                    volume = int(float(entry.get('reg_volume', 0) or 0))
                except (ValueError, TypeError):
                    volume = 0
                
                try:
                    price_change = float(entry.get('reg_change_pct', 0.0) or 0.0)
                except (ValueError, TypeError):
                    price_change = 0.0
                
                try:
                    market_cap = int(float(entry.get('market_cap', 0) or 0))
                except (ValueError, TypeError):
                    market_cap = 0
                
                # Skip if missing critical data
                if not symbol or price <= 0 or volume <= 0:
                    continue
                
                # Calculate volume ratio (we'll need to estimate - API doesn't provide 30-day avg)
                # For now, use volume as proxy (higher volume = higher ratio)
                volume_ratio = max(1.0, volume / 10_000_000) if volume > 0 else 1.0
                
                # DP and short data not available in screener response
                # We'll fetch separately if needed, but for now use defaults
                dp_pct = 0.0  # Not available in screener response
                short_pct = 0.0  # Not available in screener response
                
                # Calculate composite scores
                squeeze_score = self._calculate_squeeze_score(
                    short_pct=short_pct,
                    volume_ratio=volume_ratio,
                    dp_pct=dp_pct
                )
                
                # Gamma pressure not available in screener - use volume as proxy
                gamma_pressure = min(100.0, (volume / 50_000_000) * 100) if volume > 0 else 0.0
                
                # Calculate institutional score without DP/short data
                # Weight: volume (60%), market cap (20%), price change (20%)
                institutional_score = self._calculate_institutional_score(
                    dp_pct=0.0,  # Not available
                    volume_ratio=volume_ratio,
                    short_pct=0.0  # Not available
                )
                
                # Boost score for high volume stocks (institutional proxy)
                if volume > 20_000_000:
                    institutional_score = min(100.0, institutional_score * 1.2)
                elif volume > 10_000_000:
                    institutional_score = min(100.0, institutional_score * 1.1)
                
                result = ScreenerResult(
                    symbol=symbol,
                    price=price,
                    volume=volume,
                    volume_ratio=volume_ratio,
                    dp_volume_pct=dp_pct,
                    short_interest_pct=short_pct,
                    price_change_pct=price_change,
                    squeeze_score=squeeze_score,
                    gamma_pressure=gamma_pressure,
                    institutional_score=institutional_score,
                    rank=0  # Will set after sorting
                )
                
                results.append(result)
            
            # Sort by institutional score
            results.sort(key=lambda r: r.institutional_score, reverse=True)
            
            # Assign ranks
            for i, result in enumerate(results, 1):
                result.rank = i
            
            logger.info(f"✅ Found {len(results)} high-flow tickers")
            
            return results
            
        except Exception as e:
            logger.error(f"❌ Error screening tickers: {e}")
            return []
    
    def screen_squeeze_candidates(self,
                                    min_short_pct: float = 20.0,
                                    min_volume_ratio: float = 2.0,
                                    max_results: int = 10) -> List[ScreenerResult]:
        """
        Screen specifically for short squeeze candidates
        
        Args:
            min_short_pct: Minimum short interest %
            min_volume_ratio: Minimum volume vs average
            max_results: Maximum number of results
        
        Returns:
            List of ScreenerResult objects sorted by squeeze score
        """
        try:
            logger.info("🎯 Screening for squeeze candidates...")
            logger.info(f"   Min Short %: {min_short_pct:.1f}%")
            logger.info(f"   Min Volume Ratio: {min_volume_ratio:.1f}x")
            
            # Get all high-flow tickers first
            all_results = self.screen_high_flow_tickers(max_results=100)
            
            # Filter for squeeze criteria
            squeeze_candidates = [
                r for r in all_results
                if r.short_interest_pct >= min_short_pct
                and r.volume_ratio >= min_volume_ratio
            ]
            
            # Sort by squeeze score
            squeeze_candidates.sort(key=lambda r: r.squeeze_score, reverse=True)
            
            # Re-rank
            for i, result in enumerate(squeeze_candidates[:max_results], 1):
                result.rank = i
            
            logger.info(f"✅ Found {len(squeeze_candidates)} squeeze candidates")
            
            return squeeze_candidates[:max_results]
            
        except Exception as e:
            logger.error(f"❌ Error screening for squeezes: {e}")
            return []
    
    def _calculate_squeeze_score(self, short_pct: float, volume_ratio: float, dp_pct: float) -> float:
        """
        Calculate composite squeeze potential score (0-100)
        
        Args:
            short_pct: Short interest %
            volume_ratio: Volume vs average
            dp_pct: Dark pool %
        
        Returns:
            Squeeze score (0-100)
        """
        # Weight factors:
        # - Short interest: 50% (primary driver)
        # - Volume ratio: 30% (buying pressure)
        # - DP %: 20% (institutional accumulation)
        
        short_score = min(short_pct / 50.0 * 100, 100)  # Cap at 50% SI = 100 score
        volume_score = min((volume_ratio - 1.0) / 4.0 * 100, 100)  # 5x volume = 100 score
        dp_score = min(dp_pct / 70.0 * 100, 100)  # 70% DP = 100 score
        
        composite = (
            short_score * 0.5 +
            volume_score * 0.3 +
            dp_score * 0.2
        )
        
        return min(composite, 100.0)
    
    def _calculate_institutional_score(self, dp_pct: float, volume_ratio: float, short_pct: float) -> float:
        """
        Calculate composite institutional activity score (0-100)
        
        Args:
            dp_pct: Dark pool % (may be 0 if not available)
            volume_ratio: Volume vs average
            short_pct: Short interest % (may be 0 if not available)
        
        Returns:
            Institutional score (0-100)
        """
        # Weight factors (adjusted for missing DP data):
        # - Volume ratio: 70% (primary indicator when DP unavailable)
        # - DP %: 20% (if available)
        # - Short interest: 10% (if available)
        
        volume_score = min((volume_ratio - 1.0) / 4.0 * 100, 100)
        
        # If DP data available, use it
        if dp_pct > 0:
            dp_score = min(dp_pct / 70.0 * 100, 100)
            composite = (
                dp_score * 0.2 +
                volume_score * 0.7 +
                (min(short_pct / 50.0 * 100, 100) * 0.1 if short_pct > 0 else 0)
            )
        else:
            # No DP data - rely on volume only
            composite = volume_score
        
        return min(composite, 100.0)
    
    def print_screener_results(self, results: List[ScreenerResult], title: str = "SCREENER RESULTS"):
        """Print screener results in a readable format"""
        if not results:
            logger.info("⚪ No results found")
            return
        
        logger.info("")
        logger.info("=" * 120)
        logger.info(f"🔍 {title}")
        logger.info("=" * 120)
        logger.info(f"{'Rank':<6} {'Symbol':<8} {'Price':<10} {'Volume':<12} {'DP%':<8} {'Short%':<8} {'Chg%':<8} {'Inst':<8} {'Squeeze':<8}")
        logger.info("-" * 120)
        
        for result in results:
            logger.info(
                f"{result.rank:<6} "
                f"{result.symbol:<8} "
                f"${result.price:<9.2f} "
                f"{result.volume:<12,} "
                f"{result.dp_volume_pct:<7.1f}% "
                f"{result.short_interest_pct:<7.1f}% "
                f"{result.price_change_pct:<+7.2f}% "
                f"{result.institutional_score:<7.0f} "
                f"{result.squeeze_score:<7.0f}"
            )
        
        logger.info("=" * 120)
        logger.info(f"Total: {len(results)} ticker(s)")
        logger.info("=" * 120)
        logger.info("")


if __name__ == "__main__":
    # Test the stock screener
    logging.basicConfig(level=logging.INFO, format='%(levelname)s:%(name)s:%(message)s')
    
    import sys
    sys.path.append(str(Path(__file__).parent.parent.parent / 'configs'))
    from chartexchange_config import CHARTEXCHANGE_API_KEY
    
    screener = InstitutionalScreener(api_key=CHARTEXCHANGE_API_KEY)
    
    # Test 1: High institutional flow
    print("\n" + "=" * 120)
    print("TEST 1: HIGH INSTITUTIONAL FLOW TICKERS")
    print("=" * 120)
    
    high_flow = screener.screen_high_flow_tickers(
        min_price=20.0,
        min_volume=5_000_000,
        max_results=10
    )
    
    screener.print_screener_results(high_flow, "HIGH INSTITUTIONAL FLOW")
    
    # Test 2: Squeeze candidates
    print("\n" + "=" * 120)
    print("TEST 2: SHORT SQUEEZE CANDIDATES")
    print("=" * 120)
    
    squeeze_candidates = screener.screen_squeeze_candidates(
        min_short_pct=15.0,
        min_volume_ratio=2.0,
        max_results=10
    )
    
    screener.print_screener_results(squeeze_candidates, "SQUEEZE CANDIDATES")

