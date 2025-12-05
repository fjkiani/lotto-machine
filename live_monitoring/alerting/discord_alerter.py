#!/usr/bin/env python3
"""
DISCORD ALERTER - Send alerts to Discord
- Webhook integration
- Rich embeds with colors
- Formatted messages
"""

import requests
import json
import sys
from pathlib import Path
from datetime import datetime

sys.path.append(str(Path(__file__).parent.parent / 'core'))
from signal_generator import LiveSignal

class DiscordAlerter:
    """Send alerts to Discord via webhook"""
    
    def __init__(self, webhook_url: str, username: str = "Alpha Intelligence"):
        self.webhook_url = webhook_url
        self.username = username
        self.enabled = bool(webhook_url)
        
        if not self.enabled:
            print("⚠️  Discord webhook not configured - Discord alerts disabled")
    
    def alert_signal(self, signal: LiveSignal):
        """Send signal to Discord"""
        if not self.enabled:
            return
        
        try:
            # Determine color and emoji
            if signal.is_master_signal:
                color = 0x00ff00  # Green for master signals
                emoji = "🎯"
                title_prefix = "MASTER SIGNAL"
            else:
                color = 0x3498db  # Blue for high confidence
                emoji = "📊"
                title_prefix = "HIGH CONFIDENCE SIGNAL"
            
            # Calculate R/R
            risk = abs(signal.entry_price - signal.stop_price)
            reward = abs(signal.target_price - signal.entry_price)
            rr_ratio = reward / risk if risk > 0 else 0
            
            # Handle enum types
            action_str = signal.action.value if hasattr(signal.action, 'value') else str(signal.action)
            signal_type_str = signal.signal_type.value if hasattr(signal.signal_type, 'value') else str(signal.signal_type)
            
            # Build embed
            embed = {
                "title": f"{emoji} {title_prefix}: {signal.symbol}",
                "color": color,
                "timestamp": signal.timestamp.isoformat(),
                "fields": [
                    {
                        "name": "Action",
                        "value": f"**{action_str}** {signal_type_str}",
                        "inline": True
                    },
                    {
                        "name": "Confidence",
                        "value": f"**{signal.confidence:.0%}**",
                        "inline": True
                    },
                    {
                        "name": "Entry Price",
                        "value": f"${signal.entry_price:.2f}",
                        "inline": True
                    },
                    {
                        "name": "Stop Loss",
                        "value": f"${signal.stop_price:.2f}",
                        "inline": True
                    },
                    {
                        "name": "Take Profit",
                        "value": f"${signal.target_price:.2f}",
                        "inline": True
                    },
                    {
                        "name": "Risk/Reward",
                        "value": f"**1:{rr_ratio:.1f}**",
                        "inline": True
                    },
                    {
                        "name": "Signal Type",
                        "value": signal_type_str,
                        "inline": True
                    },
                    {
                        "name": "Reasoning",
                        "value": signal.rationale[:1000] if len(signal.rationale) > 1000 else signal.rationale,
                        "inline": False
                    }
                ],
                "footer": {
                    "text": f"Alpha Intelligence • {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
                }
            }
            
            # Add supporting factors if available
            if hasattr(signal, 'supporting_factors') and signal.supporting_factors:
                factors_text = "\n".join([f"• {factor}" for factor in signal.supporting_factors[:5]])
                embed["fields"].append({
                    "name": "Supporting Factors",
                    "value": factors_text[:1024],
                    "inline": False
                })
            
            payload = {
                "username": self.username,
                "embeds": [embed]
            }
            
            response = requests.post(self.webhook_url, json=payload, timeout=10)
            response.raise_for_status()
            
        except Exception as e:
            print(f"❌ Error sending to Discord: {e}")
    
    def alert_info(self, message: str):
        """Send info message"""
        if not self.enabled:
            return
        self._send_simple("ℹ️", message, 0x3498db)
    
    def alert_warning(self, message: str):
        """Send warning"""
        if not self.enabled:
            return
        self._send_simple("⚠️", message, 0xf39c12)
    
    def alert_error(self, message: str):
        """Send error"""
        if not self.enabled:
            return
        self._send_simple("❌", message, 0xe74c3c)
    
    def _send_simple(self, emoji: str, message: str, color: int):
        """Send simple message"""
        try:
            embed = {
                "description": f"{emoji} {message}",
                "color": color,
                "timestamp": datetime.now().isoformat(),
                "footer": {
                    "text": "Alpha Intelligence"
                }
            }
            
            payload = {
                "username": self.username,
                "embeds": [embed]
            }
            
            requests.post(self.webhook_url, json=payload, timeout=10)
        except Exception as e:
            print(f"❌ Error sending to Discord: {e}")

