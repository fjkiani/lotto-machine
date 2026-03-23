#!/usr/bin/env python3
"""
📊 OPTIONS FLOW CHECKER - RapidAPI Integration

Monitors options flow for institutional positioning signals.
Uses Yahoo Finance 15 RapidAPI (VALIDATED & WORKING).

SIGNALS GENERATED:
1. BULLISH_CALL_ACCUMULATION - P/C ratio < 0.7, high volume
2. BEARISH_PUT_ACCUMULATION - P/C ratio > 1.2, high volume  
3. UNUSUAL_OPTIONS_ACTIVITY - Vol/OI > 30x on specific contract
4. MARKET_SENTIMENT_SHIFT - Overall market bias change

DATA SOURCES:
- Most Active Options (500+ stocks)
- Unusual Options Activity (1,859+ trades)
- Full Options Chains

STORAGE: SQLite for historical tracking and pattern learning
"""

import os
import sys
import logging
from datetime import datetime, timedelta
from typing import List, Optional, Dict
import sqlite3
import json

# Add paths
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))))

from live_monitoring.orchestrator.checkers.base_checker import BaseChecker, CheckerAlert
from core.data.rapidapi_options_client import RapidAPIOptionsClient, MostActiveOption, UnusualOption

logger = logging.getLogger(__name__)


