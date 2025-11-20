#!/usr/bin/env python3
"""
LIVE HIGH-RESOLUTION BREAKOUT DETECTOR
- 1-5 minute resolution with real timestamps
- Live signal firing in real-time
- Detailed regime detection logic
- Robust failover mechanisms
"""

import asyncio
import logging
import time
import random
import numpy as np
import matplotlib.pyplot as plt
import pandas as pd
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass
import json
import requests
from bs4 import BeautifulSoup
import yfinance as yf

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

logger = logging.getLogger(__name__)

@dataclass
class LiveSignal:
    """Live signal with timestamp"""
    timestamp: datetime
    ticker: str
    signal_type: str
    price: float
    volume: int
    confidence: float
    regime: str
    reasoning: str
    data_source: str
    resistance_level: Optional[float] = None
    support_level: Optional[float] = None
    breakout_strength: Optional[float] = None
    reversal_strength: Optional[float] = None
    volume_spike: bool = False
    options_flow: bool = False

@dataclass
class RegimeAnalysis:
    """Regime analysis with detailed logic"""
    timestamp: datetime
    ticker: str
    regime: str
    confidence: float
    trend_strength: float
    volatility_regime: str
    volume_regime: str
    price_momentum: float
    support_resistance_ratio: float
    reasoning: str
    data_points_used: int

