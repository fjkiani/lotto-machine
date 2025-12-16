"""
Tradytics Checker - Analyzes Tradytics bot alerts using LLM.

Extracted from unified_monitor.py for modularity.

This checker processes Tradytics webhook alerts and generates
savage LLM-powered analysis of options flow and block trades.
"""

import logging
import hashlib
import re
from datetime import datetime
from typing import List, Optional, Dict, Any

from .base_checker import BaseChecker, CheckerAlert

logger = logging.getLogger(__name__)


class TradyticsChecker(BaseChecker):
    """
    Checks Tradytics alerts and generates savage LLM analysis.
    
    Responsibilities:
    - Process Tradytics webhook alerts
    - Analyze alerts using LLM (savage mode)
    - Classify alert types (options, blocks, flow)
    - Extract symbols from alert content
    - Deduplicate alerts using hash-based tracking
    """
    
    def __init__(
        self,
        alert_manager,
        tradytics_llm_available=False,
        tradytics_analysis_interval=300,
        unified_mode=False
    ):
        """
        Initialize Tradytics checker.
        
        Args:
            alert_manager: AlertManager instance for deduplication
            tradytics_llm_available: Whether LLM analysis is available
            tradytics_analysis_interval: Interval between analyses (seconds)
            unified_mode: If True, suppresses individual alerts
        """
        super().__init__(alert_manager, unified_mode)
        self.tradytics_llm_available = tradytics_llm_available
        self.tradytics_analysis_interval = tradytics_analysis_interval
        
        # State management
        self.seen_tradytics_alerts = set()
        self.tradytics_alerts_processed = 0
    
    def check(self) -> List[CheckerAlert]:
        """
        Run autonomous Tradytics analysis.
        
        Returns:
            List of CheckerAlert objects (empty if no alerts)
        """
        if not self.tradytics_llm_available:
            return []
        
        try:
            logger.info("🤖 Running Autonomous Tradytics Analysis...")
            sample_alerts = self._generate_sample_tradytics_alerts()
            
            alerts = []
            for alert in sample_alerts:
                alert_hash = hashlib.md5(f"{alert['content']}:{alert['bot_name']}".encode()).hexdigest()[:12]
                if alert_hash in self.seen_tradytics_alerts:
                    logger.debug(f"   📊 Tradytics alert duplicate (hash: {alert_hash[:8]}) - skipping")
                    continue
                
                self.seen_tradytics_alerts.add(alert_hash)
                if len(self.seen_tradytics_alerts) > 50:
                    self.seen_tradytics_alerts = set(list(self.seen_tradytics_alerts)[-50:])
                
                analysis = self._analyze_tradytics_alert(alert)
                if analysis and "Analysis failed" not in analysis:
                    alert_obj = self._create_analysis_alert(alert, analysis)
                    if alert_obj:
                        alerts.append(alert_obj)
                        self.tradytics_alerts_processed += 1
            
            if sample_alerts:
                logger.info(f"   ✅ Processed {len(sample_alerts)} autonomous Tradytics analyses")
            
            return alerts
                
        except Exception as e:
            logger.error(f"   ❌ Autonomous Tradytics analysis error: {e}")
            return []
    
    def process_webhook(self, webhook_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Process incoming Tradytics webhook data.
        
        Args:
            webhook_data: Webhook data dictionary
            
        Returns:
            Dictionary with status and processing result
        """
        try:
            logger.info(f"🔗 Processing Tradytics webhook: {webhook_data}")
            
            if 'content' not in webhook_data:
                return {"status": "invalid_format", "alert_processed": False}
            
            message_content = webhook_data['content']
            author = webhook_data.get('author', {}).get('username', 'Unknown')
            
            tradytics_keywords = ['SWEEP', 'BLOCK', 'CALL', 'PUT', 'PREMIUM', 'VOLUME', 'FLOW']
            if not any(keyword in message_content.upper() for keyword in tradytics_keywords):
                return {"status": "not_tradytics_alert", "alert_processed": False}
            
            logger.info(f"🎯 Detected Tradytics alert from {author}: {message_content[:100]}...")
            
            alert = {
                'bot_name': author,
                'alert_type': self._classify_alert_type(message_content),
                'content': message_content,
                'symbols': self._extract_symbols(message_content),
                'timestamp': webhook_data.get('timestamp', datetime.now().isoformat()),
                'confidence': 0.8,
                'source': 'webhook'
            }
            
            analysis = self._analyze_tradytics_alert(alert)
            if analysis:
                alert_obj = self._create_analysis_alert(alert, analysis)
                if alert_obj:
                    # Return alert for orchestrator to send
                    return {
                        "status": "analyzed",
                        "alert_processed": True,
                        "analysis": analysis[:200],
                        "alert": alert_obj
                    }
                else:
                    return {"status": "analysis_failed", "alert_processed": False}
            else:
                return {"status": "analysis_failed", "alert_processed": False}
                
        except Exception as e:
            logger.error(f"❌ Webhook processing error: {e}")
            return {"status": "error", "error": str(e)}
    
    def _generate_sample_tradytics_alerts(self) -> List[Dict[str, Any]]:
        """Generate sample Tradytics alerts for demonstration"""
        # DISABLED: Sample alerts were causing spam
        return []
    
    def _analyze_tradytics_alert(self, alert: Dict[str, Any]) -> Optional[str]:
        """Analyze a Tradytics alert using savage LLM"""
        try:
            savage_prompt = f"""
            🔥 **SAVAGE TRADYTICS ANALYSIS - GODLIKE MODE** 🔥

            Tradytics Bot: {alert['bot_name']}
            Alert Type: {alert['alert_type']}
            Symbols: {', '.join(alert.get('symbols', []))}
            Raw Alert: {alert['content']}

            **YOUR MISSION AS A RUTHLESS ALPHA PREDATOR:**
            Analyze this Tradytics alert like the market's most brutal hunter. What does this REALLY fucking mean? Is this a BUY signal, SELL signal, or RUN-FOR-YOUR-LIFE signal? Connect the institutional dots. Be savage, be precise, be profitable.

            **ALPHA WARRIOR RULES:**
            - NO MARKET BULLSHIT - Cut the crap
            - Tell REAL traders what this means RIGHT NOW
            - If the signal is weak, FUCKING SAY IT'S WEAK
            - If it's strong, EXPLAIN WHY YOU'D BET YOUR HOUSE ON IT
            - Give ACTIONABLE insight, not pussy predictions
            - Think like a hedge fund killer, not a retail chump

            **SAVAGE INSTITUTIONAL ANALYSIS:**
            """
            
            try:
                from src.data.llm_api import query_llm
                response = query_llm(savage_prompt, provider="gemini")
            except (ImportError, NameError):
                logger.warning("   ⚠️ query_llm not available - skipping analysis")
                return f"Analysis unavailable: query_llm not found"
            
            if isinstance(response, dict):
                analysis = (response.get('detailed_analysis') or
                           response.get('market_sentiment') or
                           str(response))
                if isinstance(analysis, str) and len(analysis) > 50:
                    return analysis
                else:
                    return f"Savage Analysis: {analysis}"
            else:
                return str(response)
                
        except Exception as e:
            logger.error(f"   ❌ Tradytics alert analysis error: {e}")
            return f"Analysis failed: {str(e)}"
    
    def _classify_alert_type(self, content: str) -> str:
        """Classify the type of Tradytics alert"""
        content_upper = content.upper()
        if 'SWEEP' in content_upper:
            return 'options_signal'
        elif 'BLOCK' in content_upper:
            return 'block_trade'
        elif 'FLOW' in content_upper:
            return 'volume_flow'
        elif any(word in content_upper for word in ['CALL', 'PUT']):
            return 'options_signal'
        else:
            return 'market_signal'
    
    def _extract_symbols(self, content: str) -> List[str]:
        """Extract stock symbols from alert content"""
        symbols = re.findall(r'\b[A-Z]{1,5}\b', content)
        exclude_words = ['A', 'I', 'ON', 'AT', 'IN', 'IS', 'IT', 'TO', 'OF', 'BY', 'OR', 'AS', 'AN', 'BE', 'DO', 'FOR', 'IF', 'NO', 'SO', 'UP', 'US', 'WE', 'YES']
        filtered_symbols = [s for s in symbols if s not in exclude_words and len(s) >= 2]
        return list(set(filtered_symbols))
    
    def _create_analysis_alert(self, alert: Dict[str, Any], analysis: str) -> Optional[CheckerAlert]:
        """Create a CheckerAlert from Tradytics analysis"""
        try:
            if not analysis or "Analysis failed" in analysis or "unavailable" in analysis.lower():
                logger.debug(f"   ⏭️  Skipping Tradytics alert - analysis failed or unavailable")
                return None
            
            embed = {
                "title": f"🧠 **SAVAGE ANALYSIS** - {alert['bot_name']} Alert",
                "description": f"**Alert:** {alert['content']}\n\n{analysis}",
                "color": 0xff0000,
                "timestamp": alert['timestamp'],
                "footer": {"text": "Alpha Intelligence | Autonomous Tradytics Integration"}
            }
            
            content = f"🧠 **AUTONOMOUS ANALYSIS** | {alert['bot_name']} detected significant activity"
            symbols = ",".join(alert.get('symbols', [])) if alert.get('symbols') else None
            
            return CheckerAlert(
                embed=embed,
                content=content,
                alert_type="tradytics",
                source="tradytics_checker",
                symbol=symbols
            )
            
        except Exception as e:
            logger.error(f"   ❌ Create Tradytics alert error: {e}")
            return None

