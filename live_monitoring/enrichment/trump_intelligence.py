#!/usr/bin/env python3
"""
TRUMP INTELLIGENCE ENGINE
=========================
Proactive Trump monitoring for market exploitation.

We're not reacting to Trump - we're ANTICIPATING him.
"""

import os
import sys
import json
import logging
import requests
from datetime import datetime, timedelta
from dataclasses import dataclass, field
from typing import List, Dict, Optional, Any, Tuple
from enum import Enum

logger = logging.getLogger(__name__)

class TrumpCatalystType(Enum):
    """Types of Trump market-moving events"""
    TARIFF_THREAT = "tariff_threat"
    TARIFF_DEAL = "tariff_deal"
    TARIFF_IMPLEMENT = "tariff_implement"
    FED_CRITICISM = "fed_criticism"
    CHINA_HAWKISH = "china_hawkish"
    CHINA_DOVISH = "china_dovish"
    COMPANY_ATTACK = "company_attack"
    COMPANY_PRAISE = "company_praise"
    WAR_THREAT = "war_threat"
    WAR_DEESCALATION = "war_deescalation"
    GEOPOLITICAL = "geopolitical"
    ECONOMIC_BOAST = "economic_boast"
    POLICY_ANNOUNCEMENT = "policy_announcement"
    UNKNOWN = "unknown"

class MarketImpact(Enum):
    """Expected market impact"""
    VERY_BEARISH = "very_bearish"  # -2% or more
    BEARISH = "bearish"            # -0.5% to -2%
    NEUTRAL = "neutral"            # -0.5% to +0.5%
    BULLISH = "bullish"            # +0.5% to +2%
    VERY_BULLISH = "very_bullish"  # +2% or more

@dataclass
class TrumpEvent:
    """A detected Trump market-moving event"""
    timestamp: datetime
    source: str  # truth_social, news, speech, etc.
    content: str
    catalyst_type: TrumpCatalystType
    keywords_matched: List[str]
    expected_impact: MarketImpact
    confidence: float  # 0-1
    affected_symbols: List[str]
    trade_recommendation: str
    urgency: str  # immediate, prepare, watch

@dataclass
class TrumpScenario:
    """A proactive scenario to prepare for"""
    scenario_id: str
    description: str
    trigger_conditions: List[str]
    probability: float  # 0-1
    if_bullish: Dict[str, Any]  # action if bullish outcome
    if_bearish: Dict[str, Any]  # action if bearish outcome
    preparation_actions: List[str]
    expiry: datetime