class OptionsFlowStorage:
    """
    SQLite storage for options flow data.
    
    Tracks:
    - Market sentiment over time
    - Unusual activity alerts
    - Signal performance
    """
    
    def __init__(self, db_path: str = "data/options_flow.db"):
        self.db_path = db_path
        os.makedirs(os.path.dirname(db_path), exist_ok=True)
        self._init_db()
    
    def _init_db(self):
        """Initialize database tables"""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS market_sentiment (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp TEXT NOT NULL,
                    bias TEXT NOT NULL,
                    bullish_pct REAL,
                    bullish_count INTEGER,
                    bearish_count INTEGER,
                    top_bullish TEXT,
                    top_bearish TEXT,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP
                )
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS unusual_activity (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp TEXT NOT NULL,
                    symbol TEXT NOT NULL,
                    base_symbol TEXT NOT NULL,
                    option_type TEXT NOT NULL,
                    strike REAL,
                    expiration TEXT,
                    days_to_exp INTEGER,
                    volume INTEGER,
                    open_interest INTEGER,
                    vol_oi_ratio REAL,
                    volatility REAL,
                    delta REAL,
                    base_price REAL,
                    alert_sent INTEGER DEFAULT 0,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP
                )
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS options_signals (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp TEXT NOT NULL,
                    symbol TEXT NOT NULL,
                    signal_type TEXT NOT NULL,
                    direction TEXT NOT NULL,
                    confidence REAL,
                    entry_price REAL,
                    pc_ratio REAL,
                    volume INTEGER,
                    reasoning TEXT,
                    outcome TEXT,
                    pnl_pct REAL,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP
                )
            """)
            conn.commit()
        logger.info(f"📊 OptionsFlowStorage initialized: {self.db_path}")
    
    def store_sentiment(self, sentiment: Dict):
        """Store market sentiment snapshot"""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                INSERT INTO market_sentiment 
                (timestamp, bias, bullish_pct, bullish_count, bearish_count, top_bullish, top_bearish)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (
                datetime.now().isoformat(),
                sentiment.get('bias', 'NEUTRAL'),
                sentiment.get('bullish_pct', 50),
                sentiment.get('bullish_count', 0),
                sentiment.get('bearish_count', 0),
                json.dumps(sentiment.get('top_bullish', [])),
                json.dumps(sentiment.get('top_bearish', []))
            ))
            conn.commit()
    
    def store_unusual(self, unusual: UnusualOption):
        """Store unusual options activity"""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                INSERT INTO unusual_activity 
                (timestamp, symbol, base_symbol, option_type, strike, expiration, 
                 days_to_exp, volume, open_interest, vol_oi_ratio, volatility, delta, base_price)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                datetime.now().isoformat(),
                unusual.symbol,
                unusual.base_symbol,
                unusual.option_type,
                unusual.strike,
                unusual.expiration,
                unusual.days_to_exp,
                unusual.volume,
                unusual.open_interest,
                unusual.vol_oi_ratio,
                unusual.volatility,
                unusual.delta,
                unusual.base_price
            ))
            conn.commit()
    
    def store_signal(self, signal: Dict):
        """Store generated signal"""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                INSERT INTO options_signals 
                (timestamp, symbol, signal_type, direction, confidence, entry_price, 
                 pc_ratio, volume, reasoning)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                datetime.now().isoformat(),
                signal.get('symbol'),
                signal.get('signal_type'),
                signal.get('direction'),
                signal.get('confidence'),
                signal.get('entry_price'),
                signal.get('pc_ratio'),
                signal.get('volume'),
                signal.get('reasoning')
            ))
            conn.commit()
    
    def get_recent_sentiment(self, hours: int = 24) -> List[Dict]:
        """Get recent sentiment snapshots"""
        cutoff = (datetime.now() - timedelta(hours=hours)).isoformat()
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute("""
                SELECT * FROM market_sentiment 
                WHERE timestamp > ? 
                ORDER BY timestamp DESC
            """, (cutoff,))
            return [dict(row) for row in cursor.fetchall()]
    
    def detect_sentiment_shift(self) -> Optional[Dict]:
        """Detect if sentiment shifted significantly"""
        recent = self.get_recent_sentiment(hours=4)
        if len(recent) < 2:
            return None
        
        latest = recent[0]
        previous = recent[-1]
        
        shift = latest['bullish_pct'] - previous['bullish_pct']
        
        if abs(shift) >= 10:  # 10% shift threshold
            return {
                'shift': shift,
                'from_bias': previous['bias'],
                'to_bias': latest['bias'],
                'from_pct': previous['bullish_pct'],
                'to_pct': latest['bullish_pct']
            }
        return None


class OptionsFlowChecker(BaseChecker):
    """
    Options Flow Checker - Monitors institutional options positioning.
    
    Runs every 15-30 minutes during RTH.
    Generates alerts for significant options flow.
    """
    
    # Symbols to monitor for specific unusual activity
    WATCH_SYMBOLS = ['SPY', 'QQQ', 'AAPL', 'NVDA', 'TSLA', 'AMZN', 'MSFT', 'META', 'GOOGL']
    
    # Alert thresholds
    BULLISH_PC_THRESHOLD = 0.7  # P/C below this = bullish
    BEARISH_PC_THRESHOLD = 1.2  # P/C above this = bearish
    MIN_VOLUME_ALERT = 500000   # Minimum volume for alerts
    UNUSUAL_VOL_OI_THRESHOLD = 40  # Vol/OI above this = very unusual
    
    def __init__(self, alert_manager, api_key: str = None, unified_mode: bool = False, confluence_gate=None):
        """
        Initialize Options Flow Checker.
        
        Args:
            alert_manager: AlertManager for sending Discord alerts
            api_key: RapidAPI key (defaults to env var)
            unified_mode: If True, suppresses individual alerts
            confluence_gate: ConfluenceGate instance (blocks blind signals)
        """
        super().__init__(alert_manager, unified_mode)
        
        self.api_key = api_key or os.getenv('YAHOO_RAPIDAPI_KEY')
        self.client = RapidAPIOptionsClient(api_key=self.api_key)
        self.storage = OptionsFlowStorage()
        self.confluence_gate = confluence_gate
        
        # State tracking
        self.last_sentiment: Optional[Dict] = None
        self.alerted_unusual: set = set()  # Track already-alerted unusual activity
        self.alerted_bullish: set = set()  # Track already-alerted bullish symbols
        self.alerted_bearish: set = set()  # Track already-alerted bearish symbols
        
        logger.info("📊 OptionsFlowChecker initialized (RapidAPI)")
    
    @property
    def name(self) -> str:
        return "options_flow_checker"
    
    def check(self, symbols: List[str] = None) -> List[CheckerAlert]:
        """
        Check options flow for signals.
        
        Returns:
            List of CheckerAlert objects for any detected signals
        """
        alerts = []
        
        try:
            # 1. Get market sentiment
            sentiment = self.client.get_market_sentiment()
            self.storage.store_sentiment(sentiment)
            
            logger.info(f"📊 Options Flow: {sentiment['bias']} ({sentiment['bullish_pct']:.1f}% bullish)")
            
            # 2. Check for sentiment shift
            shift = self.storage.detect_sentiment_shift()
            if shift:
                alert = self._create_sentiment_shift_alert(shift, sentiment)
                alerts.append(alert)
            
            # 3. Get most active options
            most_active = self.client.get_most_active_options()
            
            # Check for extreme P/C ratios on watch symbols
            for opt in most_active:
                if opt.symbol in self.WATCH_SYMBOLS or opt.total_volume >= self.MIN_VOLUME_ALERT:
                    if opt.put_call_ratio < self.BULLISH_PC_THRESHOLD:
                        # DEDUP: Skip if already alerted for this symbol today
                        if opt.symbol in self.alerted_bullish:
                            logger.debug(f"   ⏭️ Already alerted bullish for {opt.symbol} — skipping")
                            continue
                        # ═══ CONFLUENCE GATE ═══
                        gate_multiplier = 1.0
                        if self.confluence_gate:
                            confidence = min(90, 50 + (0.7 - opt.put_call_ratio) * 100)
                            gate_result = self.confluence_gate.should_fire(
                                signal_direction="LONG",
                                symbol=opt.symbol,
                                raw_confidence=confidence,
                            )
                            if gate_result.blocked:
                                logger.warning(f"   ⛔ OPTIONS FLOW BLOCKED: {opt.symbol} LONG — {gate_result.reason}")
                                continue
                            gate_multiplier = gate_result.sizing_multiplier
                        # ═══ END GATE ═══
                        alert = self._create_bullish_alert(opt, gate_multiplier)
                        if alert:
                            alerts.append(alert)
                            self.alerted_bullish.add(opt.symbol)
                            self._store_signal(opt, "BULLISH_CALL_ACCUMULATION", "LONG")
                    
                    elif opt.put_call_ratio > self.BEARISH_PC_THRESHOLD:
                        # DEDUP: Skip if already alerted for this symbol today
                        if opt.symbol in self.alerted_bearish:
                            logger.debug(f"   ⏭️ Already alerted bearish for {opt.symbol} — skipping")
                            continue
                        # ═══ CONFLUENCE GATE ═══
                        gate_multiplier = 1.0
                        if self.confluence_gate:
                            confidence = min(90, 50 + (opt.put_call_ratio - 1.2) * 50)
                            gate_result = self.confluence_gate.should_fire(
                                signal_direction="SHORT",
                                symbol=opt.symbol,
                                raw_confidence=confidence,
                            )
                            if gate_result.blocked:
                                logger.warning(f"   ⛔ OPTIONS FLOW BLOCKED: {opt.symbol} SHORT — {gate_result.reason}")
                                continue
                            gate_multiplier = gate_result.sizing_multiplier
                        # ═══ END GATE ═══
                        alert = self._create_bearish_alert(opt, gate_multiplier)
                        if alert:
                            alerts.append(alert)
                            self.alerted_bearish.add(opt.symbol)
                            self._store_signal(opt, "BEARISH_PUT_ACCUMULATION", "SHORT")
            
            # 4. Get unusual activity for watch symbols
            for symbol in (symbols or self.WATCH_SYMBOLS[:5]):
                unusual = self.client.get_unusual_for_symbol(symbol)
                for u in unusual:
                    if u.vol_oi_ratio >= self.UNUSUAL_VOL_OI_THRESHOLD:
                        if u.symbol not in self.alerted_unusual:
                            alert = self._create_unusual_alert(u)
                            alerts.append(alert)
                            self.storage.store_unusual(u)
                            self.alerted_unusual.add(u.symbol)
            
            # 5. Update last sentiment
            self.last_sentiment = sentiment
            
            logger.info(f"   ✅ Generated {len(alerts)} options flow alerts")
            
        except Exception as e:
            logger.error(f"❌ Options flow check error: {e}")
            import traceback
            logger.debug(traceback.format_exc())
        
        return alerts
    
    def _create_sentiment_shift_alert(self, shift: Dict, sentiment: Dict) -> CheckerAlert:
        """Create alert for market sentiment shift"""
        direction = "BULLISH" if shift['shift'] > 0 else "BEARISH"
        emoji = "🟢📈" if direction == "BULLISH" else "🔴📉"
        color = 0x00FF00 if direction == "BULLISH" else 0xFF0000
        
        message = f"""
