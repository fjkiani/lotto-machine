"""
MOAT Chart Engine - Competitive Advantage Charting System
==========================================================

Multi-layer intelligence charting that combines ALL our capabilities:
- Dark Pool Intelligence (levels, battlegrounds, flow)
- Gamma Intelligence (flip, max pain, dealer positioning)
- Options Flow (call/put accumulation, unusual activity)
- Short Squeeze (SI, borrow fees, FTDs)
- Signal Markers (entry/exit with context)
- Institutional Context (buying pressure, squeeze potential, gamma pressure)
- Regime Detection (trend, time-of-day, VIX)
- Volume Profile (institutional timing)
- News/Events (economic calendar, Fed Watch)
- Historical Learning (DP bounce rates, pattern recognition)
- Reddit Sentiment (contrarian signals)

Charts update ONLY when signals are generated or levels change - FULL CONTROL!
"""

import plotly.graph_objects as go
import plotly.express as px
import pandas as pd
import numpy as np
from typing import List, Optional, Dict, Any, Union
from dataclasses import dataclass, field
from datetime import datetime, timedelta
import logging
import sys
from pathlib import Path

# Add paths for imports
sys.path.append(str(Path(__file__).parent.parent.parent / 'core'))
sys.path.append(str(Path(__file__).parent.parent.parent / 'live_monitoring' / 'core'))

logger = logging.getLogger(__name__)

# Import our intelligence modules
try:
    from core.data.ultimate_chartexchange_client import UltimateChartExchangeClient
    from core.ultra_institutional_engine import InstitutionalContext, UltraInstitutionalEngine
    from live_monitoring.core.signal_generator import SignalGenerator, LiveSignal, LotterySignal
    from live_monitoring.core.lottery_signals import SignalType, SignalAction
    from live_monitoring.core.gamma_exposure import GammaExposureTracker, GammaExposureData
    from live_monitoring.exploitation.squeeze_detector import SqueezeDetector, SqueezeSignal
    from live_monitoring.exploitation.gamma_tracker import GammaTracker, GammaSignal
    from live_monitoring.orchestrator.checkers.options_flow_checker import OptionsFlowChecker
    from live_monitoring.core.volume_profile import VolumeProfileAnalyzer
    from live_monitoring.core.reddit_sentiment import RedditSentimentAnalyzer
    from live_monitoring.agents.economic_exploit_engine import EconomicExploitSignal
    INTELLIGENCE_AVAILABLE = True
except ImportError as e:
    logger.warning(f"Some intelligence modules not available: {e}")
    INTELLIGENCE_AVAILABLE = False


@dataclass
class DPLevel:
    """Dark Pool Level with full context"""
    price: float
    volume: int
    type: str  # 'SUPPORT', 'RESISTANCE', 'BATTLEGROUND'
    strength: str  # 'WEAK', 'MODERATE', 'STRONG'
    buy_sell_ratio: Optional[float] = None  # Institutional sentiment at this level
    is_battleground: bool = False  # >1M shares


@dataclass
class SignalMarker:
    """Signal marker for chart visualization"""
    timestamp: datetime
    price: float
    signal_type: str  # SQUEEZE, GAMMA_RAMP, BREAKOUT, BOUNCE, SELLOFF, RALLY, etc.
    action: str  # 'BUY' or 'SELL'
    confidence: float  # 0-1
    entry_price: float
    target_price: Optional[float] = None
    stop_price: Optional[float] = None
    risk_reward: Optional[float] = None
    rationale: str = ""
    supporting_factors: List[str] = field(default_factory=list)


@dataclass
class OptionsFlowZone:
    """Options flow accumulation zone"""
    price_min: float
    price_max: float
    call_volume: int
    put_volume: int
    put_call_ratio: float
    unusual_activity: bool = False


@dataclass
class SqueezeZone:
    """Short squeeze zone"""
    price_min: float
    price_max: float
    short_interest: float
    borrow_fee: float
    days_to_cover: Optional[float] = None
    ftd_spike: Optional[float] = None