class TrumpKeywordEngine:
    """Analyzes text for Trump market-moving keywords"""
    
    def __init__(self):
        # Keywords with their typical market impact
        self.keyword_map = {
            # TARIFFS - High Impact
            "tariff": {"type": TrumpCatalystType.TARIFF_THREAT, "impact": MarketImpact.BEARISH, "symbols": ["SPY", "QQQ"]},
            "tariffs": {"type": TrumpCatalystType.TARIFF_THREAT, "impact": MarketImpact.BEARISH, "symbols": ["SPY", "QQQ"]},
            "trade war": {"type": TrumpCatalystType.TARIFF_THREAT, "impact": MarketImpact.VERY_BEARISH, "symbols": ["SPY", "QQQ", "FXI"]},
            "25%": {"type": TrumpCatalystType.TARIFF_THREAT, "impact": MarketImpact.BEARISH, "symbols": ["SPY"]},  # Common tariff %
            "100%": {"type": TrumpCatalystType.TARIFF_THREAT, "impact": MarketImpact.VERY_BEARISH, "symbols": ["SPY"]},
            
            # CHINA - High Impact
            "china": {"type": TrumpCatalystType.CHINA_HAWKISH, "impact": MarketImpact.BEARISH, "symbols": ["FXI", "BABA", "QQQ"]},
            "xi": {"type": TrumpCatalystType.CHINA_HAWKISH, "impact": MarketImpact.BEARISH, "symbols": ["FXI", "BABA"]},
            "ccp": {"type": TrumpCatalystType.CHINA_HAWKISH, "impact": MarketImpact.BEARISH, "symbols": ["FXI"]},
            "beijing": {"type": TrumpCatalystType.CHINA_HAWKISH, "impact": MarketImpact.BEARISH, "symbols": ["FXI"]},
            
            # DEAL KEYWORDS - Bullish
            "deal": {"type": TrumpCatalystType.TARIFF_DEAL, "impact": MarketImpact.BULLISH, "symbols": ["SPY", "QQQ"]},
            "agreement": {"type": TrumpCatalystType.TARIFF_DEAL, "impact": MarketImpact.BULLISH, "symbols": ["SPY"]},
            "negotiate": {"type": TrumpCatalystType.TARIFF_DEAL, "impact": MarketImpact.NEUTRAL, "symbols": ["SPY"]},
            "progress": {"type": TrumpCatalystType.TARIFF_DEAL, "impact": MarketImpact.BULLISH, "symbols": ["SPY"]},
            
            # FED - Medium Impact
            "fed": {"type": TrumpCatalystType.FED_CRITICISM, "impact": MarketImpact.NEUTRAL, "symbols": ["TLT", "GLD"]},
            "powell": {"type": TrumpCatalystType.FED_CRITICISM, "impact": MarketImpact.BEARISH, "symbols": ["TLT"]},
            "interest rate": {"type": TrumpCatalystType.FED_CRITICISM, "impact": MarketImpact.NEUTRAL, "symbols": ["TLT", "XLF"]},
            "rate cut": {"type": TrumpCatalystType.FED_CRITICISM, "impact": MarketImpact.BULLISH, "symbols": ["SPY", "TLT"]},
            
            # COMPANIES - Stock Specific
            "apple": {"type": TrumpCatalystType.COMPANY_ATTACK, "impact": MarketImpact.BEARISH, "symbols": ["AAPL"]},
            "amazon": {"type": TrumpCatalystType.COMPANY_ATTACK, "impact": MarketImpact.BEARISH, "symbols": ["AMZN"]},
            "boeing": {"type": TrumpCatalystType.COMPANY_ATTACK, "impact": MarketImpact.BEARISH, "symbols": ["BA"]},
            "tesla": {"type": TrumpCatalystType.COMPANY_PRAISE, "impact": MarketImpact.BULLISH, "symbols": ["TSLA"]},
            "elon": {"type": TrumpCatalystType.COMPANY_PRAISE, "impact": MarketImpact.BULLISH, "symbols": ["TSLA"]},
            
            # GEOPOLITICAL - Variable Impact
            "russia": {"type": TrumpCatalystType.GEOPOLITICAL, "impact": MarketImpact.NEUTRAL, "symbols": ["RSX", "USO"]},
            "putin": {"type": TrumpCatalystType.GEOPOLITICAL, "impact": MarketImpact.NEUTRAL, "symbols": ["RSX"]},
            "ukraine": {"type": TrumpCatalystType.GEOPOLITICAL, "impact": MarketImpact.BEARISH, "symbols": ["SPY", "USO"]},
            "iran": {"type": TrumpCatalystType.WAR_THREAT, "impact": MarketImpact.BEARISH, "symbols": ["USO", "XLE"]},
            "israel": {"type": TrumpCatalystType.GEOPOLITICAL, "impact": MarketImpact.NEUTRAL, "symbols": ["USO"]},
            "nato": {"type": TrumpCatalystType.GEOPOLITICAL, "impact": MarketImpact.NEUTRAL, "symbols": ["ITA"]},
            
            # MEXICO/CANADA - Medium Impact
            "mexico": {"type": TrumpCatalystType.TARIFF_THREAT, "impact": MarketImpact.BEARISH, "symbols": ["EWW", "SPY"]},
            "canada": {"type": TrumpCatalystType.TARIFF_THREAT, "impact": MarketImpact.BEARISH, "symbols": ["EWC", "SPY"]},
            "border": {"type": TrumpCatalystType.TARIFF_THREAT, "impact": MarketImpact.BEARISH, "symbols": ["SPY"]},
            "usmca": {"type": TrumpCatalystType.TARIFF_DEAL, "impact": MarketImpact.BULLISH, "symbols": ["SPY"]},
            
            # ENERGY - Sector Specific
            "oil": {"type": TrumpCatalystType.POLICY_ANNOUNCEMENT, "impact": MarketImpact.NEUTRAL, "symbols": ["USO", "XLE"]},
            "drill": {"type": TrumpCatalystType.POLICY_ANNOUNCEMENT, "impact": MarketImpact.BEARISH, "symbols": ["USO"]},  # More supply = lower prices
            "energy": {"type": TrumpCatalystType.POLICY_ANNOUNCEMENT, "impact": MarketImpact.NEUTRAL, "symbols": ["XLE"]},
            
            # WAR/MILITARY - High Impact
            "military": {"type": TrumpCatalystType.WAR_THREAT, "impact": MarketImpact.BEARISH, "symbols": ["SPY", "ITA"]},
            "war": {"type": TrumpCatalystType.WAR_THREAT, "impact": MarketImpact.VERY_BEARISH, "symbols": ["SPY", "VIX"]},
            "peace": {"type": TrumpCatalystType.WAR_DEESCALATION, "impact": MarketImpact.BULLISH, "symbols": ["SPY"]},
            "troops": {"type": TrumpCatalystType.WAR_THREAT, "impact": MarketImpact.BEARISH, "symbols": ["SPY", "ITA"]},
        }
        
        # Context modifiers - change the interpretation
        self.bullish_modifiers = ["great", "beautiful", "tremendous", "winning", "success", "deal", "agreement", "progress", "love"]
        self.bearish_modifiers = ["bad", "terrible", "disaster", "enemy", "threat", "attack", "war", "tariff", "sanction"]
    
    def analyze(self, text: str) -> Tuple[List[str], TrumpCatalystType, MarketImpact, List[str], float]:
        """
        Analyze text for Trump keywords
        Returns: (matched_keywords, catalyst_type, expected_impact, affected_symbols, confidence)
        """
        text_lower = text.lower()
        
        matched_keywords = []
        catalyst_types = []
        impacts = []
        all_symbols = set()
        
        # Find all keyword matches
        for keyword, data in self.keyword_map.items():
            if keyword in text_lower:
                matched_keywords.append(keyword)
                catalyst_types.append(data["type"])
                impacts.append(data["impact"])
                all_symbols.update(data["symbols"])
        
        if not matched_keywords:
            return [], TrumpCatalystType.UNKNOWN, MarketImpact.NEUTRAL, [], 0.0
        
        # Determine dominant catalyst type
        catalyst_counts = {}
        for ct in catalyst_types:
            catalyst_counts[ct] = catalyst_counts.get(ct, 0) + 1
        dominant_catalyst = max(catalyst_counts, key=catalyst_counts.get)
        
        # Determine impact (most severe wins)
        impact_severity = {
            MarketImpact.VERY_BEARISH: -2,
            MarketImpact.BEARISH: -1,
            MarketImpact.NEUTRAL: 0,
            MarketImpact.BULLISH: 1,
            MarketImpact.VERY_BULLISH: 2
        }
        
        # Check for context modifiers
        bullish_count = sum(1 for m in self.bullish_modifiers if m in text_lower)
        bearish_count = sum(1 for m in self.bearish_modifiers if m in text_lower)
        
        # Adjust impact based on context
        avg_impact = sum(impact_severity[i] for i in impacts) / len(impacts)
        modifier_adjustment = (bullish_count - bearish_count) * 0.3
        final_impact_score = avg_impact + modifier_adjustment
        
        # Map back to MarketImpact
        if final_impact_score <= -1.5:
            final_impact = MarketImpact.VERY_BEARISH
        elif final_impact_score <= -0.3:
            final_impact = MarketImpact.BEARISH
        elif final_impact_score >= 1.5:
            final_impact = MarketImpact.VERY_BULLISH
        elif final_impact_score >= 0.3:
            final_impact = MarketImpact.BULLISH
        else:
            final_impact = MarketImpact.NEUTRAL
        
        # Confidence based on keyword count and clarity
        confidence = min(0.9, 0.3 + (len(matched_keywords) * 0.15))
        
        return matched_keywords, dominant_catalyst, final_impact, list(all_symbols), confidence