class MultiSourceDataProvider:
    """Multi-source data provider with failover"""
    
    def __init__(self):
        self.sources = ['yahoo_direct', 'yfinance', 'rapidapi']
        self.current_source = 0
        self.source_errors = {source: 0 for source in self.sources}
        self.max_errors_per_source = 3
        
        # Rate limiting per source
        self.last_request_time = {source: 0 for source in self.sources}
        self.request_delays = {
            'yahoo_direct': 1.0,
            'yfinance': 0.5,
            'rapidapi': 2.0
        }
        
        self.user_agents = [
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
            'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36',
            'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36'
        ]
    
    def _enforce_rate_limit(self, source: str):
        """Enforce rate limiting per source"""
        current_time = time.time()
        time_since_last = current_time - self.last_request_time[source]
        
        if time_since_last < self.request_delays[source]:
            wait_time = self.request_delays[source] - time_since_last
            logger.info(f"Rate limiting {source}: waiting {wait_time:.2f}s")
            time.sleep(wait_time)
        
        self.last_request_time[source] = time.time()
    
    def get_market_data_with_failover(self, ticker: str) -> Dict[str, Any]:
        """Get market data with automatic failover"""
        
        # Try each source in order
        for attempt in range(len(self.sources)):
            source = self.sources[self.current_source]
            
            try:
                self._enforce_rate_limit(source)
                
                if source == 'yahoo_direct':
                    data = self._get_yahoo_direct_data(ticker)
                elif source == 'yfinance':
                    data = self._get_yfinance_data(ticker)
                elif source == 'rapidapi':
                    data = self._get_rapidapi_data(ticker)
                
                if data and data.get('price', 0) > 0:
                    logger.info(f"✅ Data from {source}: {ticker} = ${data['price']:.2f}")
                    return data
                else:
                    raise Exception(f"No valid data from {source}")
                    
            except Exception as e:
                logger.warning(f"❌ {source} failed for {ticker}: {e}")
                self.source_errors[source] += 1
                
                # Switch to next source
                self.current_source = (self.current_source + 1) % len(self.sources)
                
                # If all sources have too many errors, reset
                if all(errors >= self.max_errors_per_source for errors in self.source_errors.values()):
                    logger.warning("🔄 Resetting all source error counts")
                    self.source_errors = {source: 0 for source in self.sources}
        
        logger.error(f"❌ All sources failed for {ticker}")
        return {}
    
    def _get_yahoo_direct_data(self, ticker: str) -> Dict[str, Any]:
        """Get data from Yahoo Direct"""
        try:
            user_agent = random.choice(self.user_agents)
            url = f"https://finance.yahoo.com/quote/{ticker}"
            headers = {
                'User-Agent': user_agent,
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
                'Accept-Language': 'en-US,en;q=0.5',
                'Connection': 'keep-alive',
            }
            
            response = requests.get(url, headers=headers, timeout=10)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.content, 'html.parser')
            
            # Extract price
            price = self._extract_price_from_html(soup)
            volume = self._extract_volume_from_html(soup)
            change = self._extract_change_from_html(soup)
            
            if price > 0:
                return {
                    'ticker': ticker,
                    'price': price,
                    'volume': volume,
                    'change': change,
                    'change_percent': (change / price * 100) if price != 0 else 0,
                    'source': 'yahoo_direct',
                    'timestamp': datetime.now().isoformat()
                }
            
            return {}
            
        except Exception as e:
            raise Exception(f"Yahoo Direct error: {e}")
    
    def _get_yfinance_data(self, ticker: str) -> Dict[str, Any]:
        """Get data from yfinance"""
        try:
            stock = yf.Ticker(ticker)
            hist = stock.history(period="1d", interval="1m")
            
            if not hist.empty:
                latest = hist.iloc[-1]
                return {
                    'ticker': ticker,
                    'price': float(latest['Close']),
                    'volume': int(latest['Volume']),
                    'change': float(latest['Close'] - hist.iloc[-2]['Close']) if len(hist) > 1 else 0.0,
                    'change_percent': float((latest['Close'] - hist.iloc[-2]['Close']) / hist.iloc[-2]['Close'] * 100) if len(hist) > 1 and hist.iloc[-2]['Close'] != 0 else 0.0,
                    'source': 'yfinance',
                    'timestamp': datetime.now().isoformat()
                }
            
            return {}
            
        except Exception as e:
            raise Exception(f"yfinance error: {e}")
    
    def _get_rapidapi_data(self, ticker: str) -> Dict[str, Any]:
        """Get data from RapidAPI (if available)"""
        try:
            # This would be your RapidAPI implementation
            # For now, return empty to trigger failover
            raise Exception("RapidAPI not implemented")
            
        except Exception as e:
            raise Exception(f"RapidAPI error: {e}")
    
    def _extract_price_from_html(self, soup: BeautifulSoup) -> float:
        """Extract price from HTML"""
        try:
            price_selectors = [
                'span[data-field="regularMarketPrice"]',
                'span[data-symbol="price"]',
                '[data-testid="qsp-price"]',
                'fin-streamer[data-field="regularMarketPrice"]'
            ]
            
            for selector in price_selectors:
                element = soup.select_one(selector)
                if element:
                    price_text = element.get_text().strip()
                    import re
                    price_match = re.search(r'[\d,]+\.?\d*', price_text.replace(',', ''))
                    if price_match:
                        return float(price_match.group())
            
            return 0.0
            
        except Exception as e:
            logger.error(f"Error extracting price: {e}")
            return 0.0
    
    def _extract_volume_from_html(self, soup: BeautifulSoup) -> int:
        """Extract volume from HTML"""
        try:
            volume_selectors = [
                'span[data-field="regularMarketVolume"]',
                'span[data-symbol="volume"]',
                'fin-streamer[data-field="regularMarketVolume"]'
            ]
            
            for selector in volume_selectors:
                element = soup.select_one(selector)
                if element:
                    volume_text = element.get_text().strip()
                    import re
                    volume_match = re.search(r'[\d,]+', volume_text.replace(',', ''))
                    if volume_match:
                        return int(volume_match.group())
            
            return 0
            
        except Exception as e:
            logger.error(f"Error extracting volume: {e}")
            return 0
    
    def _extract_change_from_html(self, soup: BeautifulSoup) -> float:
        """Extract change from HTML"""
        try:
            change_selectors = [
                'span[data-field="regularMarketChange"]',
                'span[data-symbol="change"]',
                'fin-streamer[data-field="regularMarketChange"]'
            ]
            
            for selector in change_selectors:
                element = soup.select_one(selector)
                if element:
                    change_text = element.get_text().strip()
                    import re
                    change_match = re.search(r'[+-]?[\d,]+\.?\d*', change_text.replace(',', ''))
                    if change_match:
                        return float(change_match.group())
            
            return 0.0
            
        except Exception as e:
            logger.error(f"Error extracting change: {e}")
            return 0.0

