#!/usr/bin/env python3
"""
ULTRA INSTITUTIONAL ENGINE - Stub Implementation
================================================
Minimal implementation to support live monitoring system.
Builds InstitutionalContext from ChartExchange API data.
"""

from dataclasses import dataclass
from typing import List, Optional
from datetime import datetime
import logging
import sys
from pathlib import Path

# Add paths
sys.path.append(str(Path(__file__).parent / 'data'))

from ultimate_chartexchange_client import UltimateChartExchangeClient

logger = logging.getLogger(__name__)


@dataclass
class UltraSignal:
    """Signal from institutional analysis (not used in live monitoring)"""
    symbol: str
    signal_type: str
    confidence: float
    pass


@dataclass
class InstitutionalContext:
    """Institutional intelligence context for a symbol"""
    symbol: str
    date: str
    
    # Dark Pool
    dp_battlegrounds: List[float]  # Price levels with high DP volume
    dp_total_volume: int
    dp_buy_sell_ratio: float
    dp_avg_print_size: float
    dark_pool_pct: float
    
    # Short Data
    short_volume_pct: float
    short_interest: Optional[int]
    days_to_cover: Optional[float]
    borrow_fee_rate: float
    
    # Options
    max_pain: Optional[float]
    put_call_ratio: float
    total_option_oi: int
    
    # Composite Scores
    institutional_buying_pressure: float  # 0-1
    squeeze_potential: float  # 0-1
    gamma_pressure: float  # 0-1


