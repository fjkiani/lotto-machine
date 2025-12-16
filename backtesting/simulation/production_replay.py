"""
🔄 PRODUCTION REPLAY SIMULATOR
Replays what SHOULD have happened during production runs
"""

from dataclasses import dataclass
from typing import List, Dict, Optional
from datetime import datetime, timedelta
import sys
import os

# Add parent directory for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

@dataclass
class ReplayResult:
    """Result of production replay"""
    date: str
    dp_levels_available: int
    dp_prints_available: int
    expected_signals: int
    actual_signals: int
    missing_signals: List[Dict]
    signal_gap_reasons: List[str]
    threshold_hits: Dict[str, int]

class ProductionReplaySimulator:
    """Replays production runs to identify what should have fired"""
    
    def __init__(self):
        self.api_client = None
        self.signal_engine = None
        self._init_components()
    
    def _init_components(self):
        """Initialize API client and signal engines"""
        try:
            from core.data.ultimate_chartexchange_client import UltimateChartExchangeClient
            import os
            
            api_key = os.getenv('CHARTEXCHANGE_API_KEY')
            if api_key:
                self.api_client = UltimateChartExchangeClient(api_key)
        except Exception as e:
            print(f"⚠️  Failed to initialize API client: {e}")
    
    def replay_session(self, date: str, symbol: str = "SPY") -> ReplayResult:
        """
        Replay what SHOULD have happened during RTH
        
        Args:
            date: Date to replay (YYYY-MM-DD)
            symbol: Symbol to check (default: SPY)
        
        Returns:
            ReplayResult with analysis
        """
        # Get DP data that was available
        dp_levels = self._fetch_dp_levels(date, symbol)
        dp_prints = self._fetch_dp_prints(date, symbol)
        
        # Get actual signals that fired
        actual_signals = self._get_actual_signals(date)
        
        # Simulate what signals SHOULD have been generated
        expected_signals = self._simulate_signal_generation(dp_levels, dp_prints, symbol)
        
        # Compare
        missing_signals = self._find_missing_signals(expected_signals, actual_signals)
        gap_reasons = self._analyze_gap(dp_levels, actual_signals, expected_signals)
        
        # Analyze threshold hits
        threshold_hits = self._analyze_threshold_hits(dp_levels)
        
        return ReplayResult(
            date=date,
            dp_levels_available=len(dp_levels),
            dp_prints_available=len(dp_prints),
            expected_signals=len(expected_signals),
            actual_signals=len(actual_signals),
            missing_signals=missing_signals,
            signal_gap_reasons=gap_reasons,
            threshold_hits=threshold_hits
        )
    
    def _fetch_dp_levels(self, date: str, symbol: str) -> List[Dict]:
        """Fetch DP levels for date"""
        if not self.api_client:
            return []
        
        try:
            levels = self.api_client.get_dark_pool_levels(symbol, date)
            return levels if levels else []
        except Exception as e:
            print(f"⚠️  Error fetching DP levels: {e}")
            return []
    
    def _fetch_dp_prints(self, date: str, symbol: str) -> List[Dict]:
        """Fetch DP prints for date"""
        if not self.api_client:
            return []
        
        try:
            prints = self.api_client.get_dark_pool_prints(symbol, date)
            return prints if prints else []
        except Exception as e:
            print(f"⚠️  Error fetching DP prints: {e}")
            return []
    
    def _get_actual_signals(self, date: str) -> List[Dict]:
        """Get signals that actually fired during RTH"""
        import sqlite3
        
        conn = sqlite3.connect("data/alerts_history.db")
        cursor = conn.cursor()
        
        start = f"{date}T09:30:00"
        end = f"{date}T16:00:00"
        
        cursor.execute('''
            SELECT timestamp, alert_type, symbol, title
            FROM alerts
            WHERE timestamp >= ? AND timestamp < ?
            ORDER BY timestamp ASC
        ''', [start, end])
        
        signals = []
        for row in cursor.fetchall():
            signals.append({
                'timestamp': row[0],
                'alert_type': row[1],
                'symbol': row[2],
                'title': row[3]
            })
        
        conn.close()
        return signals
    
    def _simulate_signal_generation(self, dp_levels: List[Dict], 
                                    dp_prints: List[Dict], 
                                    symbol: str) -> List[Dict]:
        """Simulate what signals SHOULD have been generated"""
        expected = []
        
        # Check for battlegrounds (levels with significant volume)
        for level in dp_levels:
            volume = level.get('volume', 0)
            price = level.get('price', 0)
            level_type = level.get('level_type', '')
            
            # Thresholds from production system
            if volume >= 500_000:  # Moderate battleground
                expected.append({
                    'type': 'dp_alert',
                    'symbol': symbol,
                    'price': price,
                    'volume': volume,
                    'level_type': level_type,
                    'reason': f'Battleground at ${price:.2f} with {volume:,} shares'
                })
        
        return expected
    
    def _find_missing_signals(self, expected: List[Dict], actual: List[Dict]) -> List[Dict]:
        """Find signals that should have fired but didn't"""
        # Simplistic comparison - just count
        if len(actual) < len(expected):
            return expected[len(actual):]
        return []
    
    def _analyze_gap(self, dp_levels: List[Dict], actual: List[Dict], 
                    expected: List[Dict]) -> List[str]:
        """Analyze why there's a gap between expected and actual"""
        reasons = []
        
        if not dp_levels:
            reasons.append("❌ NO DP DATA AVAILABLE - API returned empty")
        elif len(expected) == 0:
            reasons.append("⚠️  DP data available but no battlegrounds met threshold (500K+ shares)")
        elif len(actual) == 0 and len(expected) > 0:
            reasons.append(f"❌ {len(expected)} signals SHOULD have fired but didn't")
            reasons.append("   → Check signal generation logic")
            reasons.append("   → Check market hours detection")
            reasons.append("   → Check if system was actually running during RTH")
        elif len(actual) < len(expected):
            reasons.append(f"⚠️  Only {len(actual)}/{len(expected)} expected signals fired")
            reasons.append("   → Some battlegrounds were filtered out")
        
        return reasons
    
    def _analyze_threshold_hits(self, dp_levels: List[Dict]) -> Dict[str, int]:
        """Analyze how many levels hit different thresholds"""
        hits = {
            '500k_plus': 0,
            '1m_plus': 0,
            '2m_plus': 0,
            '5m_plus': 0
        }
        
        for level in dp_levels:
            volume = level.get('volume', 0)
            if volume >= 5_000_000:
                hits['5m_plus'] += 1
            if volume >= 2_000_000:
                hits['2m_plus'] += 1
            if volume >= 1_000_000:
                hits['1m_plus'] += 1
            if volume >= 500_000:
                hits['500k_plus'] += 1
        
        return hits