class TrumpScenarioEngine:
    """Proactive scenario planning for Trump events"""
    
    def __init__(self):
        self.active_scenarios: List[TrumpScenario] = []
        self._load_default_scenarios()
    
    def _load_default_scenarios(self):
        """Load default high-probability scenarios"""
        now = datetime.now()
        
        default_scenarios = [
            TrumpScenario(
                scenario_id="tariff_china_deadline",
                description="China tariff deadline approaching - expect escalation or deal",
                trigger_conditions=["china", "tariff", "deadline"],
                probability=0.7,
                if_bullish={"action": "LONG", "symbols": ["SPY", "FXI", "QQQ"], "note": "Deal reached = rally"},
                if_bearish={"action": "SHORT", "symbols": ["SPY", "QQQ"], "note": "Tariffs implemented = selloff"},
                preparation_actions=["Monitor Truth Social", "Size position for 2% move", "Have both long/short orders ready"],
                expiry=now + timedelta(days=30)
            ),
            TrumpScenario(
                scenario_id="fed_meeting_trump_reaction",
                description="Fed meeting upcoming - Trump likely to comment on rates",
                trigger_conditions=["fed", "fomc", "rate decision"],
                probability=0.6,
                if_bullish={"action": "LONG", "symbols": ["TLT", "XLF"], "note": "Dovish = risk on"},
                if_bearish={"action": "LONG", "symbols": ["GLD", "TLT"], "note": "Hawkish = safe havens"},
                preparation_actions=["Watch for pre-meeting tweets", "Monitor bond market", "Check gold positioning"],
                expiry=now + timedelta(days=14)
            ),
            TrumpScenario(
                scenario_id="weekend_tweet_storm",
                description="Weekend approaching - high probability of market-moving tweets",
                trigger_conditions=["saturday", "sunday", "weekend"],
                probability=0.5,
                if_bullish={"action": "LONG", "symbols": ["SPY"], "note": "Positive news = gap up Monday"},
                if_bearish={"action": "SHORT", "symbols": ["SPY"], "note": "Tariff threats = gap down Monday"},
                preparation_actions=["Monitor Truth Social all weekend", "Have Monday gap plays ready", "Check VIX futures Sunday night"],
                expiry=now + timedelta(days=7)
            ),
            TrumpScenario(
                scenario_id="geopolitical_escalation",
                description="Geopolitical tensions rising - Trump may escalate or de-escalate",
                trigger_conditions=["russia", "ukraine", "iran", "israel", "war"],
                probability=0.4,
                if_bullish={"action": "LONG", "symbols": ["SPY", "ITA"], "note": "De-escalation = risk on"},
                if_bearish={"action": "LONG", "symbols": ["USO", "GLD", "VIX"], "note": "Escalation = safe havens, oil"},
                preparation_actions=["Monitor defense stocks", "Watch oil prices", "Check VIX level"],
                expiry=now + timedelta(days=30)
            ),
            TrumpScenario(
                scenario_id="tech_regulation_threat",
                description="Big tech under scrutiny - Trump may attack specific companies",
                trigger_conditions=["big tech", "antitrust", "amazon", "google", "facebook", "apple"],
                probability=0.3,
                if_bullish={"action": "LONG", "symbols": ["QQQ"], "note": "No action = relief rally"},
                if_bearish={"action": "SHORT", "symbols": ["QQQ", "META", "GOOGL"], "note": "Regulation = tech selloff"},
                preparation_actions=["Monitor company-specific tweets", "Watch for DOJ/FTC news", "Size for sector rotation"],
                expiry=now + timedelta(days=60)
            ),
        ]
        
        self.active_scenarios = default_scenarios
    
    def get_active_scenarios(self) -> List[TrumpScenario]:
        """Get all active scenarios that haven't expired"""
        now = datetime.now()
        return [s for s in self.active_scenarios if s.expiry > now]
    
    def check_scenario_triggers(self, text: str) -> List[TrumpScenario]:
        """Check if any scenarios are triggered by the text"""
        text_lower = text.lower()
        triggered = []
        
        for scenario in self.get_active_scenarios():
            matches = sum(1 for t in scenario.trigger_conditions if t in text_lower)
            if matches >= 2 or (matches == 1 and len(scenario.trigger_conditions) == 1):
                triggered.append(scenario)
        
        return triggered
    
    def generate_preparation_alert(self, scenario: TrumpScenario) -> str:
        """Generate a preparation alert for a scenario"""
        alert = f"""
🎯 TRUMP SCENARIO ALERT: {scenario.description}

📊 Probability: {scenario.probability:.0%}
⏰ Expires: {scenario.expiry.strftime('%Y-%m-%d')}

IF BULLISH:
  Action: {scenario.if_bullish['action']} {', '.join(scenario.if_bullish['symbols'])}
  Note: {scenario.if_bullish['note']}

IF BEARISH:
  Action: {scenario.if_bearish['action']} {', '.join(scenario.if_bearish['symbols'])}
  Note: {scenario.if_bearish['note']}

📝 PREPARATION ACTIONS:
{chr(10).join(f'  • {action}' for action in scenario.preparation_actions)}
"""
        return alert


