#!/usr/bin/env python3
"""
🔍 UNUSUAL ACTIVITY INVESTIGATOR

Deep dive framework for investigating unusual options activity.
When we see something like "UNH: Massive put hedging (Vol/OI 47x)",
this agent digs deeper to understand WHY.

INVESTIGATION FRAMEWORK:
1. OPTIONS ANALYSIS - What exactly is being bought?
2. NEWS SCAN - Any recent catalysts?
3. INSIDER ACTIVITY - Any unusual filings?
4. SECTOR CONTEXT - Is the whole sector moving?
5. TECHNICAL ANALYSIS - Support/resistance levels
6. EARNINGS CHECK - Upcoming earnings?
7. SYNTHESIS - Put it all together

GOAL: Answer "WHY is smart money positioning this way?"
"""

import os
import sys
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional
from dataclasses import dataclass, field
import json
import sqlite3

# Add paths
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

logger = logging.getLogger(__name__)


@dataclass
class InvestigationReport:
    """Complete investigation report for unusual activity"""
    symbol: str
    investigation_time: datetime = field(default_factory=datetime.now)
    
    # Options Analysis
    unusual_contracts: List[Dict] = field(default_factory=list)
    total_unusual_volume: int = 0
    dominant_direction: str = "UNKNOWN"  # BULLISH, BEARISH, MIXED
    avg_days_to_exp: float = 0
    strike_analysis: str = ""
    
    # News Context
    recent_headlines: List[str] = field(default_factory=list)
    news_sentiment: str = "NEUTRAL"  # BULLISH, BEARISH, NEUTRAL
    potential_catalysts: List[str] = field(default_factory=list)
    
    # Sector Context
    sector: str = ""
    sector_performance: float = 0
    peer_comparison: Dict = field(default_factory=dict)
    
    # Technical Context
    support_levels: List[float] = field(default_factory=list)
    resistance_levels: List[float] = field(default_factory=list)
    current_price: float = 0
    trend: str = "NEUTRAL"  # UPTREND, DOWNTREND, RANGE
    
    # Earnings
    next_earnings_date: str = ""
    earnings_in_days: int = -1
    
    # Synthesis
    confidence_score: float = 0
    thesis: str = ""
    recommended_action: str = "WATCH"  # LONG, SHORT, WATCH, AVOID
    risk_factors: List[str] = field(default_factory=list)
    
    def to_dict(self) -> Dict:
        """Convert to dictionary"""
        return {
            'symbol': self.symbol,
            'investigation_time': self.investigation_time.isoformat(),
            'unusual_contracts': self.unusual_contracts,
            'total_unusual_volume': self.total_unusual_volume,
            'dominant_direction': self.dominant_direction,
            'avg_days_to_exp': self.avg_days_to_exp,
            'strike_analysis': self.strike_analysis,
            'recent_headlines': self.recent_headlines,
            'news_sentiment': self.news_sentiment,
            'potential_catalysts': self.potential_catalysts,
            'sector': self.sector,
            'sector_performance': self.sector_performance,
            'peer_comparison': self.peer_comparison,
            'support_levels': self.support_levels,
            'resistance_levels': self.resistance_levels,
            'current_price': self.current_price,
            'trend': self.trend,
            'next_earnings_date': self.next_earnings_date,
            'earnings_in_days': self.earnings_in_days,
            'confidence_score': self.confidence_score,
            'thesis': self.thesis,
            'recommended_action': self.recommended_action,
            'risk_factors': self.risk_factors
        }
    
    def generate_report(self) -> str:
        """Generate human-readable investigation report"""
        return f"""
{'='*70}
🔍 UNUSUAL ACTIVITY INVESTIGATION: {self.symbol}
{'='*70}

📅 Investigation Time: {self.investigation_time.strftime('%Y-%m-%d %H:%M')}
💰 Current Price: ${self.current_price:.2f}

{'='*70}
📊 OPTIONS ANALYSIS
{'='*70}
• Unusual Contracts: {len(self.unusual_contracts)}
• Total Volume: {self.total_unusual_volume:,}
• Direction: **{self.dominant_direction}**
• Avg Days to Expiry: {self.avg_days_to_exp:.0f}
• Strike Analysis: {self.strike_analysis}

{'='*70}
📰 NEWS CONTEXT
{'='*70}
• News Sentiment: {self.news_sentiment}
• Potential Catalysts: {', '.join(self.potential_catalysts) if self.potential_catalysts else 'None identified'}

Recent Headlines:
{chr(10).join(f'  • {h}' for h in self.recent_headlines[:5]) if self.recent_headlines else '  No recent news'}

{'='*70}
🏢 SECTOR CONTEXT
{'='*70}
• Sector: {self.sector}
• Sector Performance: {self.sector_performance:+.2f}%
• Peer Comparison: {self.peer_comparison}

{'='*70}
📈 TECHNICAL CONTEXT
{'='*70}
• Trend: {self.trend}
• Support Levels: {', '.join(f'${s:.2f}' for s in self.support_levels) if self.support_levels else 'N/A'}
• Resistance Levels: {', '.join(f'${r:.2f}' for r in self.resistance_levels) if self.resistance_levels else 'N/A'}

{'='*70}
📆 EARNINGS
{'='*70}
• Next Earnings: {self.next_earnings_date if self.next_earnings_date else 'Unknown'}
• Days Until: {self.earnings_in_days if self.earnings_in_days > 0 else 'N/A'}

{'='*70}
🧠 SYNTHESIS
{'='*70}
**Thesis:** {self.thesis}

**Recommended Action:** {self.recommended_action}
**Confidence:** {self.confidence_score:.0f}%

**Risk Factors:**
{chr(10).join(f'  ⚠️ {r}' for r in self.risk_factors) if self.risk_factors else '  None identified'}

{'='*70}
"""