**{emoji} MARKET SENTIMENT SHIFT**

The options market has shifted **{abs(shift['shift']):.1f}%** towards **{direction}**!

━━━━━━━━━━━━━━━━━━━━━━━━━━━━
**📊 SENTIMENT CHANGE:**
• From: {shift['from_bias']} ({shift['from_pct']:.1f}% bullish)
• To: {shift['to_bias']} ({shift['to_pct']:.1f}% bullish)
• Shift: {shift['shift']:+.1f}%

━━━━━━━━━━━━━━━━━━━━━━━━━━━━
**🎯 TOP MOVERS:**
• Bullish: {', '.join(sentiment['top_bullish'][:3])}
• Bearish: {', '.join(sentiment['top_bearish'][:3])}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━
**💡 INTERPRETATION:**
{'Institutions rotating to CALLS - expect upside' if direction == 'BULLISH' else 'Institutions rotating to PUTS - expect downside or hedging'}

⚠️ **ACTION:** {'Consider LONG bias on SPY/QQQ' if direction == 'BULLISH' else 'Consider defensive positioning or SHORT bias'}
"""
        
        embed = {
            "title": f"{emoji} OPTIONS SENTIMENT: {direction} SHIFT",
            "description": message.strip()[:2000],  # Discord limit
            "color": color,
            "fields": [
                {"name": "Shift", "value": f"{shift['shift']:+.1f}%", "inline": True},
                {"name": "Current Bias", "value": sentiment['bias'], "inline": True},
                {"name": "Bullish %", "value": f"{sentiment['bullish_pct']:.1f}%", "inline": True}
            ],
            "timestamp": datetime.now().isoformat()
        }
        
        return CheckerAlert(
            embed=embed,
            content=f"📊 Options Sentiment Shift: {direction} ({shift['shift']:+.1f}%)",
            alert_type="options_sentiment",
            source=self.name
        )
    
    def _create_bullish_alert(self, opt: MostActiveOption, multiplier: float = 1.0) -> Optional[CheckerAlert]:
        """Create alert for bullish call accumulation"""
        # Skip if not significant enough
        if opt.total_volume < 300000:
            return None
        
        # Format sizing multiplier string
        if multiplier >= 3.0:
            sz_str = f"🔥 MAX CONVICTION ({multiplier}x)"
        elif multiplier >= 1.0:
            sz_str = f"🟡 STANDARD ({multiplier}x)"
        else:
            sz_str = f"⚪ LIGHT ({multiplier}x)"

        message = f"""