class TrumpIntelligenceEngine:
    """
    Main Trump Intelligence Engine
    Combines keyword analysis, scenario planning, and news monitoring
    """
    
    def __init__(self, perplexity_api_key: Optional[str] = None):
        self.keyword_engine = TrumpKeywordEngine()
        self.scenario_engine = TrumpScenarioEngine()
        self.perplexity_key = perplexity_api_key or os.getenv('PERPLEXITY_API_KEY')
        self.recent_events: List[TrumpEvent] = []
    
    def fetch_trump_news(self, hours: int = 6) -> List[Dict]:
        """Fetch recent Trump-related news using Perplexity"""
        if not self.perplexity_key:
            logger.warning("No Perplexity API key - using fallback news sources")
            return self._fallback_trump_news()
        
        try:
            headers = {
                "Authorization": f"Bearer {self.perplexity_key}",
                "Content-Type": "application/json"
            }
            
            payload = {
                "model": "llama-3.1-sonar-small-128k-online",
                "messages": [
                    {
                        "role": "system",
                        "content": "You are a financial news analyst. Provide factual, recent news about Trump's statements, policies, or actions that could affect financial markets. Focus on tariffs, trade, Fed comments, company mentions, and geopolitical statements."
                    },
                    {
                        "role": "user",
                        "content": f"What are the most recent market-moving Trump news, statements, or Truth Social posts from the last {hours} hours? Focus on tariffs, China, Fed, companies, and policy. Be specific with quotes if available."
                    }
                ],
                "max_tokens": 1500,
                "temperature": 0.1
            }
            
            response = requests.post(
                "https://api.perplexity.ai/chat/completions",
                headers=headers,
                json=payload,
                timeout=30
            )
            
            if response.status_code == 200:
                result = response.json()
                content = result.get('choices', [{}])[0].get('message', {}).get('content', '')
                
                return [{
                    "source": "perplexity",
                    "content": content,
                    "timestamp": datetime.now().isoformat(),
                    "type": "trump_news_summary"
                }]
            else:
                logger.error(f"Perplexity API error: {response.status_code}")
                return self._fallback_trump_news()
                
        except Exception as e:
            logger.error(f"Error fetching Trump news: {e}")
            return self._fallback_trump_news()
    
    def _fallback_trump_news(self) -> List[Dict]:
        """Fallback when Perplexity is not available"""
        # Use RSS feeds for Trump news
        import feedparser
        
        feeds = [
            "https://news.google.com/rss/search?q=trump+tariff&hl=en-US&gl=US&ceid=US:en",
            "https://news.google.com/rss/search?q=trump+market&hl=en-US&gl=US&ceid=US:en",
        ]
        
        articles = []
        for feed_url in feeds:
            try:
                feed = feedparser.parse(feed_url)
                for entry in feed.entries[:5]:
                    articles.append({
                        "source": "google_news",
                        "title": entry.get('title', ''),
                        "content": entry.get('summary', entry.get('title', '')),
                        "link": entry.get('link', ''),
                        "timestamp": entry.get('published', datetime.now().isoformat())
                    })
            except Exception as e:
                logger.warning(f"Error fetching RSS: {e}")
        
        return articles
    
    def analyze_for_trump_signals(self, news_items: List[Dict]) -> List[TrumpEvent]:
        """Analyze news items for Trump market signals"""
        events = []
        
        for item in news_items:
            content = item.get('content', '') or item.get('title', '')
            if not content:
                continue
            
            # Analyze keywords
            keywords, catalyst_type, impact, symbols, confidence = self.keyword_engine.analyze(content)
            
            if not keywords or confidence < 0.3:
                continue
            
            # Check scenarios
            triggered_scenarios = self.scenario_engine.check_scenario_triggers(content)
            
            # Generate trade recommendation
            trade_rec = self._generate_trade_recommendation(catalyst_type, impact, symbols, triggered_scenarios)
            
            # Determine urgency
            if impact in [MarketImpact.VERY_BEARISH, MarketImpact.VERY_BULLISH]:
                urgency = "immediate"
            elif len(keywords) >= 3:
                urgency = "immediate"
            elif triggered_scenarios:
                urgency = "prepare"
            else:
                urgency = "watch"
            
            event = TrumpEvent(
                timestamp=datetime.now(),
                source=item.get('source', 'unknown'),
                content=content[:500],  # Truncate long content
                catalyst_type=catalyst_type,
                keywords_matched=keywords,
                expected_impact=impact,
                confidence=confidence,
                affected_symbols=symbols,
                trade_recommendation=trade_rec,
                urgency=urgency
            )
            
            events.append(event)
        
        self.recent_events = events
        return events
    
    def _generate_trade_recommendation(self, catalyst: TrumpCatalystType, impact: MarketImpact, 
                                       symbols: List[str], scenarios: List[TrumpScenario]) -> str:
        """Generate actionable trade recommendation"""
        
        if impact == MarketImpact.VERY_BEARISH:
            return f"🔴 AGGRESSIVE SHORT: {', '.join(symbols[:3])} | Consider VIX calls | Stop above today's high"
        elif impact == MarketImpact.BEARISH:
            return f"🟠 SHORT BIAS: {', '.join(symbols[:3])} | Wait for bounce to short | Tight stops"
        elif impact == MarketImpact.VERY_BULLISH:
            return f"🟢 AGGRESSIVE LONG: {', '.join(symbols[:3])} | Buy the dip | Stop below today's low"
        elif impact == MarketImpact.BULLISH:
            return f"🟢 LONG BIAS: {', '.join(symbols[:3])} | Look for pullback entry | Scale in"
        else:
            if scenarios:
                return f"⚡ SCENARIO ACTIVE: Prepare for {scenarios[0].description[:50]}... | Have both sides ready"
            return f"👀 WATCH: {', '.join(symbols[:3])} | No clear direction yet | Wait for confirmation"
    
    def get_proactive_alerts(self) -> List[str]:
        """Get proactive preparation alerts based on active scenarios"""
        alerts = []
        
        for scenario in self.scenario_engine.get_active_scenarios():
            if scenario.probability >= 0.5:  # Only high probability scenarios
                alerts.append(self.scenario_engine.generate_preparation_alert(scenario))
        
        return alerts
    
    def generate_trump_briefing(self) -> str:
        """Generate a comprehensive Trump intelligence briefing"""
        # Fetch latest news
        news = self.fetch_trump_news(hours=12)
        
        # Analyze for signals
        events = self.analyze_for_trump_signals(news)
        
        # Get active scenarios
        scenarios = self.scenario_engine.get_active_scenarios()
        
        briefing = """
╔══════════════════════════════════════════════════════════════════╗
║              🎯 TRUMP INTELLIGENCE BRIEFING                       ║
║              Generated: {timestamp}                               ║
╚══════════════════════════════════════════════════════════════════╝

📡 RECENT TRUMP SIGNALS ({num_events} detected)
══════════════════════════════════════════════════════════════════
""".format(timestamp=datetime.now().strftime('%Y-%m-%d %H:%M'), num_events=len(events))
        
        if events:
            for i, event in enumerate(events[:5], 1):
                impact_emoji = {
                    MarketImpact.VERY_BEARISH: "🔴🔴",
                    MarketImpact.BEARISH: "🔴",
                    MarketImpact.NEUTRAL: "⚪",
                    MarketImpact.BULLISH: "🟢",
                    MarketImpact.VERY_BULLISH: "🟢🟢"
                }.get(event.expected_impact, "⚪")
                
                briefing += f"""
{i}. {impact_emoji} {event.catalyst_type.value.upper()}
   Keywords: {', '.join(event.keywords_matched[:5])}
   Impact: {event.expected_impact.value}
   Confidence: {event.confidence:.0%}
   Symbols: {', '.join(event.affected_symbols[:5])}
   Urgency: {event.urgency.upper()}
   
   📝 {event.trade_recommendation}
"""
        else:
            briefing += "\n   No significant Trump signals detected in recent news.\n"
        
        briefing += """
🎯 ACTIVE SCENARIOS (Prepare for these)
══════════════════════════════════════════════════════════════════
"""
        
        for scenario in scenarios[:3]:
            briefing += f"""
• {scenario.description}
  Probability: {scenario.probability:.0%}
  IF BULLISH → {scenario.if_bullish['action']} {', '.join(scenario.if_bullish['symbols'])}
  IF BEARISH → {scenario.if_bearish['action']} {', '.join(scenario.if_bearish['symbols'])}
"""
        
        briefing += """
══════════════════════════════════════════════════════════════════
💡 PROACTIVE POSITIONING:
   • Monitor Truth Social (especially 6-8 AM ET, late night)
   • Weekend = Monday gap risk
   • Have both long/short orders prepared
   • Size for 2% moves on major catalysts
══════════════════════════════════════════════════════════════════
"""
        
        return briefing