@dataclass
class MOATIntelligence:
    """Complete intelligence package for charting"""
    # Dark Pool
    dp_levels: List[DPLevel] = field(default_factory=list)
    dp_buy_sell_ratio: float = 1.0
    dark_pool_pct: float = 0.0
    
    # Gamma
    gamma_flip: Optional[float] = None
    max_pain: Optional[float] = None
    gamma_regime: str = 'NEUTRAL'  # 'POSITIVE', 'NEGATIVE', 'NEUTRAL'
    
    # Options Flow
    options_flow_zones: List[OptionsFlowZone] = field(default_factory=list)
    unusual_activity: List[Dict] = field(default_factory=list)
    
    # Squeeze
    squeeze_zones: List[SqueezeZone] = field(default_factory=list)
    squeeze_signals: List[SqueezeSignal] = field(default_factory=list)
    
    # Signals
    signals: List[SignalMarker] = field(default_factory=list)
    
    # Institutional Context
    buying_pressure: float = 0.0
    squeeze_potential: float = 0.0
    gamma_pressure: float = 0.0
    composite_score: float = 0.0
    
    # Regime
    regime: str = 'CHOPPY'  # 'UPTREND', 'DOWNTREND', 'CHOPPY'
    time_of_day: str = 'MIDDAY'  # 'MORNING', 'MIDDAY', 'AFTERNOON'
    vix_level: Optional[float] = None
    
    # Volume Profile
    peak_institutional_times: List[str] = field(default_factory=list)
    volume_profile_data: Optional[pd.DataFrame] = None
    
    # News/Events
    upcoming_events: List[Dict] = field(default_factory=list)
    fed_watch_probability: Optional[float] = None
    
    # Historical Learning
    dp_bounce_rates: Dict[float, float] = field(default_factory=dict)  # price -> bounce_rate
    
    # Reddit Sentiment
    reddit_sentiment: str = 'NEUTRAL'  # 'BULLISH', 'BEARISH', 'NEUTRAL'
    reddit_mentions: int = 0
    contrarian_signal: Optional[str] = None
    
    # Price Data
    current_price: float = 0.0
    vwap: Optional[float] = None