**🟢 BULLISH CALL ACCUMULATION: {opt.symbol}**

Heavy call buying detected - institutions positioning for upside.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━
**📊 OPTIONS DATA:**
• P/C Ratio: **{opt.put_call_ratio:.2f}** (Very Bullish < 0.7)
• Call Volume: **{opt.call_volume_pct:.0f}%** of flow
• Put Volume: {opt.put_volume_pct:.0f}%
• Total Volume: **{opt.total_volume:,}** contracts

━━━━━━━━━━━━━━━━━━━━━━━━━━━━
**📈 STOCK DATA:**
• Price: **${opt.last_price:.2f}**
• Change: {opt.percent_change:+.2f}%
• IV Rank (1Y): {opt.iv_rank_1y:.1f}%

━━━━━━━━━━━━━━━━━━━━━━━━━━━━
**🎯 SIGNAL:**
• Direction: **LONG**
• Kill Chain Conviction: **{sz_str}**
• Confidence: {min(90, 50 + (0.7 - opt.put_call_ratio) * 100):.0f}%
• Timeframe: Days to weeks

⚠️ Smart money is buying calls. Follow the flow!
"""
        
        embed = {
            "title": f"🟢 BULLISH: {opt.symbol} Call Accumulation",
            "description": message.strip()[:2000],
            "color": 0x00FF00,
            "fields": [
                {"name": "Symbol", "value": opt.symbol, "inline": True},
                {"name": "P/C Ratio", "value": f"{opt.put_call_ratio:.2f}", "inline": True},
                {"name": "Sizing", "value": f"{multiplier}x", "inline": True},
                {"name": "Price", "value": f"${opt.last_price:.2f}", "inline": True}
            ],
            "timestamp": datetime.now().isoformat()
        }
        
        return CheckerAlert(
            embed=embed,
            content=f"🟢 BULLISH {opt.symbol}: P/C {opt.put_call_ratio:.2f}, Vol {opt.total_volume:,}",
            alert_type="bullish_options",
            source=self.name,
            symbol=opt.symbol
        )
    
    def _create_bearish_alert(self, opt: MostActiveOption, multiplier: float = 1.0) -> Optional[CheckerAlert]:
        """Create alert for bearish put accumulation"""
        if opt.total_volume < 300000:
            return None
        
        # Format sizing multiplier string
        if multiplier >= 3.0:
            sz_str = f"🔥 MAX CONVICTION ({multiplier}x)"
        elif multiplier >= 1.0:
            sz_str = f"🟡 STANDARD ({multiplier}x)"
        else:
            sz_str = f"⚪ LIGHT ({multiplier}x)"

        message = f"""
