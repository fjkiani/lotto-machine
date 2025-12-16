"""
📊 SIGNAL ANALYZER
Analyzes production signals to understand what fired and why
"""

from dataclasses import dataclass
from typing import List, Dict, Optional
from datetime import datetime
from ..data.alerts_loader import SignalAlert

@dataclass
class SignalSummary:
    """Summary of signals for a date"""
    date: str
    total_signals: int
    signal_types: Dict[str, int]
    symbols: Dict[str, int]
    synthesis_signals: int
    narrative_brain_signals: int
    dp_alerts: int
    high_quality_signals: int  # Confluence >= 70
    avg_confluence: float
    signals_by_hour: Dict[int, int]
    signals: List[SignalAlert]

class SignalAnalyzer:
    """Analyzes production signals"""
    
    @staticmethod
    def analyze_signals(signals: List[SignalAlert], date: str) -> SignalSummary:
        """Analyze a list of signals"""
        if not signals:
            return SignalSummary(
                date=date,
                total_signals=0,
                signal_types={},
                symbols={},
                synthesis_signals=0,
                narrative_brain_signals=0,
                dp_alerts=0,
                high_quality_signals=0,
                avg_confluence=0.0,
                signals_by_hour={},
                signals=[]
            )
        
        # Count by type
        signal_types = {}
        symbols = {}
        synthesis_count = 0
        narrative_count = 0
        dp_count = 0
        high_quality = 0
        confluence_scores = []
        signals_by_hour = {}
        
        for signal in signals:
            # Count types
            signal_types[signal.alert_type] = signal_types.get(signal.alert_type, 0) + 1
            
            # Count symbols
            symbols[signal.symbol] = symbols.get(signal.symbol, 0) + 1
            
            # Count specific types
            if signal.alert_type == 'synthesis':
                synthesis_count += 1
            elif signal.alert_type == 'narrative_brain':
                narrative_count += 1
            elif signal.alert_type == 'dp_alert':
                dp_count += 1
            
            # Count high quality
            if signal.confluence_score and signal.confluence_score >= 70:
                high_quality += 1
            
            # Collect confluence scores
            if signal.confluence_score:
                confluence_scores.append(signal.confluence_score)
            
            # Count by hour
            hour = signal.timestamp.hour
            signals_by_hour[hour] = signals_by_hour.get(hour, 0) + 1
        
        avg_confluence = sum(confluence_scores) / len(confluence_scores) if confluence_scores else 0.0
        
        return SignalSummary(
            date=date,
            total_signals=len(signals),
            signal_types=signal_types,
            symbols=symbols,
            synthesis_signals=synthesis_count,
            narrative_brain_signals=narrative_count,
            dp_alerts=dp_count,
            high_quality_signals=high_quality,
            avg_confluence=avg_confluence,
            signals_by_hour=signals_by_hour,
            signals=signals
        )
    
    @staticmethod
    def get_key_signals(signals: List[SignalAlert], min_confluence: float = 70.0) -> List[SignalAlert]:
        """Get high-quality signals (synthesis, narrative brain, or high confluence)"""
        key_signals = []
        
        for signal in signals:
            is_key = False
            
            # Synthesis and narrative brain are always key
            if signal.alert_type in ['synthesis', 'narrative_brain']:
                is_key = True
            
            # High confluence DP alerts
            elif signal.confluence_score and signal.confluence_score >= min_confluence:
                is_key = True
            
            if is_key:
                key_signals.append(signal)
        
        return key_signals
    
    @staticmethod
    def get_tradeable_signals(signals: List[SignalAlert]) -> List[SignalAlert]:
        """Get signals with complete trade setup (entry, stop, target)"""
        tradeable = []
        
        for signal in signals:
            if signal.entry_price and signal.stop_loss and signal.take_profit:
                tradeable.append(signal)
        
        return tradeable
    
    @staticmethod
    def analyze_timing(signals: List[SignalAlert]) -> Dict[str, any]:
        """Analyze signal timing patterns"""
        if not signals:
            return {}
        
        # Group by hour
        by_hour = {}
        for signal in signals:
            hour = signal.timestamp.hour
            if hour not in by_hour:
                by_hour[hour] = []
            by_hour[hour].append(signal)
        
        # Find peak hours
        peak_hours = sorted(by_hour.items(), key=lambda x: len(x[1]), reverse=True)[:3]
        
        return {
            'peak_hours': [h for h, _ in peak_hours],
            'signals_by_hour': {h: len(sigs) for h, sigs in by_hour.items()},
            'first_signal': signals[0].timestamp if signals else None,
            'last_signal': signals[-1].timestamp if signals else None
        }