class MOATChartEngine:
    """
    Multi-layer intelligence charting engine.
    
    Combines ALL our capabilities into one unbeatable chart.
    Charts update ONLY when you explicitly call create_chart() - FULL CONTROL!
    """
    
    def __init__(self, api_key: Optional[str] = None):
        """Initialize MOAT chart engine with all intelligence sources"""
        self.api_key = api_key
        
        # Initialize intelligence sources (if available)
        if INTELLIGENCE_AVAILABLE and api_key:
            try:
                self.dp_client = UltimateChartExchangeClient(api_key, tier=3)
                self.inst_engine = UltraInstitutionalEngine(api_key)
                self.gamma_tracker = GammaExposureTracker(api_key)
                self.squeeze_detector = SqueezeDetector(self.dp_client)
                self.volume_analyzer = VolumeProfileAnalyzer(api_key)
                self.sentiment_analyzer = RedditSentimentAnalyzer(api_key)
                logger.info("✅ MOAT Chart Engine initialized with all intelligence sources")
            except Exception as e:
                logger.warning(f"⚠️  Some intelligence sources failed to initialize: {e}")
                self.dp_client = None
                self.inst_engine = None
        else:
            self.dp_client = None
            self.inst_engine = None
            logger.warning("⚠️  MOAT Chart Engine initialized in limited mode (no API key)")
    
    def gather_all_intelligence(
        self,
        ticker: str,
        date: Optional[str] = None,
        current_price: Optional[float] = None,
    ) -> MOATIntelligence:
        """
        Gather ALL intelligence from every source.
        
        This is the "MOAT" - combining 10+ data sources into one intelligence package.
        """
        intelligence = MOATIntelligence()
        date = date or datetime.now().strftime('%Y-%m-%d')
        
        try:
            # Get current price if not provided
            if current_price is None:
                import yfinance as yf
                ticker_obj = yf.Ticker(ticker)
                current_price = ticker_obj.history(period='1d')['Close'].iloc[-1]
            intelligence.current_price = current_price
            
            # 1. Dark Pool Intelligence
            if self.dp_client:
                try:
                    dp_levels_data = self.dp_client.get_dark_pool_levels(ticker, date)
                    dp_summary = self.dp_client.get_dark_pool_summary(ticker, date)
                    
                    # Convert to DPLevel objects
                    for level_data in dp_levels_data[:100]:  # Top 100 levels
                        price = float(level_data.get('level') or level_data.get('price', 0))
                        volume = int(level_data.get('volume', 0))
                        
                        # Determine type and strength
                        if volume >= 1_000_000:
                            level_type = 'BATTLEGROUND'
                            strength = 'STRONG'
                            is_battleground = True
                        elif price < current_price:
                            level_type = 'SUPPORT'
                            strength = 'STRONG' if volume >= 500_000 else 'MODERATE' if volume >= 200_000 else 'WEAK'
                            is_battleground = False
                        else:
                            level_type = 'RESISTANCE'
                            strength = 'STRONG' if volume >= 500_000 else 'MODERATE' if volume >= 200_000 else 'WEAK'
                            is_battleground = False
                        
                        intelligence.dp_levels.append(DPLevel(
                            price=price,
                            volume=volume,
                            type=level_type,
                            strength=strength,
                            is_battleground=is_battleground,
                        ))
                    
                    # Get DP summary
                    if dp_summary:
                        buy_vol = dp_summary.buy_volume
                        sell_vol = dp_summary.sell_volume
                        if sell_vol > 0:
                            intelligence.dp_buy_sell_ratio = buy_vol / sell_vol
                        intelligence.dark_pool_pct = getattr(dp_summary, 'dark_pool_pct', 0.0)
                except Exception as e:
                    logger.warning(f"Failed to fetch DP intelligence: {e}")
            
            # 2. Gamma Intelligence
            if hasattr(self, 'gamma_tracker') and self.gamma_tracker:
                try:
                    gamma_data = self.gamma_tracker.calculate_gamma_exposure(ticker, date)
                    if gamma_data:
                        intelligence.gamma_flip = gamma_data.get('gamma_flip_level')
                        intelligence.gamma_regime = gamma_data.get('current_regime', 'NEUTRAL')
                except Exception as e:
                    logger.warning(f"Failed to fetch gamma intelligence: {e}")
            
            # 3. Options Flow (if available)
            # TODO: Integrate OptionsFlowChecker when available
            
            # 4. Squeeze Intelligence
            if hasattr(self, 'squeeze_detector') and self.squeeze_detector:
                try:
                    squeeze_signal = self.squeeze_detector.analyze(ticker)
                    if squeeze_signal and squeeze_signal.score > 50:
                        intelligence.squeeze_zones.append(SqueezeZone(
                            price_min=current_price * 0.98,
                            price_max=current_price * 1.02,
                            short_interest=squeeze_signal.short_interest,
                            borrow_fee=squeeze_signal.borrow_fee,
                            days_to_cover=squeeze_signal.days_to_cover,
                        ))
                        intelligence.squeeze_signals.append(squeeze_signal)
                except Exception as e:
                    logger.warning(f"Failed to fetch squeeze intelligence: {e}")
            
            # 5. Institutional Context
            if self.inst_engine:
                try:
                    context = self.inst_engine.build_institutional_context(ticker, date)
                    if context:
                        intelligence.buying_pressure = context.institutional_buying_pressure
                        intelligence.squeeze_potential = context.squeeze_potential
                        intelligence.gamma_pressure = context.gamma_pressure
                        intelligence.max_pain = context.max_pain
                        intelligence.composite_score = (
                            intelligence.buying_pressure * 0.4 +
                            intelligence.squeeze_potential * 0.3 +
                            intelligence.gamma_pressure * 0.3
                        )
                except Exception as e:
                    logger.warning(f"Failed to fetch institutional context: {e}")
            
            # 6. Regime Detection (simplified)
            # TODO: Integrate full RegimeDetector
            
            # 7. Volume Profile
            if hasattr(self, 'volume_analyzer') and self.volume_analyzer:
                try:
                    profile = self.volume_analyzer.fetch_intraday_volume(ticker, date)
                    if profile:
                        intelligence.volume_profile_data = profile.get('data')
                        intelligence.peak_institutional_times = profile.get('peak_times', [])
                except Exception as e:
                    logger.warning(f"Failed to fetch volume profile: {e}")
            
            # 8. Reddit Sentiment
            if hasattr(self, 'sentiment_analyzer') and self.sentiment_analyzer:
                try:
                    sentiment_data = self.sentiment_analyzer.fetch_reddit_sentiment(ticker, days=7)
                    if sentiment_data:
                        intelligence.reddit_sentiment = sentiment_data.get('sentiment', 'NEUTRAL')
                        intelligence.reddit_mentions = sentiment_data.get('total_mentions', 0)
                except Exception as e:
                    logger.warning(f"Failed to fetch Reddit sentiment: {e}")
            
            logger.info(f"✅ Intelligence gathered: {len(intelligence.dp_levels)} DP levels, "
                       f"{len(intelligence.signals)} signals, "
                       f"Buying Pressure: {intelligence.buying_pressure:.0%}")
            
        except Exception as e:
            logger.error(f"Error gathering intelligence: {e}", exc_info=True)
        
        return intelligence
    
    def create_moat_chart(
        self,
        ticker: str,
        candlestick_data: pd.DataFrame,
        intelligence: Optional[MOATIntelligence] = None,
        signals: Optional[List[Union[LiveSignal, LotterySignal]]] = None,
    ) -> go.Figure:
        """
        Create complete MOAT chart with ALL intelligence layers.
        
        Chart ONLY updates when you call this function - FULL CONTROL!
        
        Args:
            ticker: Stock ticker symbol
            candlestick_data: DataFrame with Date, Open, High, Low, Close, Volume
            intelligence: Pre-gathered intelligence (optional, will gather if not provided)
            signals: List of LiveSignal/LotterySignal objects to visualize
        
        Returns:
            go.Figure: Complete MOAT chart
        """
        # Gather intelligence if not provided
        if intelligence is None:
            current_price = candlestick_data['Close'].iloc[-1] if len(candlestick_data) > 0 else 0
            intelligence = self.gather_all_intelligence(ticker, current_price=current_price)
        
        # Convert signals to markers
        if signals:
            for signal in signals:
                intelligence.signals.append(SignalMarker(
                    timestamp=signal.timestamp,
                    price=signal.entry_price,
                    signal_type=signal.signal_type.value if hasattr(signal.signal_type, 'value') else str(signal.signal_type),
                    action=signal.action.value if hasattr(signal.action, 'value') else str(signal.action),
                    confidence=signal.confidence,
                    entry_price=signal.entry_price,
                    target_price=signal.target_price,
                    stop_price=signal.stop_price,
                    risk_reward=signal.risk_reward_ratio,
                    rationale=signal.rationale,
                    supporting_factors=signal.supporting_factors,
                ))
        
        # Create base chart
        fig = self._create_base_chart(ticker, candlestick_data, intelligence)
        
        # Add all intelligence layers
        fig = self._add_dp_intelligence(fig, intelligence)
        fig = self._add_gamma_intelligence(fig, intelligence)
        fig = self._add_options_flow(fig, intelligence)
        fig = self._add_squeeze_intelligence(fig, intelligence)
        fig = self._add_signal_markers(fig, intelligence)
        fig = self._add_institutional_context(fig, intelligence)
        fig = self._add_regime_indicator(fig, intelligence)
        fig = self._add_volume_profile(fig, intelligence, candlestick_data)
        fig = self._add_news_events(fig, intelligence)
        fig = self._add_historical_learning(fig, intelligence)
        fig = self._add_sentiment(fig, intelligence)
        
        # Apply professional styling
        fig = self._apply_moat_styling(fig, intelligence)
        
        return fig
    
    def _create_base_chart(
        self,
        ticker: str,
        df: pd.DataFrame,
        intelligence: MOATIntelligence,
    ) -> go.Figure:
        """Create base candlestick chart with volume"""
        fig = go.Figure()
        
        # Ensure Date is index or column
        if 'Date' not in df.columns and not isinstance(df.index, pd.DatetimeIndex):
            raise ValueError("DataFrame must have 'Date' column or DatetimeIndex")
        
        if isinstance(df.index, pd.DatetimeIndex):
            dates = df.index
        else:
            dates = pd.to_datetime(df['Date'])
        
        # Candlestick with professional colors
        fig.add_trace(go.Candlestick(
            x=dates,
            open=df['Open'],
            high=df['High'],
            low=df['Low'],
            close=df['Close'],
            name='Price',
            increasing_line_color='#00ff88',
            decreasing_line_color='#ff3366',
            increasing_fillcolor='#00ff8840',
            decreasing_fillcolor='#ff336640',
        ))
        
        # Volume bars
        if 'Volume' in df.columns:
            fig.add_trace(go.Bar(
                x=dates,
                y=df['Volume'],
                name='Volume',
                marker_color='rgba(0, 212, 255, 0.3)',
                opacity=0.3,
                yaxis='y2',
            ))
        
        return fig
    
    def _add_dp_intelligence(self, fig: go.Figure, intelligence: MOATIntelligence) -> go.Figure:
        """Add Dark Pool levels with strength-based styling"""
        for level in intelligence.dp_levels:
            color = self._get_dp_color(level)
            line_width = self._get_line_width(level.strength)
            line_style = 'dashdot' if level.is_battleground else 'dash'
            
            # Annotation text with context
            annotation_text = f"{level.type} {level.volume:,}"
            if level.buy_sell_ratio:
                annotation_text += f"\nB/S: {level.buy_sell_ratio:.2f}"
            
            fig.add_hline(
                y=level.price,
                line_color=color,
                line_width=line_width,
                line_dash=line_style,
                annotation_text=annotation_text,
                annotation_position="right",
                annotation=dict(
                    bgcolor=color,
                    bordercolor=color,
                    font=dict(color='white', size=9, family='Arial'),
                ),
            )
        
        return fig
    
    def _add_gamma_intelligence(self, fig: go.Figure, intelligence: MOATIntelligence) -> go.Figure:
        """Add gamma flip and max pain levels"""
        if intelligence.gamma_flip:
            fig.add_hline(
                y=intelligence.gamma_flip,
                line_color='#a855f7',
                line_width=2,
                line_dash='dot',
                annotation_text=f"Gamma Flip\n{intelligence.gamma_regime}",
                annotation_position="right",
            )
        
        if intelligence.max_pain:
            fig.add_hline(
                y=intelligence.max_pain,
                line_color='#ff8c00',
                line_width=1,
                line_dash='dash',
                annotation_text='Max Pain',
                annotation_position="right",
            )
        
        return fig
    
    def _add_options_flow(self, fig: go.Figure, intelligence: MOATIntelligence) -> go.Figure:
        """Add options flow zones (call/put accumulation)"""
        for zone in intelligence.options_flow_zones:
            # Add background shading for accumulation zones
            if zone.call_volume > zone.put_volume * 1.5:
                # Call accumulation (bullish)
                fig.add_shape(
                    type='rect',
                    x0=0, x1=1,
                    y0=zone.price_min, y1=zone.price_max,
                    fillcolor='rgba(0, 255, 136, 0.1)',
                    layer='below',
                    line=dict(width=0),
                )
            elif zone.put_volume > zone.call_volume * 1.5:
                # Put accumulation (bearish)
                fig.add_shape(
                    type='rect',
                    x0=0, x1=1,
                    y0=zone.price_min, y1=zone.price_max,
                    fillcolor='rgba(255, 51, 102, 0.1)',
                    layer='below',
                    line=dict(width=0),
                )
        
        return fig
    
    def _add_squeeze_intelligence(self, fig: go.Figure, intelligence: MOATIntelligence) -> go.Figure:
        """Add squeeze zones and markers"""
        for zone in intelligence.squeeze_zones:
            # Add squeeze zone background
            fig.add_shape(
                type='rect',
                x0=0, x1=1,
                y0=zone.price_min, y1=zone.price_max,
                fillcolor='rgba(255, 107, 107, 0.15)',
                layer='below',
                line=dict(width=0),
            )
        
        return fig
    
    def _add_signal_markers(self, fig: go.Figure, intelligence: MOATIntelligence) -> go.Figure:
        """Add signal markers with full context"""
        for signal in intelligence.signals:
            # Determine marker color and symbol
            if signal.action == 'BUY':
                color = '#00ff88'
                symbol = 'triangle-up'
            else:
                color = '#ff3366'
                symbol = 'triangle-down'
            
            # Marker size based on confidence
            size = 15 if signal.confidence >= 0.75 else 12 if signal.confidence >= 0.50 else 8
            
            # Add marker
            fig.add_trace(go.Scatter(
                x=[signal.timestamp],
                y=[signal.price],
                mode='markers',
                marker=dict(
                    symbol=symbol,
                    size=size,
                    color=color,
                    line=dict(width=2, color='white'),
                ),
                name=f"{signal.signal_type} {signal.action}",
                text=f"{signal.signal_type}<br>Conf: {signal.confidence:.0%}<br>R/R: {signal.risk_reward:.1f}" if signal.risk_reward else f"{signal.signal_type}<br>Conf: {signal.confidence:.0%}",
                hovertemplate='<b>%{text}</b><br>' +
                            f'Entry: ${signal.entry_price:.2f}<br>' +
                            (f'Target: ${signal.target_price:.2f}<br>' if signal.target_price else '') +
                            (f'Stop: ${signal.stop_price:.2f}<br>' if signal.stop_price else '') +
                            f'<extra></extra>',
            ))
        
        return fig
    
    def _add_institutional_context(self, fig: go.Figure, intelligence: MOATIntelligence) -> go.Figure:
        """Add institutional context gauges (right side annotations)"""
        # Add text annotations for context scores
        fig.add_annotation(
            x=1.02, y=0.95,
            xref='paper', yref='paper',
            text=f"<b>Institutional Context</b><br>" +
                 f"Buying: {intelligence.buying_pressure:.0%}<br>" +
                 f"Squeeze: {intelligence.squeeze_potential:.0%}<br>" +
                 f"Gamma: {intelligence.gamma_pressure:.0%}<br>" +
                 f"Composite: {intelligence.composite_score:.0%}",
            showarrow=False,
            align='left',
            bgcolor='rgba(10, 10, 15, 0.9)',
            bordercolor='#2a2a35',
            borderwidth=1,
            font=dict(color='#a0a0b0', size=10),
        )
        
        return fig
    
    def _add_regime_indicator(self, fig: go.Figure, intelligence: MOATIntelligence) -> go.Figure:
        """Add regime indicator (top banner)"""
        regime_text = f"REGIME: {intelligence.regime} | Time: {intelligence.time_of_day}"
        if intelligence.vix_level:
            regime_text += f" | VIX: {intelligence.vix_level:.1f}"
        
        fig.add_annotation(
            x=0.5, y=1.05,
            xref='paper', yref='paper',
            text=f"<b>{regime_text}</b>",
            showarrow=False,
            align='center',
            bgcolor='rgba(42, 42, 53, 0.8)',
            font=dict(color='#a0a0b0', size=11),
        )
        
        return fig
    
    def _add_volume_profile(self, fig: go.Figure, intelligence: MOATIntelligence, df: pd.DataFrame) -> go.Figure:
        """Add volume profile panel (if data available)"""
        # Volume is already added in base chart
        # This could add additional volume profile visualization
        return fig
    
    def _add_news_events(self, fig: go.Figure, intelligence: MOATIntelligence) -> go.Figure:
        """Add news/event markers"""
        # TODO: Add vertical lines for economic events
        return fig
    
    def _add_historical_learning(self, fig: go.Figure, intelligence: MOATIntelligence) -> go.Figure:
        """Add historical learning annotations (bounce rates)"""
        # Add bounce rate annotations to DP levels
        for level in intelligence.dp_levels:
            if level.price in intelligence.dp_bounce_rates:
                bounce_rate = intelligence.dp_bounce_rates[level.price]
                # Add annotation with bounce rate
                fig.add_annotation(
                    x=0.02, y=level.price,
                    xref='paper', yref='y',
                    text=f"{bounce_rate:.0%} bounce rate",
                    showarrow=False,
                    align='left',
                    bgcolor='rgba(255, 215, 0, 0.2)',
                    font=dict(size=8, color='#ffd700'),
                )
        
        return fig
    
    def _add_sentiment(self, fig: go.Figure, intelligence: MOATIntelligence) -> go.Figure:
        """Add Reddit sentiment indicator"""
        sentiment_color = {
            'BULLISH': '#00ff88',
            'BEARISH': '#ff3366',
            'NEUTRAL': '#a0a0b0',
        }.get(intelligence.reddit_sentiment, '#a0a0b0')
        
        fig.add_annotation(
            x=0.98, y=0.05,
            xref='paper', yref='paper',
            text=f"<b>Reddit</b><br>{intelligence.reddit_sentiment}<br>{intelligence.reddit_mentions} mentions",
            showarrow=False,
            align='right',
            bgcolor=f'rgba{tuple(int(sentiment_color[i:i+2], 16) for i in (1, 3, 5)) + (0.2,)}',
            font=dict(color=sentiment_color, size=9),
        )
        
        return fig
    
    def _apply_moat_styling(self, fig: go.Figure, intelligence: MOATIntelligence) -> go.Figure:
        """Apply professional MOAT styling"""
        # Add VWAP if available
        if intelligence.vwap:
            fig.add_hline(
                y=intelligence.vwap,
                line_color='#00d4ff',
                line_width=1,
                line_dash='dash',
                annotation_text='VWAP',
            )
        
        # Add current price
        if intelligence.current_price:
            fig.add_hline(
                y=intelligence.current_price,
                line_color='white',
                line_width=1,
                line_dash='solid',
                annotation_text='Current',
            )
        
        # Professional dark theme
        fig.update_layout(
            title=f"{intelligence.ticker if hasattr(intelligence, 'ticker') else 'Ticker'} - MOAT Intelligence Chart",
            template='plotly_dark',
            plot_bgcolor='#0a0a0f',
            paper_bgcolor='#0a0a0f',
            font=dict(color='#a0a0b0', family='Arial', size=12),
            xaxis=dict(
                gridcolor='#2a2a35',
                showgrid=True,
                title='Date',
            ),
            yaxis=dict(
                gridcolor='#2a2a35',
                showgrid=True,
                title='Price ($)',
            ),
            yaxis2=dict(
                title='Volume',
                overlaying='y',
                side='right',
                showgrid=False,
            ),
            height=700,
            xaxis_rangeslider_visible=False,
            hovermode='x unified',
            legend=dict(
                orientation='h',
                yanchor='bottom',
                y=1.02,
                xanchor='right',
                x=1,
            ),
        )
        
        return fig
    
    def _get_dp_color(self, level: DPLevel) -> str:
        """Get color for DP level based on type and strength"""
        if level.type == 'SUPPORT':
            return {
                'STRONG': '#00ff88',
                'MODERATE': '#66ffaa',
                'WEAK': '#99ffcc'
            }.get(level.strength, '#00ff88')
        elif level.type == 'RESISTANCE':
            return {
                'STRONG': '#ff3366',
                'MODERATE': '#ff6699',
                'WEAK': '#ff99bb'
            }.get(level.strength, '#ff3366')
        else:  # BATTLEGROUND
            return '#ffd700'
    
    def _get_line_width(self, strength: str) -> int:
        """Get line width based on strength"""
        return {
            'STRONG': 3,
            'MODERATE': 2,
            'WEAK': 1
        }.get(strength, 2)


# Convenience function for Streamlit
def create_moat_chart(
    ticker: str,
    candlestick_data: pd.DataFrame,
    api_key: Optional[str] = None,
    signals: Optional[List[Union[LiveSignal, LotterySignal]]] = None,
) -> go.Figure:
    """
    Convenience function to create MOAT chart.
    
    Usage in Streamlit:
        fig = create_moat_chart('SPY', df, api_key=api_key, signals=signals)
        st.plotly_chart(fig, use_container_width=True)
    """
    engine = MOATChartEngine(api_key=api_key)
    return engine.create_moat_chart(ticker, candlestick_data, signals=signals)