**🔴 BEARISH PUT ACCUMULATION: {opt.symbol}**

Heavy put buying detected - institutions hedging or betting on downside.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━
**📊 OPTIONS DATA:**
• P/C Ratio: **{opt.put_call_ratio:.2f}** (Bearish > 1.2)
• Put Volume: **{opt.put_volume_pct:.0f}%** of flow
• Call Volume: {opt.call_volume_pct:.0f}%
• Total Volume: **{opt.total_volume:,}** contracts

━━━━━━━━━━━━━━━━━━━━━━━━━━━━
**📈 STOCK DATA:**
• Price: **${opt.last_price:.2f}**
• Change: {opt.percent_change:+.2f}%
• IV Rank (1Y): {opt.iv_rank_1y:.1f}%

━━━━━━━━━━━━━━━━━━━━━━━━━━━━
**🎯 SIGNAL:**
• Direction: **SHORT** or **HEDGE**
• Kill Chain Conviction: **{sz_str}**
• Confidence: {min(90, 50 + (opt.put_call_ratio - 1.2) * 50):.0f}%
• Timeframe: Days to weeks

⚠️ Institutions buying protection. Consider hedging!
"""
        
        embed = {
            "title": f"🔴 BEARISH: {opt.symbol} Put Accumulation",
            "description": message.strip()[:2000],
            "color": 0xFF0000,
            "fields": [
                {"name": "Symbol", "value": opt.symbol, "inline": True},
                {"name": "P/C Ratio", "value": f"{opt.put_call_ratio:.2f}", "inline": True},
                {"name": "Sizing", "value": f"{multiplier}x", "inline": True},
                {"name": "Price", "value": f"${opt.last_price:.2f}", "inline": True}
            ],
            "timestamp": datetime.now().isoformat()
        }
        
        return CheckerAlert(
            embed=embed,
            content=f"🔴 BEARISH {opt.symbol}: P/C {opt.put_call_ratio:.2f}, Vol {opt.total_volume:,}",
            alert_type="bearish_options",
            source=self.name,
            symbol=opt.symbol
        )
    
    def _create_unusual_alert(self, unusual: UnusualOption) -> CheckerAlert:
        """Create alert for unusual options activity"""
        emoji = "📈" if unusual.option_type == "Call" else "📉"
        color = 0x00FF00 if unusual.option_type == "Call" else 0xFF0000
        direction = "BULLISH" if unusual.option_type == "Call" else "BEARISH"
        
        message = f"""
