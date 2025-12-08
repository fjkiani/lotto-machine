#!/usr/bin/env python3
"""
🎯 TRADYTICS SYNTHESIS ENGINE
Combines insights from all specialized Tradytics agents into unified market intelligence
"""

import logging
from typing import Dict, List, Any, Optional
from datetime import datetime, timedelta
from collections import defaultdict

logger = logging.getLogger(__name__)

class TradyticsSynthesisEngine:
    """
    Synthesizes signals from all Tradytics agents into comprehensive market view
    """

    def __init__(self):
        self.signal_history = []
        self.max_history = 100

        # Synthesis weights for different agent types
        self.agent_weights = {
            'options_sweeps': 0.25,    # High weight - institutional options flow
            'darkpool': 0.20,          # High weight - block trades
            'golden_sweeps': 0.15,     # Institutional conviction
            'bullseye': 0.15,          # Multi-timeframe confluence
            'insider_trades': 0.10,    # Corporate intelligence
            'analyst_grades': 0.08,    # Institutional ratings
            'important_news': 0.07     # Catalyst identification
        }

        # Market regime tracking
        self.current_regime = 'neutral'
        self.regime_signals = []

    def add_signal(self, agent_signal: Dict[str, Any]) -> Dict[str, Any]:
        """Add a new agent signal and generate synthesis"""
        # Add timestamp
        agent_signal['synthesis_timestamp'] = datetime.now().isoformat()

        # Add to history
        self.signal_history.append(agent_signal)
        if len(self.signal_history) > self.max_history:
            self.signal_history.pop(0)

        # Generate comprehensive synthesis
        synthesis = self._synthesize_signals()

        return {
            'individual_signal': agent_signal,
            'market_synthesis': synthesis,
            'regime_assessment': self._assess_market_regime(),
            'correlation_analysis': self._analyze_correlations(),
            'timestamp': datetime.now().isoformat()
        }

    def _synthesize_signals(self) -> Dict[str, Any]:
        """Synthesize all recent signals into market intelligence"""
        if not self.signal_history:
            return {'status': 'no_signals', 'message': 'Waiting for agent signals'}

        # Get recent signals (last 30 minutes)
        recent_cutoff = datetime.now() - timedelta(minutes=30)
        recent_signals = [
            s for s in self.signal_history
            if datetime.fromisoformat(s['synthesis_timestamp']) > recent_cutoff
        ]

        if not recent_signals:
            return {'status': 'no_recent_signals', 'message': 'No signals in last 30 minutes'}

        # Aggregate by direction and confidence
        direction_counts = defaultdict(float)
        symbol_signals = defaultdict(list)
        agent_contributions = defaultdict(list)

        total_weighted_confidence = 0
        total_weight = 0

        for signal in recent_signals:
            feed_type = signal.get('feed_type', 'unknown')
            analysis = signal.get('analysis', {})
            confidence = analysis.get('confidence', 0.5)
            direction = analysis.get('direction', 'neutral')

            # Apply agent weight
            weight = self.agent_weights.get(feed_type, 0.05)
            weighted_confidence = confidence * weight

            direction_counts[direction] += weighted_confidence
            total_weighted_confidence += weighted_confidence
            total_weight += weight

            # Track symbols
            symbols = signal.get('parsed_data', {}).get('symbols', [])
            for symbol in symbols:
                symbol_signals[symbol].append({
                    'direction': direction,
                    'confidence': confidence,
                    'feed_type': feed_type,
                    'timestamp': signal['synthesis_timestamp']
                })

            # Track agent contributions
            agent_contributions[feed_type].append({
                'confidence': confidence,
                'direction': direction,
                'symbols': symbols
            })

        # Determine overall market direction
        if total_weighted_confidence == 0:
            overall_direction = 'neutral'
            overall_confidence = 0.5
        else:
            max_direction = max(direction_counts.keys(), key=lambda k: direction_counts[k])
            overall_direction = max_direction
            overall_confidence = direction_counts[max_direction] / total_weight

        # Identify key symbols with confluence
        key_symbols = []
        for symbol, signals in symbol_signals.items():
            if len(signals) >= 2:  # At least 2 signals for confluence
                bullish_signals = sum(1 for s in signals if s['direction'] == 'bullish')
                bearish_signals = sum(1 for s in signals if s['direction'] == 'bearish')

                if bullish_signals > bearish_signals:
                    symbol_direction = 'bullish'
                    symbol_strength = bullish_signals / len(signals)
                elif bearish_signals > bullish_signals:
                    symbol_direction = 'bearish'
                    symbol_strength = bearish_signals / len(signals)
                else:
                    symbol_direction = 'mixed'
                    symbol_strength = 0.5

                key_symbols.append({
                    'symbol': symbol,
                    'direction': symbol_direction,
                    'strength': symbol_strength,
                    'signal_count': len(signals),
                    'feeds': list(set(s['feed_type'] for s in signals))
                })

        # Sort by strength
        key_symbols.sort(key=lambda x: x['strength'], reverse=True)

        return {
            'overall_direction': overall_direction,
            'overall_confidence': min(overall_confidence, 1.0),
            'signal_count': len(recent_signals),
            'time_window': '30_minutes',
            'key_symbols': key_symbols[:5],  # Top 5 symbols
            'agent_breakdown': dict(agent_contributions),
            'market_themes': self._identify_market_themes(recent_signals),
            'risk_assessment': self._assess_risk_level(recent_signals),
            'trading_opportunities': self._identify_opportunities(key_symbols, overall_direction)
        }

    def _identify_market_themes(self, signals: List[Dict]) -> List[str]:
        """Identify overarching market themes from signal patterns"""
        themes = []

        # Check for institutional accumulation theme
        inst_signals = [s for s in signals if s.get('feed_type') in ['darkpool', 'golden_sweeps', 'insider_trades']]
        if len(inst_signals) >= 3:
            bullish_inst = sum(1 for s in inst_signals if s.get('analysis', {}).get('direction') == 'bullish')
            if bullish_inst >= len(inst_signals) * 0.6:
                themes.append('institutional_accumulation')

        # Check for options gamma theme
        options_signals = [s for s in signals if s.get('feed_type') == 'options_sweeps']
        if options_signals:
            gex_impacts = [s.get('analysis', {}).get('gex_impact') for s in options_signals]
            if gex_impacts.count('negative') > gex_impacts.count('positive'):
                themes.append('negative_gamma_exposure')
            elif gex_impacts.count('positive') > gex_impacts.count('negative'):
                themes.append('positive_gamma_exposure')

        # Check for news catalyst theme
        news_signals = [s for s in signals if s.get('feed_type') == 'important_news']
        if news_signals:
            themes.append('news_catalysts_active')

        return themes

    def _assess_risk_level(self, signals: List[Dict]) -> Dict[str, Any]:
        """Assess overall market risk level"""
        high_confidence_signals = [s for s in signals if s.get('analysis', {}).get('confidence', 0) > 0.7]

        if len(high_confidence_signals) >= 5:
            risk_level = 'high'
            rationale = 'Multiple high-confidence signals indicating strong directional move'
        elif len(high_confidence_signals) >= 3:
            risk_level = 'medium'
            rationale = 'Several confident signals suggesting moderate market movement'
        else:
            risk_level = 'low'
            rationale = 'Limited high-confidence signals, market relatively stable'

        return {
            'level': risk_level,
            'rationale': rationale,
            'high_confidence_count': len(high_confidence_signals)
        }

    def _identify_opportunities(self, key_symbols: List[Dict], overall_direction: str) -> List[Dict]:
        """Identify specific trading opportunities"""
        opportunities = []

        for symbol_data in key_symbols[:3]:  # Top 3 symbols
            if symbol_data['strength'] > 0.7 and symbol_data['signal_count'] >= 3:
                opportunities.append({
                    'symbol': symbol_data['symbol'],
                    'direction': symbol_data['direction'],
                    'confidence': symbol_data['strength'],
                    'rationale': f"Strong {symbol_data['direction']} confluence from {symbol_data['signal_count']} feeds",
                    'feeds': symbol_data['feeds']
                })

        return opportunities

    def _assess_market_regime(self) -> Dict[str, Any]:
        """Assess current market regime based on signal patterns"""
        if len(self.signal_history) < 10:
            return {'regime': 'insufficient_data', 'confidence': 0.0}

        recent_signals = self.signal_history[-10:]

        # Analyze directional consistency
        directions = [s.get('analysis', {}).get('direction', 'neutral') for s in recent_signals]
        bullish_ratio = directions.count('bullish') / len(directions)
        bearish_ratio = directions.count('bearish') / len(directions)

        if bullish_ratio > 0.7:
            regime = 'strongly_bullish'
            confidence = bullish_ratio
        elif bearish_ratio > 0.7:
            regime = 'strongly_bearish'
            confidence = bearish_ratio
        elif bullish_ratio > 0.5:
            regime = 'moderately_bullish'
            confidence = bullish_ratio
        elif bearish_ratio > 0.5:
            regime = 'moderately_bearish'
            confidence = bearish_ratio
        else:
            regime = 'neutral_choppy'
            confidence = 1.0 - max(bullish_ratio, bearish_ratio)

        return {
            'regime': regime,
            'confidence': confidence,
            'bullish_ratio': bullish_ratio,
            'bearish_ratio': bearish_ratio,
            'sample_size': len(recent_signals)
        }

    def _analyze_correlations(self) -> Dict[str, Any]:
        """Analyze correlations between different signal types"""
        if len(self.signal_history) < 20:
            return {'status': 'insufficient_data'}

        # Analyze which agent types tend to signal together
        agent_pairs = defaultdict(int)

        recent_signals = self.signal_history[-20:]
        for i, signal1 in enumerate(recent_signals):
            for signal2 in recent_signals[i+1:]:
                if signal1['feed_type'] != signal2['feed_type']:
                    key = tuple(sorted([signal1['feed_type'], signal2['feed_type']]))
                    # Check if they agree on direction
                    dir1 = signal1.get('analysis', {}).get('direction')
                    dir2 = signal2.get('analysis', {}).get('direction')
                    if dir1 == dir2 and dir1 != 'neutral':
                        agent_pairs[key] += 1

        # Find strongest correlations
        correlations = []
        for agent_pair, agreement_count in agent_pairs.items():
            if agreement_count >= 3:  # At least 3 agreements
                correlations.append({
                    'agents': list(agent_pair),
                    'agreement_count': agreement_count,
                    'strength': agreement_count / 10  # Normalize
                })

        correlations.sort(key=lambda x: x['strength'], reverse=True)

        return {
            'correlations': correlations[:5],  # Top 5 correlations
            'analysis_window': 20
        }

    def get_comprehensive_market_view(self) -> Dict[str, Any]:
        """Get the complete synthesized market intelligence"""
        return {
            'synthesis': self._synthesize_signals(),
            'regime': self._assess_market_regime(),
            'correlations': self._analyze_correlations(),
            'signal_history_summary': {
                'total_signals': len(self.signal_history),
                'recent_signals': len([s for s in self.signal_history
                                      if datetime.fromisoformat(s['synthesis_timestamp']) >
                                      datetime.now() - timedelta(hours=1)]),
                'agent_distribution': self._get_agent_distribution()
            },
            'timestamp': datetime.now().isoformat()
        }

    def _get_agent_distribution(self) -> Dict[str, int]:
        """Get distribution of signals by agent type"""
        distribution = defaultdict(int)
        for signal in self.signal_history[-50:]:  # Last 50 signals
            distribution[signal.get('feed_type', 'unknown')] += 1
        return dict(distribution)
