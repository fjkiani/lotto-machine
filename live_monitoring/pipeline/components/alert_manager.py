"""
Alert Manager - Alert Routing & Formatting

Responsibility: Format synthesis results and send to Discord/console/CSV.
No hardcoded formatting - clean separation!
"""

import logging
import requests
from typing import Optional
from datetime import datetime

from .synthesis_engine import SynthesisResult

logger = logging.getLogger(__name__)


class AlertManager:
    """
    Manages alert routing and formatting.
    
    Before: Alert logic mixed with synthesis
    After: Clean alert formatting, testable independently
    """
    
    def __init__(
        self,
        discord_webhook: Optional[str] = None,
        console_enabled: bool = True,
        csv_enabled: bool = True
    ):
        """
        Initialize Alert Manager.
        
        Args:
            discord_webhook: Discord webhook URL
            console_enabled: Enable console output
            csv_enabled: Enable CSV logging
        """
        self.discord_webhook = discord_webhook
        self.console_enabled = console_enabled
        self.csv_enabled = csv_enabled
        
        logger.info(f"📤 AlertManager initialized (Discord: {'✅' if discord_webhook else '❌'})")
    
    def send_synthesis_alert(self, result: SynthesisResult, prices: dict) -> bool:
        """
        Send synthesis result as alert.
        
        Args:
            result: SynthesisResult from SynthesisEngine
            prices: Current prices dict
        
        Returns:
            True if sent successfully
        """
        # Format message
        message = self._format_synthesis_message(result, prices)
        
        # Send to all channels
        success = True
        
        if self.console_enabled:
            self._send_console(message)
        
        if self.discord_webhook:
            if not self._send_discord(message):
                success = False
        
        if self.csv_enabled:
            self._send_csv(result, prices)
        
        return success
    
    def _format_synthesis_message(self, result: SynthesisResult, prices: dict) -> str:
        """Format synthesis result for Discord"""
        # Determine color
        color = 0x00ff00 if result.direction == 'BULLISH' else 0xff0000 if result.direction == 'BEARISH' else 0x808080
        
        # Build embed
        embed = {
            "title": f"🧠 UNIFIED MARKET SYNTHESIS | {int(result.confluence_score * 100)}% {result.direction}",
            "color": color,
            "fields": [
                {
                    "name": "📊 Confluence",
                    "value": f"{result.confluence_score:.0%}",
                    "inline": True
                },
                {
                    "name": "💡 Action",
                    "value": result.action,
                    "inline": True
                },
                {
                    "name": "🔗 Components",
                    "value": f"DP: {result.dp_score:.2f} | Cross: {result.cross_asset_score:.2f} | Macro: {result.macro_score:.2f}",
                    "inline": False
                },
                {
                    "name": "💭 Reasoning",
                    "value": result.reasoning,
                    "inline": False
                }
            ],
            "timestamp": datetime.utcnow().isoformat()
        }
        
        # Add price info
        price_text = " | ".join([f"{sym} ${prices.get(sym, 0):.2f}" for sym in prices.keys()])
        embed["fields"].append({
            "name": "💰 Prices",
            "value": price_text,
            "inline": False
        })
        
        return embed
    
    def _send_console(self, message: dict):
        """Send to console"""
        print("\n" + "=" * 70)
        print(f"🧠 {message['title']}")
        for field in message['fields']:
            print(f"   {field['name']}: {field['value']}")
        print("=" * 70 + "\n")
    
    def _send_discord(self, embed: dict) -> bool:
        """Send to Discord webhook"""
        if not self.discord_webhook:
            return False
        
        try:
            payload = {"embeds": [embed]}
            response = requests.post(self.discord_webhook, json=payload, timeout=5)
            response.raise_for_status()
            logger.info("   ✅ Alert sent to Discord")
            return True
        except Exception as e:
            logger.error(f"   ❌ Discord alert failed: {e}")
            return False
    
    def _send_csv(self, result: SynthesisResult, prices: dict):
        """Log to CSV"""
        try:
            import csv
            from pathlib import Path
            
            csv_file = Path("logs/live_monitoring/signals.csv")
            csv_file.parent.mkdir(parents=True, exist_ok=True)
            
            file_exists = csv_file.exists()
            
            with open(csv_file, 'a', newline='') as f:
                writer = csv.writer(f)
                
                if not file_exists:
                    writer.writerow([
                        'timestamp', 'confluence', 'direction', 'action', 
                        'dp_score', 'cross_score', 'macro_score', 'prices'
                    ])
                
                writer.writerow([
                    datetime.now().isoformat(),
                    result.confluence_score,
                    result.direction,
                    result.action,
                    result.dp_score,
                    result.cross_asset_score,
                    result.macro_score,
                    str(prices)
                ])
            
            logger.debug("   ✅ Alert logged to CSV")
        except Exception as e:
            logger.error(f"   ⚠️ CSV logging failed: {e}")


