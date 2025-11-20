#!/usr/bin/env python3
"""
INTRADAY VOLUME PROFILE ANALYZER
=================================
Analyzes 30-minute exchange volume breakdowns to identify:
- Institutional entry times
- High liquidity periods
- Low liquidity traps
- Best risk/reward timing

Uses ChartExchange's /data/stocks/exchange-volume-intraday/ endpoint.

Author: Alpha's AI Hedge Fund
Date: 2024-10-18
"""

import sys
from pathlib import Path
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
import logging
from dataclasses import dataclass

# Add paths
sys.path.append(str(Path(__file__).parent.parent.parent / 'core/data'))

from ultimate_chartexchange_client import UltimateChartExchangeClient

logger = logging.getLogger(__name__)


@dataclass
class VolumeWindow:
    """Represents a 30-minute volume window"""
    time: str  # e.g., "09:30"
    total_volume: int
    on_exchange_volume: int
    off_exchange_volume: int
    on_exchange_pct: float
    off_exchange_pct: float
    is_high_institutional: bool  # >60% off-exchange = institutional
    is_low_liquidity: bool  # <20% of daily average


@dataclass
class OrderFlowImbalance:
    """Order flow imbalance analysis"""
    symbol: str
    date: str
    buy_volume: int
    sell_volume: int
    net_imbalance: int
    imbalance_ratio: float  # 0.5 = neutral, >0.6 = bullish, <0.4 = bearish
    bias: str  # BULLISH, BEARISH, or NEUTRAL


@dataclass
class VolumeProfile:
    """Complete intraday volume profile"""
    symbol: str
    date: datetime
    windows: List[VolumeWindow]
    total_volume: int
    avg_window_volume: int
    peak_institutional_time: Optional[str]  # Time with highest institutional %
    peak_volume_time: Optional[str]  # Time with highest total volume
    low_liquidity_times: List[str]  # Times to avoid (lunch dip, etc.)
    high_liquidity_times: List[str]  # Best times to enter/exit


