#!/usr/bin/env python3
"""
SLACK ALERTER - Send alerts to Slack
- Webhook integration
- Formatted messages
"""

import requests
import json
import sys
from pathlib import Path

sys.path.append(str(Path(__file__).parent.parent / 'core'))
from signal_generator import LiveSignal

class SlackAlerter:
    """Send alerts to Slack via webhook"""
    
    def __init__(self, webhook_url: str, channel: str = "#trading-signals",
                 username: str = "Signal Bot"):
        self.webhook_url = webhook_url
        self.channel = channel
        self.username = username
        self.enabled = bool(webhook_url)
        
        if not self.enabled:
            print("⚠️  Slack webhook not configured - Slack alerts disabled")
    
    def alert_signal(self, signal: LiveSignal):
        """Send signal to Slack"""
        if not self.enabled:
            return
        
        try:
            # Build message
            emoji = "🎯" if signal.is_master_signal else "📊"
            color = "#36a64f" if signal.action == "BUY" else "#ff0000"
            
            message = {
                "channel": self.channel,
                "username": self.username,
                "icon_emoji": ":chart_with_upwards_trend:",
                "attachments": [
                    {
                        "color": color,
                        "title": f"{emoji} {'MASTER' if signal.is_master_signal else 'HIGH CONFIDENCE'} SIGNAL: {signal.symbol}",
                        "fields": [
                            {
                                "title": "Action",
                                "value": f"*{signal.action}* {signal.signal_type}",
                                "short": True
                            },
                            {
                                "title": "Confidence",
                                "value": f"{signal.confidence:.0%}",
                                "short": True
                            },
                            {
                                "title": "Entry",
                                "value": f"${signal.entry_price:.2f}",
                                "short": True
                            },
                            {
                                "title": "Stop / Target",
                                "value": f"${signal.stop_loss:.2f} / ${signal.take_profit:.2f}",
                                "short": True
                            },
                            {
                                "title": "Risk/Reward",
                                "value": f"1:{signal.risk_reward_ratio:.1f}",
                                "short": True
                            },
                            {
                                "title": "Position Size",
                                "value": f"{signal.position_size_pct:.1%}",
                                "short": True
                            },
                            {
                                "title": "Reasoning",
                                "value": signal.primary_reason,
                                "short": False
                            }
                        ],
                        "footer": f"Institutional Score: {signal.institutional_score:.0%}",
                        "ts": int(signal.timestamp.timestamp())
                    }
                ]
            }
            
            response = requests.post(self.webhook_url, json=message, timeout=5)
            response.raise_for_status()
            
        except Exception as e:
            print(f"Error sending to Slack: {e}")
    
    def alert_info(self, message: str):
        """Send info message"""
        if not self.enabled:
            return
        self._send_simple("ℹ️", message, "#3498db")
    
    def alert_warning(self, message: str):
        """Send warning"""
        if not self.enabled:
            return
        self._send_simple("⚠️", message, "#f39c12")
    
    def alert_error(self, message: str):
        """Send error"""
        if not self.enabled:
            return
        self._send_simple("❌", message, "#e74c3c")
    
    def _send_simple(self, emoji: str, message: str, color: str):
        """Send simple message"""
        try:
            payload = {
                "channel": self.channel,
                "username": self.username,
                "text": f"{emoji} {message}",
                "color": color
            }
            requests.post(self.webhook_url, json=payload, timeout=5)
        except Exception as e:
            print(f"Error sending to Slack: {e}")