class UltraInstitutionalEngine:
    """Builds institutional context from API data"""
    
    def __init__(self, api_key: str):
        self.client = UltimateChartExchangeClient(api_key, tier=3)
        logger.info("🏗️  Ultra Institutional Engine initialized")
    
    def build_institutional_context(self, symbol: str, date: str) -> Optional[InstitutionalContext]:
        """
        Build institutional context from API data
        
        Args:
            symbol: Ticker symbol
            date: Date string (YYYY-MM-DD)
        
        Returns:
            InstitutionalContext or None if data unavailable
        """
        try:
            logger.info(f"Building institutional context for {symbol} ({date})...")
            
            # Fetch dark pool levels
            dp_levels = self.client.get_dark_pool_levels(symbol, date)
            battlegrounds = []
            
            # Calculate total DP volume from ALL levels
            total_dp_volume = sum(int(level.get('volume', 0)) for level in dp_levels)
            
            # Identify battlegrounds (top 50 levels, vol >= 1M)
            for level in dp_levels[:50]:  # Top 50 levels for battleground identification
                # API returns 'level' not 'price'
                price = float(level.get('level') or level.get('price', 0))
                volume = int(level.get('volume', 0))
                if volume >= 1_000_000:  # Battleground threshold
                    battlegrounds.append(price)
            
            battlegrounds = sorted(set(battlegrounds))
            
            # Fetch dark pool summary (primary source)
            dp_summary = self.client.get_dark_pool_summary(symbol, date)
            dp_buy_sell_ratio = 1.0
            dp_avg_print_size = 0.0
            
            if dp_summary:
                buy_vol = dp_summary.buy_volume
                sell_vol = dp_summary.sell_volume
                if sell_vol > 0:
                    dp_buy_sell_ratio = buy_vol / sell_vol
                dp_avg_print_size = dp_summary.avg_trade_size
            else:
                # Fallback: Calculate from prints if summary unavailable
                try:
                    dp_prints = self.client.get_dark_pool_prints(symbol, date)
                    if dp_prints and len(dp_prints) > 0:
                        total_size = 0
                        buy_vol = 0
                        sell_vol = 0
                        count = 0
                        
                        for p in dp_prints[:1000]:  # Use up to 1000 prints
                            if isinstance(p, dict):
                                size = int(p.get('size', 0))
                                side = p.get('side', '').upper()
                                
                                total_size += size
                                count += 1
                                
                                # Handle different side codes
                                if side == 'B' or side == 'BUY':
                                    buy_vol += size
                                elif side == 'S' or side == 'SELL':
                                    sell_vol += size
                                elif side == 'M' or side == 'MARKET':
                                    # Market orders - try to infer from price vs mid
                                    # For now, split 50/50 or skip
                                    # Most prints are 'M' so we need a better heuristic
                                    # Skip 'M' for now to avoid inflating ratios
                                    pass
                        
                        if count > 0:
                            dp_avg_print_size = total_size / count
                        
                        if sell_vol > 0:
                            dp_buy_sell_ratio = buy_vol / sell_vol
                        elif buy_vol > 0:
                            dp_buy_sell_ratio = 1.5  # All buys, bullish
                        
                        logger.debug(f"Calculated from prints: ratio={dp_buy_sell_ratio:.2f}, avg_size={dp_avg_print_size:.0f}")
                except Exception as e:
                    logger.warning(f"Could not calculate from prints: {e}")
            
            # Fetch short data
            short_volume_data = self.client.get_short_volume(symbol, date)
            short_volume_pct = 0.0
            if short_volume_data and len(short_volume_data) > 0:
                short_volume_pct = short_volume_data[0].short_pct
            
            short_interest_data = self.client.get_short_interest(symbol)
            short_interest = None
            days_to_cover = None
            if short_interest_data:
                # Handle both list and single object
                if isinstance(short_interest_data, list) and len(short_interest_data) > 0:
                    short_interest_data = short_interest_data[0]
                if hasattr(short_interest_data, 'shares_short'):
                    short_interest = short_interest_data.shares_short
                    days_to_cover = getattr(short_interest_data, 'days_to_cover', None)
            
            # Fetch borrow fee
            borrow_fee = self.client.get_borrow_fee(symbol, date)
            borrow_fee_rate = borrow_fee.fee_rate if borrow_fee else 0.0
            
            # Fetch options
            options_summary = self.client.get_options_chain_summary(symbol, date)
            max_pain = options_summary.max_pain if options_summary else None
            put_call_ratio = options_summary.put_call_ratio if options_summary else 1.0
            total_option_oi = (options_summary.total_call_oi + options_summary.total_put_oi) if options_summary else 0
            
            # Calculate dark pool % using DP levels + yfinance total volume
            # NOTE: ChartExchange exchange volume endpoint is BROKEN (returns 2019 data)
            # So we calculate DP % ourselves: DP volume (from levels) / Total volume (yfinance)
            dark_pool_pct = 0.0
            
            # Calculate total DP volume from ALL levels (not just top 50)
            dp_total_all_levels = sum(int(level.get('volume', 0)) for level in dp_levels)
            
            try:
                import yfinance as yf
                from datetime import datetime, timedelta
                
                # Get total market volume from yfinance
                ticker = yf.Ticker(symbol)
                
                # Try to get volume for the specific date
                end_date = (datetime.strptime(date, '%Y-%m-%d') + timedelta(days=1)).strftime('%Y-%m-%d')
                hist = ticker.history(start=date, end=end_date)
                
                if len(hist) > 0 and hist['Volume'].iloc[0] > 0:
                    total_market_vol = hist['Volume'].iloc[0]
                    dark_pool_pct = (dp_total_all_levels / total_market_vol) * 100
                    logger.debug(f"DP %: {dp_total_all_levels:,} / {int(total_market_vol):,} = {dark_pool_pct:.2f}%")
                else:
                    # Fallback: use recent 5-day average
                    hist = ticker.history(period='5d')
                    if len(hist) > 0:
                        total_market_vol = hist['Volume'].mean()
                        dark_pool_pct = (dp_total_all_levels / total_market_vol) * 100
                        logger.warning(f"Using 5-day avg volume for DP %: {dark_pool_pct:.2f}%")
                        
            except Exception as e:
                logger.warning(f"Could not calculate dark pool % from yfinance: {e}")
                # Absolute fallback: estimate based on typical SPY/QQQ DP % (~35-45%)
                if dp_total_all_levels > 0:
                    dark_pool_pct = 35.0  # Conservative estimate
                    logger.warning(f"Using default DP % estimate: {dark_pool_pct}%")
            
            # Calculate composite scores
            institutional_buying_pressure = self._calculate_buying_pressure(
                dp_buy_sell_ratio, short_volume_pct, dark_pool_pct, dp_avg_print_size, put_call_ratio
            )
            
            squeeze_potential = self._calculate_squeeze_potential(
                short_volume_pct, borrow_fee_rate, days_to_cover, dark_pool_pct
            )
            
            gamma_pressure = self._calculate_gamma_pressure(
                put_call_ratio, max_pain, total_option_oi
            )
            
            context = InstitutionalContext(
                symbol=symbol.upper(),
                date=date,
                dp_battlegrounds=battlegrounds,
                dp_total_volume=total_dp_volume,
                dp_buy_sell_ratio=dp_buy_sell_ratio,
                dp_avg_print_size=dp_avg_print_size,
                dark_pool_pct=dark_pool_pct,
                short_volume_pct=short_volume_pct,
                short_interest=short_interest,
                days_to_cover=days_to_cover,
                borrow_fee_rate=borrow_fee_rate,
                max_pain=max_pain,
                put_call_ratio=put_call_ratio,
                total_option_oi=total_option_oi,
                institutional_buying_pressure=institutional_buying_pressure,
                squeeze_potential=squeeze_potential,
                gamma_pressure=gamma_pressure
            )
            
            logger.info(f"✅ Context built: {len(battlegrounds)} battlegrounds, buying pressure: {institutional_buying_pressure:.0%}")
            return context
            
        except Exception as e:
            logger.error(f"Error building context for {symbol}: {e}")
            return None
    
    def _calculate_buying_pressure(self, dp_ratio: float, short_pct: float, 
                                   dp_pct: float, avg_print: float, pc_ratio: float) -> float:
        """Calculate institutional buying pressure (0-1)"""
        score = 0.0
        
        # DP buying (30% weight)
        if dp_ratio > 1.5:
            score += 0.30
        elif dp_ratio > 1.2:
            score += 0.20
        elif dp_ratio > 1.0:
            score += 0.10
        
        # Low shorting (20% weight)
        if short_pct < 25:
            score += 0.20
        elif short_pct < 30:
            score += 0.10
        
        # High DP activity (20% weight)
        if dp_pct > 45:
            score += 0.20
        elif dp_pct > 40:
            score += 0.10
        
        # Large prints (15% weight)
        if avg_print > 10000:
            score += 0.15
        elif avg_print > 5000:
            score += 0.10
        
        # Options sentiment (15% weight)
        if pc_ratio < 0.8:
            score += 0.15
        elif pc_ratio < 1.0:
            score += 0.10
        
        return min(score, 1.0)
    
    def _calculate_squeeze_potential(self, short_pct: float, borrow_fee: float,
                                     days_to_cover: Optional[float], dp_pct: float) -> float:
        """Calculate squeeze potential (0-1)"""
        score = 0.0
        
        # Short interest (40% weight)
        if short_pct > 40:
            score += 0.40
        elif short_pct > 30:
            score += 0.25
        elif short_pct > 20:
            score += 0.10
        
        # Borrow fee (30% weight)
        if borrow_fee > 5.0:
            score += 0.30
        elif borrow_fee > 3.0:
            score += 0.20
        elif borrow_fee > 1.0:
            score += 0.10
        
        # Days to cover (20% weight)
        if days_to_cover and days_to_cover > 5:
            score += 0.20
        elif days_to_cover and days_to_cover > 3:
            score += 0.10
        
        # DP support (10% weight)
        if dp_pct > 50:
            score += 0.10
        
        return min(score, 1.0)
    
    def _calculate_gamma_pressure(self, pc_ratio: float, max_pain: Optional[float],
                                  total_oi: int) -> float:
        """Calculate gamma pressure (0-1)"""
        score = 0.0
        
        # Low P/C ratio (40% weight)
        if pc_ratio < 0.7:
            score += 0.40
        elif pc_ratio < 0.9:
            score += 0.25
        elif pc_ratio < 1.0:
            score += 0.10
        
        # High OI (30% weight)
        if total_oi > 10_000_000:
            score += 0.30
        elif total_oi > 5_000_000:
            score += 0.20
        elif total_oi > 1_000_000:
            score += 0.10
        
        # Max pain distance (30% weight) - would need current price
        # For now, skip this component
        
        return min(score, 1.0)