def _demo():
    """Demo the Trump Intelligence Engine"""
    logging.basicConfig(level=logging.INFO, format='%(message)s')
    
    print("=" * 70)
    print("🎯 TRUMP INTELLIGENCE ENGINE - DEMO")
    print("=" * 70)
    
    engine = TrumpIntelligenceEngine()
    
    # Generate briefing
    briefing = engine.generate_trump_briefing()
    print(briefing)
    
    # Test keyword analysis on sample text
    test_texts = [
        "Trump threatens 25% tariff on China if they don't make a deal",
        "President says Powell is doing a terrible job with interest rates",
        "Trump announces beautiful trade deal with Mexico",
        "Military options on the table for Iran, says Trump"
    ]
    
    print("\n" + "=" * 70)
    print("🧪 KEYWORD ANALYSIS TEST")
    print("=" * 70)
    
    for text in test_texts:
        keywords, catalyst, impact, symbols, conf = engine.keyword_engine.analyze(text)
        print(f"\n📝 \"{text[:60]}...\"")
        print(f"   Keywords: {keywords}")
        print(f"   Catalyst: {catalyst.value}")
        print(f"   Impact: {impact.value}")
        print(f"   Symbols: {symbols}")
        print(f"   Confidence: {conf:.0%}")


if __name__ == "__main__":
    _demo()