class LiveHighResolutionDetector:
    """Live high-resolution breakout detector"""
    
    def __init__(self):
        self.data_provider = MultiSourceDataProvider()
        
        # Live tracking
        self.price_history = {}
        self.signal_history = []
        self.regime_history = []
        
        # Detection thresholds
        self.breakout_threshold = 0.015  # 1.5% above resistance
        self.reversal_threshold = 0.015  # 1.5% below support
        self.volume_spike_threshold = 1.8  # 1.8x average volume
        self.min_data_points = 10  # Minimum data points for analysis
        
    async def run_live_detection(self, tickers: List[str], duration_minutes: int = 30, resolution_seconds: int = 60) -> Dict[str, Any]:
        """Run live detection with high resolution"""
        try:
            logger.info(f"🚀 LIVE HIGH-RESOLUTION DETECTION - {duration_minutes} minutes, {resolution_seconds}s resolution")
            
            results = {
                'live_signals': [],
                'regime_analysis': [],
                'data_sources_used': [],
                'failover_events': [],
                'timestamped_log': []
            }
            
            # Initialize tracking
            for ticker in tickers:
                self.price_history[ticker] = []
            
            # Run detection loop
            start_time = datetime.now()
            end_time = start_time + timedelta(minutes=duration_minutes)
            
            cycle_count = 0
            
            while datetime.now() < end_time:
                cycle_start = datetime.now()
                cycle_count += 1
                
                logger.info(f"🔍 LIVE CYCLE {cycle_count} - {cycle_start.strftime('%H:%M:%S')}")
                
                for ticker in tickers:
                    # Get live data with failover
                    market_data = self.data_provider.get_market_data_with_failover(ticker)
                    
                    if market_data:
                        # Track data source
                        results['data_sources_used'].append({
                            'timestamp': cycle_start.isoformat(),
                            'ticker': ticker,
                            'source': market_data['source'],
                            'price': market_data['price']
                        })
                        
                        # Update price history
                        self.price_history[ticker].append({
                            'timestamp': cycle_start,
                            'price': market_data['price'],
                            'volume': market_data['volume'],
                            'change': market_data['change'],
                            'source': market_data['source']
                        })
                        
                        # Keep only last 100 points
                        if len(self.price_history[ticker]) > 100:
                            self.price_history[ticker] = self.price_history[ticker][-100:]
                        
                        # Analyze regime
                        regime_analysis = self._analyze_regime(ticker, cycle_start)
                        if regime_analysis:
                            self.regime_history.append(regime_analysis)
                            results['regime_analysis'].append(regime_analysis)
                        
                        # Detect signals
                        signals = self._detect_live_signals(ticker, market_data, cycle_start)
                        for signal in signals:
                            self.signal_history.append(signal)
                            results['live_signals'].append(signal)
                            
                            logger.info(f"🚨 LIVE SIGNAL: {signal.ticker} {signal.signal_type} @ ${signal.price:.2f} - {signal.reasoning}")
                
                # Log timestamped activity
                results['timestamped_log'].append({
                    'timestamp': cycle_start.isoformat(),
                    'cycle': cycle_count,
                    'tickers_processed': len(tickers),
                    'signals_detected': len([s for s in self.signal_history if s.timestamp >= cycle_start - timedelta(seconds=resolution_seconds)]),
                    'data_sources_active': len(set([d['source'] for d in results['data_sources_used'][-len(tickers):]]))
                })
                
                # Wait for next cycle
                cycle_duration = (datetime.now() - cycle_start).total_seconds()
                sleep_time = max(0, resolution_seconds - cycle_duration)
                
                if sleep_time > 0:
                    await asyncio.sleep(sleep_time)
            
            # Generate final analysis
            results['final_analysis'] = self._generate_final_analysis(results)
            
            # Display results
            self._display_live_results(results)
            
            return results
            
        except Exception as e:
            logger.error(f"Error in live detection: {e}")
            return {'error': str(e)}
    
    def _analyze_regime(self, ticker: str, timestamp: datetime) -> Optional[RegimeAnalysis]:
        """Analyze market regime with detailed logic"""
        try:
            if len(self.price_history[ticker]) < self.min_data_points:
                return None
            
            price_data = [p['price'] for p in self.price_history[ticker]]
            volume_data = [p['volume'] for p in self.price_history[ticker]]
            
            # Calculate trend strength
            if len(price_data) >= 5:
                recent_prices = price_data[-5:]
                trend_slope = np.polyfit(range(len(recent_prices)), recent_prices, 1)[0]
                trend_strength = abs(trend_slope) / np.mean(recent_prices)
            else:
                trend_strength = 0.0
            
            # Calculate volatility
            if len(price_data) >= 10:
                returns = np.diff(price_data[-10:]) / price_data[-10:-1]
                volatility = np.std(returns)
            else:
                volatility = 0.0
            
            # Calculate volume regime
            if len(volume_data) >= 5:
                avg_volume = np.mean(volume_data[-5:])
                recent_volume = volume_data[-1]
                volume_ratio = recent_volume / avg_volume if avg_volume > 0 else 1.0
            else:
                volume_ratio = 1.0
            
            # Calculate price momentum
            if len(price_data) >= 3:
                price_momentum = (price_data[-1] - price_data[-3]) / price_data[-3]
            else:
                price_momentum = 0.0
            
            # Calculate support/resistance ratio
            if len(price_data) >= 10:
                resistance_levels = self._calculate_resistance_levels(price_data)
                support_levels = self._calculate_support_levels(price_data)
                current_price = price_data[-1]
                
                if resistance_levels and support_levels:
                    resistance_distance = min([abs(r - current_price) for r in resistance_levels])
                    support_distance = min([abs(s - current_price) for s in support_levels])
                    sr_ratio = resistance_distance / support_distance if support_distance > 0 else 1.0
                else:
                    sr_ratio = 1.0
            else:
                sr_ratio = 1.0
            
            # Determine regime
            regime = "CHOP"
            confidence = 0.5
            
            if trend_strength > 0.002:  # Strong trend
                if price_momentum > 0.01:
                    regime = "UPTREND"
                    confidence = min(0.9, 0.5 + trend_strength * 100)
                elif price_momentum < -0.01:
                    regime = "DOWNTREND"
                    confidence = min(0.9, 0.5 + trend_strength * 100)
            elif volatility > 0.02:  # High volatility
                regime = "HIGH_VOLATILITY"
                confidence = min(0.8, 0.5 + volatility * 10)
            
            # Determine volatility regime
            if volatility > 0.03:
                volatility_regime = "HIGH"
            elif volatility > 0.015:
                volatility_regime = "MEDIUM"
            else:
                volatility_regime = "LOW"
            
            # Determine volume regime
            if volume_ratio > 2.0:
                volume_regime = "HIGH"
            elif volume_ratio > 1.5:
                volume_regime = "MEDIUM"
            else:
                volume_regime = "LOW"
            
            reasoning = f"Trend: {trend_strength:.4f}, Vol: {volatility:.4f}, VolRatio: {volume_ratio:.2f}, Momentum: {price_momentum:.4f}, SR: {sr_ratio:.2f}"
            
            return RegimeAnalysis(
                timestamp=timestamp,
                ticker=ticker,
                regime=regime,
                confidence=confidence,
                trend_strength=trend_strength,
                volatility_regime=volatility_regime,
                volume_regime=volume_regime,
                price_momentum=price_momentum,
                support_resistance_ratio=sr_ratio,
                reasoning=reasoning,
                data_points_used=len(price_data)
            )
            
        except Exception as e:
            logger.error(f"Error analyzing regime for {ticker}: {e}")
            return None
    
    def _detect_live_signals(self, ticker: str, market_data: Dict[str, Any], timestamp: datetime) -> List[LiveSignal]:
        """Detect live signals with real-time analysis"""
        try:
            signals = []
            
            if len(self.price_history[ticker]) < self.min_data_points:
                return signals
            
            current_price = market_data['price']
            current_volume = market_data['volume']
            
            # Get current regime
            current_regime = "CHOP"
            if self.regime_history:
                latest_regime = max([r for r in self.regime_history if r.ticker == ticker], 
                                  key=lambda x: x.timestamp, default=None)
                if latest_regime:
                    current_regime = latest_regime.regime
            
            # Detect breakouts
            breakout_signal = self._detect_breakout_signal(ticker, current_price, current_volume, current_regime, timestamp)
            if breakout_signal:
                signals.append(breakout_signal)
            
            # Detect reversals
            reversal_signal = self._detect_reversal_signal(ticker, current_price, current_volume, current_regime, timestamp)
            if reversal_signal:
                signals.append(reversal_signal)
            
            return signals
            
        except Exception as e:
            logger.error(f"Error detecting live signals for {ticker}: {e}")
            return []
    
    def _detect_breakout_signal(self, ticker: str, current_price: float, current_volume: int, regime: str, timestamp: datetime) -> Optional[LiveSignal]:
        """Detect breakout signal"""
        try:
            price_data = [p['price'] for p in self.price_history[ticker]]
            resistance_levels = self._calculate_resistance_levels(price_data)
            
            for resistance_level in resistance_levels:
                if current_price > resistance_level * (1 + self.breakout_threshold):
                    # Check volume spike
                    volume_data = [p['volume'] for p in self.price_history[ticker][-10:]]
                    avg_volume = np.mean(volume_data) if volume_data else current_volume
                    volume_spike = current_volume > avg_volume * self.volume_spike_threshold
                    
                    # Calculate confidence based on regime
                    confidence = 0.6  # Base confidence
                    if regime == "UPTREND":
                        confidence += 0.2
                    elif regime == "DOWNTREND":
                        confidence -= 0.1
                    
                    if volume_spike:
                        confidence += 0.1
                    
                    confidence = max(0.3, min(0.9, confidence))
                    
                    if confidence > 0.5:  # Only signal if confident
                        breakout_strength = (current_price - resistance_level) / resistance_level
                        
                        return LiveSignal(
                            timestamp=timestamp,
                            ticker=ticker,
                            signal_type="BREAKOUT",
                            price=current_price,
                            volume=current_volume,
                            confidence=confidence,
                            regime=regime,
                            reasoning=f"Breakout above ${resistance_level:.2f} resistance, strength: {breakout_strength:.2%}, vol spike: {volume_spike}",
                            data_source=self.price_history[ticker][-1]['source'],
                            resistance_level=resistance_level,
                            breakout_strength=breakout_strength,
                            volume_spike=volume_spike
                        )
            
            return None
            
        except Exception as e:
            logger.error(f"Error detecting breakout for {ticker}: {e}")
            return None
    
    def _detect_reversal_signal(self, ticker: str, current_price: float, current_volume: int, regime: str, timestamp: datetime) -> Optional[LiveSignal]:
        """Detect reversal signal"""
        try:
            price_data = [p['price'] for p in self.price_history[ticker]]
            support_levels = self._calculate_support_levels(price_data)
            
            for support_level in support_levels:
                if current_price < support_level * (1 - self.reversal_threshold):
                    # Check volume spike
                    volume_data = [p['volume'] for p in self.price_history[ticker][-10:]]
                    avg_volume = np.mean(volume_data) if volume_data else current_volume
                    volume_spike = current_volume > avg_volume * self.volume_spike_threshold
                    
                    # Calculate confidence based on regime
                    confidence = 0.6  # Base confidence
                    if regime == "DOWNTREND":
                        confidence += 0.2
                    elif regime == "UPTREND":
                        confidence -= 0.1
                    
                    if volume_spike:
                        confidence += 0.1
                    
                    confidence = max(0.3, min(0.9, confidence))
                    
                    if confidence > 0.5:  # Only signal if confident
                        reversal_strength = (support_level - current_price) / support_level
                        
                        return LiveSignal(
                            timestamp=timestamp,
                            ticker=ticker,
                            signal_type="REVERSAL",
                            price=current_price,
                            volume=current_volume,
                            confidence=confidence,
                            regime=regime,
                            reasoning=f"Reversal off ${support_level:.2f} support, strength: {reversal_strength:.2%}, vol spike: {volume_spike}",
                            data_source=self.price_history[ticker][-1]['source'],
                            support_level=support_level,
                            reversal_strength=reversal_strength,
                            volume_spike=volume_spike
                        )
            
            return None
            
        except Exception as e:
            logger.error(f"Error detecting reversal for {ticker}: {e}")
            return None
    
    def _calculate_resistance_levels(self, price_history: List[float]) -> List[float]:
        """Calculate resistance levels"""
        try:
            if len(price_history) < 10:
                return []
            
            # Find local maxima
            resistance_levels = []
            for i in range(2, len(price_history) - 2):
                if (price_history[i] > price_history[i-1] and 
                    price_history[i] > price_history[i+1] and
                    price_history[i] > price_history[i-2] and
                    price_history[i] > price_history[i+2]):
                    resistance_levels.append(price_history[i])
            
            return sorted(resistance_levels, reverse=True)[:3]
            
        except Exception as e:
            logger.error(f"Error calculating resistance levels: {e}")
            return []
    
    def _calculate_support_levels(self, price_history: List[float]) -> List[float]:
        """Calculate support levels"""
        try:
            if len(price_history) < 10:
                return []
            
            # Find local minima
            support_levels = []
            for i in range(2, len(price_history) - 2):
                if (price_history[i] < price_history[i-1] and 
                    price_history[i] < price_history[i+1] and
                    price_history[i] < price_history[i-2] and
                    price_history[i] < price_history[i+2]):
                    support_levels.append(price_history[i])
            
            return sorted(support_levels)[:3]
            
        except Exception as e:
            logger.error(f"Error calculating support levels: {e}")
            return []
    
    def _generate_final_analysis(self, results: Dict[str, Any]) -> Dict[str, Any]:
        """Generate final analysis with timestamps"""
        try:
            signals = results.get('live_signals', [])
            regimes = results.get('regime_analysis', [])
            data_sources = results.get('data_sources_used', [])
            
            # Analyze signal timing
            signal_timing = {}
            for signal in signals:
                hour = signal.timestamp.hour
                if hour not in signal_timing:
                    signal_timing[hour] = []
                signal_timing[hour].append(signal)
            
            # Analyze regime changes
            regime_changes = {}
            for regime in regimes:
                ticker = regime.ticker
                if ticker not in regime_changes:
                    regime_changes[ticker] = []
                regime_changes[ticker].append(regime)
            
            # Analyze data source reliability
            source_reliability = {}
            for data_point in data_sources:
                source = data_point['source']
                if source not in source_reliability:
                    source_reliability[source] = {'count': 0, 'success_rate': 0}
                source_reliability[source]['count'] += 1
            
            return {
                'total_signals': len(signals),
                'signals_by_type': {
                    'breakouts': len([s for s in signals if s.signal_type == 'BREAKOUT']),
                    'reversals': len([s for s in signals if s.signal_type == 'REVERSAL'])
                },
                'signals_by_ticker': {
                    ticker: len([s for s in signals if s.ticker == ticker])
                    for ticker in set([s.ticker for s in signals])
                },
                'signal_timing': signal_timing,
                'regime_changes': regime_changes,
                'data_source_reliability': source_reliability,
                'average_confidence': np.mean([s.confidence for s in signals]) if signals else 0,
                'regime_distribution': {
                    regime: len([r for r in regimes if r.regime == regime])
                    for regime in set([r.regime for r in regimes])
                }
            }
            
        except Exception as e:
            logger.error(f"Error generating final analysis: {e}")
            return {}
    
    def _display_live_results(self, results: Dict[str, Any]):
        """Display live results with timestamps"""
        try:
            print(f"\n{'='*120}")
            print(f"🎯 LIVE HIGH-RESOLUTION DETECTION RESULTS")
            print(f"{'='*120}")
            
            # Live Signals
            signals = results.get('live_signals', [])
            print(f"\n🚨 LIVE SIGNALS DETECTED ({len(signals)} total):")
            for signal in signals:
                print(f"\n   {signal.timestamp.strftime('%H:%M:%S')} - {signal.ticker} {signal.signal_type}:")
                print(f"      Price: ${signal.price:.2f}")
                print(f"      Volume: {signal.volume:,}")
                print(f"      Confidence: {signal.confidence:.2f}")
                print(f"      Regime: {signal.regime}")
                print(f"      Data Source: {signal.data_source}")
                print(f"      Reasoning: {signal.reasoning}")
                if signal.resistance_level:
                    print(f"      Resistance Level: ${signal.resistance_level:.2f}")
                if signal.support_level:
                    print(f"      Support Level: ${signal.support_level:.2f}")
            
            # Regime Analysis
            regimes = results.get('regime_analysis', [])
            print(f"\n📊 REGIME ANALYSIS ({len(regimes)} analyses):")
            for regime in regimes[-10:]:  # Show last 10
                print(f"\n   {regime.timestamp.strftime('%H:%M:%S')} - {regime.ticker}:")
                print(f"      Regime: {regime.regime} (confidence: {regime.confidence:.2f})")
                print(f"      Trend Strength: {regime.trend_strength:.4f}")
                print(f"      Volatility: {regime.volatility_regime}")
                print(f"      Volume: {regime.volume_regime}")
                print(f"      Price Momentum: {regime.price_momentum:.4f}")
                print(f"      Data Points: {regime.data_points_used}")
                print(f"      Reasoning: {regime.reasoning}")
            
            # Data Source Analysis
            data_sources = results.get('data_sources_used', [])
            print(f"\n📡 DATA SOURCE ANALYSIS:")
            source_counts = {}
            for data_point in data_sources:
                source = data_point['source']
                source_counts[source] = source_counts.get(source, 0) + 1
            
            for source, count in source_counts.items():
                print(f"   {source}: {count} successful retrievals")
            
            # Timestamped Log
            timestamped_log = results.get('timestamped_log', [])
            print(f"\n⏰ TIMESTAMPED ACTIVITY LOG:")
            for log_entry in timestamped_log[-10:]:  # Show last 10
                print(f"   {log_entry['timestamp']} - Cycle {log_entry['cycle']}: "
                      f"{log_entry['tickers_processed']} tickers, "
                      f"{log_entry['signals_detected']} signals, "
                      f"{log_entry['data_sources_active']} sources active")
            
            # Final Analysis
            final_analysis = results.get('final_analysis', {})
            print(f"\n📈 FINAL ANALYSIS:")
            print(f"   Total Signals: {final_analysis.get('total_signals', 0)}")
            print(f"   Breakouts: {final_analysis.get('signals_by_type', {}).get('breakouts', 0)}")
            print(f"   Reversals: {final_analysis.get('signals_by_type', {}).get('reversals', 0)}")
            print(f"   Average Confidence: {final_analysis.get('average_confidence', 0):.2f}")
            
            print(f"\n✅ LIVE HIGH-RESOLUTION DETECTION COMPLETE!")
            print(f"🎯 REAL-TIME SIGNALS WITH TIMESTAMPS!")
            
        except Exception as e:
            logger.error(f"Error displaying live results: {e}")

async def main():
    """Main function"""
    print("🔥 LIVE HIGH-RESOLUTION BREAKOUT DETECTOR")
    print("=" * 80)
    
    detector = LiveHighResolutionDetector()
    
    # Focus on major movers
    tickers = ['SPY', 'QQQ', 'TSLA', 'AAPL', 'NVDA']
    
    try:
        # Run for 10 minutes with 60-second resolution
        results = await detector.run_live_detection(tickers, duration_minutes=10, resolution_seconds=60)
        
        if results.get('error'):
            print(f"\n❌ ERROR: {results['error']}")
            return
        
        print(f"\n🎯 LIVE HIGH-RESOLUTION DETECTION COMPLETE!")
        print(f"🚀 REAL-TIME SIGNALS WITH TIMESTAMPS!")
        
    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(main())