**🔥 UNUSUAL OPTIONS ACTIVITY: {unusual.base_symbol}**

Extremely high volume relative to open interest detected!

━━━━━━━━━━━━━━━━━━━━━━━━━━━━
**📊 CONTRACT DETAILS:**
• Contract: **{unusual.option_type} ${unusual.strike:.2f}**
• Expiration: **{unusual.expiration}** ({unusual.days_to_exp} days)
• Volume: **{unusual.volume:,}** contracts
• Open Interest: {unusual.open_interest:,}
• **Vol/OI Ratio: {unusual.vol_oi_ratio:.1f}x** (Very Unusual > 30x)

━━━━━━━━━━━━━━━━━━━━━━━━━━━━
**📈 GREEKS & IV:**
• Delta: {unusual.delta:.4f}
• Implied Volatility: **{unusual.volatility:.1f}%**
• Stock Price: ${unusual.base_price:.2f}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━
**🧠 INTERPRETATION:**
• Vol/OI > 30x = Someone knows something
• {unusual.days_to_exp} days to expiry = {'Near-term catalyst expected' if unusual.days_to_exp < 30 else 'Longer-term positioning'}
• {direction} positioning

⚠️ **INVESTIGATE FURTHER:** Check for upcoming earnings, FDA decisions, or other catalysts!
"""
        
        embed = {
            "title": f"🔥 UNUSUAL: {unusual.base_symbol} {unusual.option_type} ${unusual.strike:.0f}",
            "description": message.strip()[:2000],
            "color": color,
            "fields": [
                {"name": "Symbol", "value": unusual.base_symbol, "inline": True},
                {"name": "Contract", "value": f"{unusual.option_type} ${unusual.strike:.2f}", "inline": True},
                {"name": "Vol/OI", "value": f"{unusual.vol_oi_ratio:.1f}x", "inline": True},
                {"name": "Expiration", "value": unusual.expiration, "inline": True}
            ],
            "timestamp": datetime.now().isoformat()
        }
        
        return CheckerAlert(
            embed=embed,
            content=f"🔥 UNUSUAL {unusual.base_symbol}: {unusual.option_type} ${unusual.strike:.0f} Vol/OI {unusual.vol_oi_ratio:.1f}x",
            alert_type="unusual_options",
            source=self.name,
            symbol=unusual.base_symbol
        )
    
    def _store_signal(self, opt: MostActiveOption, signal_type: str, direction: str):
        """Store signal for tracking"""
        self.storage.store_signal({
            'symbol': opt.symbol,
            'signal_type': signal_type,
            'direction': direction,
            'confidence': 70,
            'entry_price': opt.last_price,
            'pc_ratio': opt.put_call_ratio,
            'volume': opt.total_volume,
            'reasoning': f"P/C ratio {opt.put_call_ratio:.2f}, Volume {opt.total_volume:,}"
        })


# Standalone test
if __name__ == "__main__":
    from dotenv import load_dotenv
    load_dotenv()
    
    print("=" * 70)
    print("📊 OPTIONS FLOW CHECKER TEST")
    print("=" * 70)
    
    class MockAlertManager:
        def send_alert(self, alert):
            print(f"[MOCK ALERT] {alert.embed.get('title', 'N/A')}")
    
    checker = OptionsFlowChecker(
        alert_manager=MockAlertManager(),
        api_key=os.getenv('YAHOO_RAPIDAPI_KEY')
    )
    
    print(f"\nChecker: {checker.name}")
    print(f"Watch Symbols: {checker.WATCH_SYMBOLS}")
    
    print("\n🔍 Running check...")
    alerts = checker.check()
    
    print(f"\n✅ Generated {len(alerts)} alerts:")
    for alert in alerts[:5]:
        print(f"\n{'='*50}")
        print(f"Title: {alert.embed.get('title', 'N/A')}")
        print(f"Alert Type: {alert.alert_type}")
        print(f"Symbol: {alert.symbol}")
        print(f"Source: {alert.source}")
    
    print("\n" + "=" * 70)
    print("✅ Options Flow Checker test complete!")