class VolumeProfileAnalyzer:
    """
    Analyzes intraday volume patterns to identify optimal trading times
    """
    
    def __init__(self, api_key: str):
        """
        Initialize Volume Profile Analyzer
        
        Args:
            api_key: ChartExchange API key
        """
        self.client = UltimateChartExchangeClient(api_key=api_key)
        logger.info("📊 Volume Profile Analyzer initialized")
    
    def fetch_intraday_volume(self, symbol: str, date: Optional[datetime] = None) -> Optional[VolumeProfile]:
        """
        Fetch and analyze intraday volume profile
        
        Args:
            symbol: Ticker symbol
            date: Date to fetch (defaults to yesterday for most recent complete day)
        
        Returns:
            VolumeProfile object or None if data unavailable
        """
        if date is None:
            # Default to yesterday (most recent complete trading day)
            date = datetime.now() - timedelta(days=1)
        
        try:
            # Fetch 30-minute exchange volume data
            date_str = date.strftime('%Y-%m-%d') if isinstance(date, datetime) else date
            data = self.client.get_exchange_volume_intraday(symbol, date_str)
            
            if not data:
                logger.warning(f"⚠️ No intraday volume data for {symbol} on {date.date()}")
                return None
            
            # Parse windows
            # API returns individual exchange volumes: xnas, xnys, bats, edgx, xadf, etc.
            # Need to calculate on/off exchange totals
            windows = []
            total_volume = 0
            
            # Define lit exchanges (on-exchange) and dark pools (off-exchange)
            lit_exchanges = ['xnas', 'xnys', 'arcx', 'bats', 'edgx', 'edga', 'baty', 'xcis', 'xase', 'xchi', 'xphl', 'xngs', 'iexg', 'eprl', 'memx', 'ltse']
            dark_pools = ['xadf', 'xngs']  # XADF is dark pool, XNGS might be too
            
            for entry in data:
                # Extract time from datetime field
                datetime_str = entry.get('datetime', '')
                if datetime_str:
                    try:
                        dt = datetime.fromisoformat(datetime_str.replace('Z', '+00:00'))
                        time = dt.strftime('%H:%M')
                    except:
                        time = datetime_str.split(' ')[1][:5] if ' ' in datetime_str else ''
                else:
                    time = ''
                
                # Calculate on-exchange total (sum of lit exchanges)
                on_exchange = 0
                for exchange in lit_exchanges:
                    on_exchange += entry.get(exchange, 0)
                
                # Calculate off-exchange total (dark pools + FINRA TRFs)
                # XADF is primary dark pool identifier
                off_exchange = entry.get('xadf', 0)
                
                # Total volume
                total = on_exchange + off_exchange
                
                if total == 0:
                    continue
                
                on_pct = (on_exchange / total) * 100 if total > 0 else 0
                off_pct = (off_exchange / total) * 100 if total > 0 else 0
                
                window = VolumeWindow(
                    time=time,
                    total_volume=total,
                    on_exchange_volume=on_exchange,
                    off_exchange_volume=off_exchange,
                    on_exchange_pct=on_pct,
                    off_exchange_pct=off_pct,
                    is_high_institutional=(off_pct > 60.0),  # >60% off-exchange = dark pool heavy
                    is_low_liquidity=False  # Will set after calculating average
                )
                
                windows.append(window)
                total_volume += total
            
            if not windows:
                logger.warning(f"⚠️ No valid volume windows for {symbol}")
                return None
            
            # Calculate average
            avg_volume = total_volume // len(windows)
            
            # Mark low liquidity windows (<20% of average)
            for window in windows:
                window.is_low_liquidity = (window.total_volume < avg_volume * 0.2)
            
            # Find peak times
            peak_inst_window = max(windows, key=lambda w: w.off_exchange_pct)
            peak_vol_window = max(windows, key=lambda w: w.total_volume)
            
            # Identify time buckets
            low_liq_times = [w.time for w in windows if w.is_low_liquidity]
            high_liq_times = [w.time for w in windows if w.total_volume > avg_volume * 1.5]
            
            profile = VolumeProfile(
                symbol=symbol,
                date=date,
                windows=windows,
                total_volume=total_volume,
                avg_window_volume=avg_volume,
                peak_institutional_time=peak_inst_window.time,
                peak_volume_time=peak_vol_window.time,
                low_liquidity_times=low_liq_times,
                high_liquidity_times=high_liq_times
            )
            
            logger.info(f"✅ Volume profile built for {symbol} on {date.date()}")
            logger.debug(f"   {len(windows)} windows | Total volume: {total_volume:,}")
            logger.debug(f"   Peak institutional: {profile.peak_institutional_time}")
            logger.debug(f"   Peak volume: {profile.peak_volume_time}")
            
            return profile
            
        except Exception as e:
            logger.error(f"❌ Error fetching volume profile for {symbol}: {e}")
            return None
    
    def should_trade_now(self, profile: VolumeProfile) -> Tuple[bool, str]:
        """
        Determine if current time is good for trading based on volume profile
        
        Args:
            profile: VolumeProfile object
        
        Returns:
            (should_trade: bool, reason: str)
        """
        now = datetime.now()
        current_time = now.strftime("%H:%M")
        
        # Check if in low liquidity period
        if current_time in profile.low_liquidity_times:
            return (False, f"Low liquidity period ({current_time})")
        
        # Check if in high liquidity period
        if current_time in profile.high_liquidity_times:
            return (True, f"High liquidity period ({current_time})")
        
        # Default: trade during normal periods
        return (True, "Normal liquidity")
    
    def get_best_entry_times(self, profile: VolumeProfile) -> List[str]:
        """
        Get recommended entry times based on volume profile
        
        Args:
            profile: VolumeProfile object
        
        Returns:
            List of recommended times (e.g., ["09:30", "10:00", "14:00"])
        """
        # Prioritize:
        # 1. High liquidity windows (>150% avg volume)
        # 2. High institutional presence (>60% off-exchange)
        # 3. NOT low liquidity (<20% avg volume)
        
        recommended = []
        
        for window in profile.windows:
            if window.is_low_liquidity:
                continue
            
            # Strong recommendation: high volume + high institutional
            if window.total_volume > profile.avg_window_volume * 1.5 and window.is_high_institutional:
                recommended.append(window.time)
            # Good recommendation: high volume OR high institutional
            elif window.total_volume > profile.avg_window_volume * 1.5 or window.is_high_institutional:
                recommended.append(window.time)
        
        return recommended
    
    def calculate_order_flow_imbalance(self, symbol: str, date: Optional[str] = None) -> Optional[OrderFlowImbalance]:
        """
        Track institutional buy vs sell volume
        
        Note: This requires intraday trades data which may not be available
        in ChartExchange API. This is a placeholder implementation that
        can be enhanced when the endpoint becomes available.
        
        Args:
            symbol: Ticker symbol
            date: Date for analysis (default: today)
        
        Returns:
            OrderFlowImbalance or None if data unavailable
        """
        if date is None:
            date = datetime.now().strftime('%Y-%m-%d')
        
        try:
            # TODO: When ChartExchange adds intraday trades endpoint:
            # trades = self.client.get_intraday_trades(symbol, date)
            # 
            # For now, use dark pool prints as proxy for institutional flow
            # Dark pool buy/sell ratio indicates institutional bias
            
            # Get dark pool prints as proxy
            formatted_symbol = f"US:{symbol.upper()}" if not symbol.startswith('US:') else symbol.upper()
            dp_prints = self.client.get_dark_pool_prints(formatted_symbol, date)
            
            if not dp_prints:
                logger.warning(f"No dark pool prints available for {symbol} on {date}")
                return None
            
            buy_volume = 0
            sell_volume = 0
            
            for print_data in dp_prints:
                if isinstance(print_data, dict):
                    size = int(print_data.get('size', 0))
                    side = print_data.get('side', '').upper()
                    
                    if side == 'B':
                        buy_volume += size
                    elif side == 'S':
                        sell_volume += size
            
            total_volume = buy_volume + sell_volume
            if total_volume == 0:
                return None
            
            net_imbalance = buy_volume - sell_volume
            imbalance_ratio = buy_volume / total_volume if total_volume > 0 else 0.5
            
            # Determine bias
            if imbalance_ratio > 0.6:
                bias = 'BULLISH'
            elif imbalance_ratio < 0.4:
                bias = 'BEARISH'
            else:
                bias = 'NEUTRAL'
            
            return OrderFlowImbalance(
                symbol=symbol,
                date=date,
                buy_volume=buy_volume,
                sell_volume=sell_volume,
                net_imbalance=net_imbalance,
                imbalance_ratio=imbalance_ratio,
                bias=bias
            )
            
        except Exception as e:
            logger.error(f"Error calculating order flow imbalance for {symbol}: {e}")
            return None
    
    def print_profile_summary(self, profile: VolumeProfile):
        """Print a human-readable summary of the volume profile"""
        logger.info("")
        logger.info("=" * 100)
        logger.info(f"📊 VOLUME PROFILE - {profile.symbol} ({profile.date.date()})")
        logger.info("=" * 100)
        logger.info(f"Total Volume: {profile.total_volume:,}")
        logger.info(f"Avg Window Volume: {profile.avg_window_volume:,}")
        logger.info(f"Peak Institutional Time: {profile.peak_institutional_time}")
        logger.info(f"Peak Volume Time: {profile.peak_volume_time}")
        logger.info("")
        logger.info("🔴 LOW LIQUIDITY PERIODS (AVOID):")
        if profile.low_liquidity_times:
            for time in profile.low_liquidity_times:
                logger.info(f"   - {time}")
        else:
            logger.info("   None")
        logger.info("")
        logger.info("🟢 HIGH LIQUIDITY PERIODS (PREFERRED):")
        if profile.high_liquidity_times:
            for time in profile.high_liquidity_times:
                logger.info(f"   - {time}")
        else:
            logger.info("   None")
        logger.info("")
        
        best_times = self.get_best_entry_times(profile)
        logger.info("⭐ RECOMMENDED ENTRY TIMES:")
        if best_times:
            for time in best_times:
                logger.info(f"   - {time}")
        else:
            logger.info("   Standard market hours OK")
        logger.info("=" * 100)
        logger.info("")


if __name__ == "__main__":
    # Test the volume profile analyzer
    logging.basicConfig(level=logging.INFO, format='%(levelname)s:%(name)s:%(message)s')
    
    import sys
    sys.path.append(str(Path(__file__).parent.parent.parent / 'configs'))
    from chartexchange_config import CHARTEXCHANGE_API_KEY
    
    analyzer = VolumeProfileAnalyzer(api_key=CHARTEXCHANGE_API_KEY)
    
    # Test for SPY (yesterday's data)
    yesterday = datetime.now() - timedelta(days=1)
    profile = analyzer.fetch_intraday_volume("SPY", yesterday)
    
    if profile:
        analyzer.print_profile_summary(profile)
        
        # Test current time logic
        should_trade, reason = analyzer.should_trade_now(profile)
        logger.info(f"Should trade now? {should_trade} - {reason}")
    else:
        logger.error("Failed to fetch volume profile")