class UnusualActivityInvestigator:
    """
    Deep dive investigator for unusual options activity.
    
    When triggered by the OptionsFlowChecker detecting unusual activity,
    this agent investigates WHY smart money is positioning.
    """
    
    # Sector mappings
    SECTOR_ETFS = {
        'XLV': 'Healthcare',
        'XLF': 'Financials',
        'XLK': 'Technology',
        'XLE': 'Energy',
        'XLI': 'Industrials',
        'XLY': 'Consumer Discretionary',
        'XLP': 'Consumer Staples',
        'XLU': 'Utilities',
        'XLB': 'Materials',
        'XLRE': 'Real Estate',
        'XLC': 'Communication'
    }
    
    # Stock to sector mapping (expand as needed)
    STOCK_SECTORS = {
        'UNH': ('XLV', 'Healthcare'),
        'JNJ': ('XLV', 'Healthcare'),
        'PFE': ('XLV', 'Healthcare'),
        'MRNA': ('XLV', 'Healthcare'),
        'CVS': ('XLV', 'Healthcare'),
        'AAPL': ('XLK', 'Technology'),
        'MSFT': ('XLK', 'Technology'),
        'NVDA': ('XLK', 'Technology'),
        'GOOGL': ('XLC', 'Communication'),
        'META': ('XLC', 'Communication'),
        'JPM': ('XLF', 'Financials'),
        'GS': ('XLF', 'Financials'),
        'TSLA': ('XLY', 'Consumer Discretionary'),
        'AMZN': ('XLY', 'Consumer Discretionary'),
    }
    
    def __init__(
        self,
        options_client=None,
        news_client=None,
        db_path: str = "data/investigations.db"
    ):
        """
        Initialize the investigator.
        
        Args:
            options_client: RapidAPIOptionsClient instance
            news_client: RapidAPINewsClient instance
            db_path: Path to store investigation results
        """
        self.db_path = db_path
        os.makedirs(os.path.dirname(db_path), exist_ok=True)
        
        # Initialize clients if not provided
        if options_client is None:
            from core.data.rapidapi_options_client import RapidAPIOptionsClient
            self.options_client = RapidAPIOptionsClient()
        else:
            self.options_client = options_client
        
        if news_client is None:
            from core.data.rapidapi_news_client import RapidAPINewsClient
            self.news_client = RapidAPINewsClient()
        else:
            self.news_client = news_client
        
        self._init_db()
        logger.info("🔍 UnusualActivityInvestigator initialized")
    
    def _init_db(self):
        """Initialize database"""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS investigations (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp TEXT NOT NULL,
                    symbol TEXT NOT NULL,
                    trigger_reason TEXT,
                    report_json TEXT,
                    recommended_action TEXT,
                    confidence REAL,
                    outcome TEXT,
                    outcome_date TEXT,
                    pnl_pct REAL,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP
                )
            """)
            conn.commit()
    
    def investigate(self, symbol: str, trigger_reason: str = None) -> InvestigationReport:
        """
        Conduct full investigation on a symbol.
        
        Args:
            symbol: Stock symbol to investigate
            trigger_reason: Why this investigation was triggered
            
        Returns:
            InvestigationReport with all findings
        """
        logger.info(f"🔍 Investigating {symbol}...")
        
        report = InvestigationReport(symbol=symbol)
        
        # 1. Analyze unusual options
        self._analyze_options(report)
        
        # 2. Scan recent news
        self._scan_news(report)
        
        # 3. Get sector context
        self._get_sector_context(report)
        
        # 4. Technical analysis (basic)
        self._analyze_technicals(report)
        
        # 5. Check earnings
        self._check_earnings(report)
        
        # 6. Synthesize findings
        self._synthesize(report)
        
        # 7. Store investigation
        self._store_investigation(report, trigger_reason)
        
        logger.info(f"   ✅ Investigation complete: {report.recommended_action} ({report.confidence_score:.0f}%)")
        
        return report
    
    def _analyze_options(self, report: InvestigationReport):
        """Analyze unusual options activity"""
        try:
            unusual = self.options_client.get_unusual_for_symbol(report.symbol)
            
            if not unusual:
                return
            
            report.unusual_contracts = [
                {
                    'type': u.option_type,
                    'strike': u.strike,
                    'expiration': u.expiration,
                    'days_to_exp': u.days_to_exp,
                    'volume': u.volume,
                    'oi': u.open_interest,
                    'vol_oi': u.vol_oi_ratio,
                    'iv': u.volatility
                }
                for u in unusual[:10]  # Top 10
            ]
            
            report.total_unusual_volume = sum(u.volume for u in unusual)
            
            # Determine dominant direction
            calls = [u for u in unusual if u.option_type == 'Call']
            puts = [u for u in unusual if u.option_type == 'Put']
            
            call_volume = sum(u.volume for u in calls)
            put_volume = sum(u.volume for u in puts)
            
            if call_volume > put_volume * 1.5:
                report.dominant_direction = "BULLISH"
            elif put_volume > call_volume * 1.5:
                report.dominant_direction = "BEARISH"
            else:
                report.dominant_direction = "MIXED"
            
            # Average days to expiry
            if unusual:
                report.avg_days_to_exp = sum(u.days_to_exp for u in unusual) / len(unusual)
            
            # Strike analysis
            if unusual and report.current_price > 0:
                avg_strike = sum(u.strike for u in unusual) / len(unusual)
                if avg_strike > report.current_price * 1.05:
                    report.strike_analysis = "OTM - Speculative/Lottery"
                elif avg_strike < report.current_price * 0.95:
                    report.strike_analysis = "ITM - Protection/Hedging"
                else:
                    report.strike_analysis = "ATM - Directional Bet"
            
        except Exception as e:
            logger.warning(f"Options analysis failed: {e}")
    
    def _scan_news(self, report: InvestigationReport):
        """Scan recent news for context"""
        try:
            # Use correct API signature
            news = self.news_client.get_credible_news(
                ticker=report.symbol,
                hours=24
            )
            
            # Convert NewsArticle objects to headlines
            report.recent_headlines = [getattr(n, 'title', '') for n in news[:10]]
            
            # Determine sentiment
            bullish_words = ['beat', 'surge', 'upgrade', 'record', 'growth']
            bearish_words = ['miss', 'plunge', 'lawsuit', 'downgrade', 'crisis']
            
            all_text = ' '.join(report.recent_headlines).lower()
            
            bullish_count = sum(1 for w in bullish_words if w in all_text)
            bearish_count = sum(1 for w in bearish_words if w in all_text)
            
            if bullish_count > bearish_count:
                report.news_sentiment = "BULLISH"
            elif bearish_count > bullish_count:
                report.news_sentiment = "BEARISH"
            else:
                report.news_sentiment = "NEUTRAL"
            
            # Identify catalysts
            catalyst_keywords = {
                'earnings': 'Earnings Report',
                'fda': 'FDA Decision',
                'merger': 'M&A Activity',
                'lawsuit': 'Legal Risk',
                'ceo': 'Executive Change',
                'guidance': 'Guidance Update',
                'layoff': 'Restructuring'
            }
            
            for keyword, catalyst in catalyst_keywords.items():
                if keyword in all_text:
                    report.potential_catalysts.append(catalyst)
            
        except Exception as e:
            logger.warning(f"News scan failed: {e}")
    
    def _get_sector_context(self, report: InvestigationReport):
        """Get sector context"""
        try:
            sector_info = self.STOCK_SECTORS.get(report.symbol.upper())
            
            if sector_info:
                report.sector = sector_info[1]
                # Note: Would need yfinance or similar to get actual sector performance
                # For now, placeholder
                report.sector_performance = 0
                report.peer_comparison = {'sector': sector_info[0]}
            
        except Exception as e:
            logger.warning(f"Sector analysis failed: {e}")
    
    def _analyze_technicals(self, report: InvestigationReport):
        """Basic technical analysis"""
        try:
            import yfinance as yf
            
            ticker = yf.Ticker(report.symbol)
            hist = ticker.history(period='1mo')
            
            if hist.empty:
                return
            
            report.current_price = float(hist['Close'].iloc[-1])
            
            # Simple trend detection
            sma_10 = hist['Close'].rolling(10).mean().iloc[-1]
            sma_20 = hist['Close'].rolling(20).mean().iloc[-1]
            
            if report.current_price > sma_10 > sma_20:
                report.trend = "UPTREND"
            elif report.current_price < sma_10 < sma_20:
                report.trend = "DOWNTREND"
            else:
                report.trend = "RANGE"
            
            # Support/Resistance (simplified)
            report.support_levels = [hist['Low'].min(), hist['Close'].quantile(0.25)]
            report.resistance_levels = [hist['High'].max(), hist['Close'].quantile(0.75)]
            
        except Exception as e:
            logger.warning(f"Technical analysis failed: {e}")
    
    def _check_earnings(self, report: InvestigationReport):
        """Check upcoming earnings"""
        try:
            import yfinance as yf
            
            ticker = yf.Ticker(report.symbol)
            
            # Get calendar data
            try:
                calendar = ticker.calendar
                if calendar is not None and 'Earnings Date' in calendar:
                    earnings_date = calendar['Earnings Date']
                    if hasattr(earnings_date, '__iter__'):
                        earnings_date = list(earnings_date)[0]
                    report.next_earnings_date = str(earnings_date)
                    
                    # Calculate days until
                    if hasattr(earnings_date, 'date'):
                        days = (earnings_date.date() - datetime.now().date()).days
                        report.earnings_in_days = days
            except:
                pass
            
        except Exception as e:
            logger.warning(f"Earnings check failed: {e}")
    
    def _synthesize(self, report: InvestigationReport):
        """Synthesize all findings into actionable thesis"""
        confidence = 50  # Base confidence
        risk_factors = []
        thesis_parts = []
        
        # Options-based thesis
        if report.dominant_direction == "BULLISH":
            thesis_parts.append("Smart money buying calls")
            confidence += 15
        elif report.dominant_direction == "BEARISH":
            thesis_parts.append("Smart money buying puts/hedging")
            confidence += 15
            risk_factors.append("Institutional hedging detected")
        
        # Near-term expiry = urgent catalyst expected
        if report.avg_days_to_exp < 14:
            thesis_parts.append("Near-term catalyst expected")
            confidence += 10
        
        # News alignment
        if report.news_sentiment == report.dominant_direction:
            thesis_parts.append(f"News confirms {report.dominant_direction} positioning")
            confidence += 10
        elif report.news_sentiment != "NEUTRAL" and report.dominant_direction != "MIXED":
            thesis_parts.append("News diverges from options flow - contrarian setup")
            risk_factors.append("News/options divergence")
        
        # Catalyst awareness
        if report.potential_catalysts:
            thesis_parts.append(f"Catalysts: {', '.join(report.potential_catalysts)}")
            confidence += 5
        
        # Earnings proximity
        if 0 < report.earnings_in_days <= 14:
            thesis_parts.append(f"Earnings in {report.earnings_in_days} days - event positioning")
            confidence += 5
            risk_factors.append("Earnings event risk")
        
        # Set confidence
        report.confidence_score = min(95, max(30, confidence))
        
        # Build thesis
        report.thesis = ". ".join(thesis_parts) if thesis_parts else "Insufficient data for thesis"
        
        # Determine action
        if report.dominant_direction == "BULLISH" and report.confidence_score >= 60:
            report.recommended_action = "LONG"
        elif report.dominant_direction == "BEARISH" and report.confidence_score >= 60:
            report.recommended_action = "SHORT"
        elif report.confidence_score < 50:
            report.recommended_action = "AVOID"
        else:
            report.recommended_action = "WATCH"
        
        report.risk_factors = risk_factors
    
    def _store_investigation(self, report: InvestigationReport, trigger_reason: str = None):
        """Store investigation in database"""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                INSERT INTO investigations 
                (timestamp, symbol, trigger_reason, report_json, recommended_action, confidence)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (
                datetime.now().isoformat(),
                report.symbol,
                trigger_reason,
                json.dumps(report.to_dict()),
                report.recommended_action,
                report.confidence_score
            ))
            conn.commit()


# Standalone test
if __name__ == "__main__":
    from dotenv import load_dotenv
    load_dotenv()
    
    print("=" * 70)
    print("🔍 UNUSUAL ACTIVITY INVESTIGATOR TEST")
    print("=" * 70)
    
    investigator = UnusualActivityInvestigator()
    
    # Investigate UNH (healthcare crisis example)
    print("\n🔍 Investigating UNH (massive put hedging detected)...")
    report = investigator.investigate("UNH", trigger_reason="Massive put hedging Vol/OI 47x")
    
    print(report.generate_report())
    
    # Also test TSLA
    print("\n" + "=" * 70)
    print("\n🔍 Investigating TSLA (bullish call flow)...")
    report2 = investigator.investigate("TSLA", trigger_reason="60% call volume, P/C 0.67")
    
    print(report2.generate_report())
    
    print("\n✅ Investigation complete!")

