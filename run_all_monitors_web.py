#!/usr/bin/env python3
"""
🎯 ALPHA INTELLIGENCE - WEB SERVICE VERSION (FREE TIER!)

Wraps run_all_monitors.py in a FastAPI web server so it stays awake on Render free tier.

Features:
- HTTP health check endpoint
- Background monitoring loop
- Self-pinging to prevent sleep (every 10 minutes)
- All monitors run in parallel

Usage:
    python3 run_all_monitors_web.py

Environment Variables:
    DISCORD_WEBHOOK_URL - Discord webhook (required)
    PERPLEXITY_API_KEY - For news/Trump intelligence
    CHARTEXCHANGE_API_KEY - For dark pool data
    FRED_API_KEY - For economic data
    PORT - Port for web server (Render sets automatically)
"""

import os
import sys
import time
import logging
import threading
import requests
from datetime import datetime, timezone
from pathlib import Path
from http.server import HTTPServer, BaseHTTPRequestHandler
import json

# Add paths
base_path = Path(__file__).parent
sys.path.insert(0, str(base_path))

# Setup logging early for import debugging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s | %(levelname)s | %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)

# Initialize Tradytics Ecosystem
logger.info("🔍 Initializing Tradytics Ecosystem...")
try:
    from tradytics_agents import (
        OptionsSweepsAgent, DarkpoolAgent, TradyticsSynthesisEngine
    )
    tradytics_agents = {
        'options_sweeps': OptionsSweepsAgent(),
        'darkpool': DarkpoolAgent()
    }
    synthesis_engine = TradyticsSynthesisEngine()
    logger.info("   ✅ Tradytics Ecosystem initialized with specialized agents")
    tradytics_available = True
except Exception as e:
    logger.error(f"   ❌ Tradytics Ecosystem failed: {e}")
    tradytics_agents = {}
    synthesis_engine = None
    tradytics_available = False

# Discord bot DISABLED - Render compatibility issues
logger.info("🔍 Discord bot status...")
logger.info("   ❌ DISABLED: discord.py incompatible with Render free tier (audioop dependency)")
logger.info("   ✅ AUTONOMOUS TRADYTICS: Full ecosystem with specialized agents")
logger.info("   ✅ SYNTHESIS ENGINE: Combines all feed intelligence")
logger.info("   ✅ DISCORD ALERTS: Webhook delivery of synthesized insights")
discord_available = False


# Global instances
monitor = None
discord_bot = None


def run_monitors():
    """Run the unified monitor in background thread."""
    global monitor
    
    try:
        from run_all_monitors import UnifiedAlphaMonitor
        
        logger.info("🚀 Starting Unified Alpha Monitor...")
        monitor = UnifiedAlphaMonitor()
        monitor.run()
        
    except Exception as e:
        logger.error(f"❌ Monitor error: {e}")
        import traceback
        logger.error(traceback.format_exc())


def self_ping():
    """
    Self-ping to keep Render free tier awake.

    Pings the health endpoint every 10 minutes to prevent sleep.
    """
    port = int(os.getenv('PORT', 8000))
    url = f"http://localhost:{port}/health"

    while True:
        try:
            time.sleep(600)  # Every 10 minutes
            response = requests.get(url, timeout=5)
            if response.status_code == 200:
                logger.debug("✅ Self-ping successful (keeping service awake)")
            else:
                logger.warning(f"⚠️ Self-ping returned {response.status_code}")
        except Exception as e:
            logger.debug(f"Self-ping error: {e}")


def run_discord_bot():
    """Run Discord bot in background thread"""
    global discord_bot

    logger.info("🔍 Checking Discord bot availability...")
    logger.info(f"   discord_available: {discord_available}")

    if not discord_available:
        logger.error("❌ CRITICAL: Discord bot import failed!")
        logger.error("   Check if discord.py is installed and import path is correct")
        logger.error("   Run: pip install discord.py>=2.3.0")
        return

    try:
        logger.info("🤖 Initializing Alpha Intelligence Bot...")
        discord_bot = AlphaIntelligenceBot()

        # Check token before running
        token = os.getenv("DISCORD_BOT_TOKEN")
        if not token:
            logger.error("❌ CRITICAL: DISCORD_BOT_TOKEN not found in environment!")
            logger.error("   Set DISCORD_BOT_TOKEN in Render environment variables")
            return

        logger.info(f"🤖 Bot token found (length: {len(token)})")
        logger.info("🤖 Starting Discord bot connection...")

        # This will block the thread until bot stops
        discord_bot.run(token)

    except Exception as e:
        logger.error(f"❌ FATAL: Discord bot crashed: {e}")
        import traceback
        logger.error("Full traceback:")
        logger.error(traceback.format_exc())


class HealthHandler(BaseHTTPRequestHandler):
    """HTTP handler for health checks and status."""
    
    def do_GET(self):
        global monitor
        
        if self.path == '/health' or self.path == '/':
            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.end_headers()
            
            status = {
                "status": "running",
                "service": "alpha-intelligence-monitor",
                "timestamp": datetime.now().isoformat(),
                "monitor_running": monitor is not None and monitor.running if monitor else False,
            }
            
            # Add monitor stats if available
            if monitor:
                try:
                    status["fed_enabled"] = getattr(monitor, 'fed_enabled', False)
                    status["trump_enabled"] = getattr(monitor, 'trump_enabled', False)
                    status["econ_enabled"] = getattr(monitor, 'econ_enabled', False)
                    status["last_fed_check"] = str(monitor.last_fed_check) if monitor.last_fed_check else None
                    status["last_econ_check"] = str(monitor.last_econ_check) if monitor.last_econ_check else None
                except:
                    pass
            
            self.wfile.write(json.dumps(status, indent=2).encode())

    def do_POST(self):
        """Handle POST requests (webhooks)"""
        global monitor

        if self.path == '/tradytics-webhook' or self.path == '/tradytics-forward':
            try:
                # Read the request body
                content_length = int(self.headers.get('Content-Length', 0))
                if content_length == 0:
                    logger.warning("⚠️ Empty request body received")
                    self.send_response(400)
                    self.send_header('Content-type', 'application/json')
                    self.end_headers()
                    self.wfile.write(json.dumps({"error": "Empty request body"}).encode())
                    return

                post_data = self.rfile.read(content_length)
                webhook_data = json.loads(post_data.decode('utf-8'))

                logger.info(f"📥 Received Tradytics webhook at {self.path}: {json.dumps(webhook_data)[:200]}...")

                # Convert Discord webhook format to our analysis format
                # Tradytics might send different formats - handle all cases
                analysis_payload = {
                    'content': '',
                    'author': {'username': 'TradyticsBot'},
                    'timestamp': datetime.now().isoformat()
                }

                # Try to extract content from various possible formats
                if 'embeds' in webhook_data and webhook_data['embeds']:
                    # Handle Discord embed format
                    embed = webhook_data['embeds'][0]
                    analysis_payload['content'] = (
                        embed.get('description', '') or 
                        embed.get('title', '') or 
                        embed.get('fields', [{}])[0].get('value', '') if embed.get('fields') else ''
                    )
                    analysis_payload['author']['username'] = webhook_data.get('username', embed.get('author', {}).get('name', 'TradyticsBot'))
                elif 'content' in webhook_data:
                    # Handle simple message format
                    analysis_payload['content'] = webhook_data.get('content', '')
                    analysis_payload['author']['username'] = webhook_data.get('username', 'TradyticsBot')
                elif 'message' in webhook_data:
                    # Handle nested message format
                    message = webhook_data['message']
                    analysis_payload['content'] = message.get('content', str(message))
                    analysis_payload['author']['username'] = message.get('author', {}).get('username', 'TradyticsBot')
                elif 'text' in webhook_data or 'alert' in webhook_data:
                    # Handle custom Tradytics format
                    analysis_payload['content'] = webhook_data.get('text', webhook_data.get('alert', str(webhook_data)))
                    analysis_payload['author']['username'] = webhook_data.get('bot_name', webhook_data.get('source', 'TradyticsBot'))
                else:
                    # Fallback: try to extract any text content
                    analysis_payload['content'] = str(webhook_data)
                    analysis_payload['author']['username'] = webhook_data.get('username', webhook_data.get('bot', 'TradyticsBot'))

                # If still no content, use the whole payload as string
                if not analysis_payload['content'] or analysis_payload['content'] == '{}':
                    analysis_payload['content'] = json.dumps(webhook_data, indent=2)

                logger.info(f"📊 Parsed alert content: {analysis_payload['content'][:100]}...")

                # First, forward the original message to Discord (for /tradytics-forward)
                if self.path == '/tradytics-forward':
                    discord_webhook_url = os.getenv('DISCORD_WEBHOOK_URL')
                    if discord_webhook_url:
                        try:
                            bot_name = analysis_payload['author']['username']
                            emoji_map = {
                                'Bullseye': '🎯',
                                'Darkpool': '🔒',
                                'Spidey': '🕷️',
                                'Captain': '⚓',
                                'default': '📡'
                            }
                            emoji = emoji_map.get(bot_name.split()[0], emoji_map['default'])

                            forward_payload = {
                                "content": f"{emoji} **TRADYTICS ALERT** | {bot_name}\n{analysis_payload['content']}",
                                "username": "Tradytics Forwarder"
                            }

                            forward_response = requests.post(discord_webhook_url, json=forward_payload, timeout=5)
                            if forward_response.status_code == 204:
                                logger.info(f"✅ Forwarded {bot_name} alert to Discord")
                            else:
                                logger.warning(f"⚠️ Discord forward failed: {forward_response.status_code} - {forward_response.text}")
                        except Exception as e:
                            logger.error(f"❌ Discord forwarding error: {e}")

                # Process with Tradytics Ecosystem
                if tradytics_available and synthesis_engine:
                    # Determine agent based on content
                    agent = self._select_tradytics_agent(analysis_payload)
                    logger.info(f"🤖 Selected agent: {agent.agent_name if agent else 'None'}")

                    if agent:
                        # Process with specialized agent
                        result = agent.process_alert(analysis_payload['content'])
                        logger.info(f"📊 Agent processing result: success={result.get('success')}, confidence={result.get('analysis', {}).get('confidence', 0):.1%}")

                        if result['success']:
                            # Add to synthesis engine
                            synthesis_result = synthesis_engine.add_signal(result)
                            logger.info(f"🧠 Synthesis generated: direction={synthesis_result.get('market_synthesis', {}).get('overall_direction', 'unknown')}")

                            # Send comprehensive analysis to Discord
                            self._send_synthesized_analysis(synthesis_result)

                            self.send_response(200)
                            self.send_header('Content-type', 'application/json')
                            self.end_headers()
                            self.wfile.write(json.dumps({
                                "status": "processed",
                                "agent": result['agent'],
                                "synthesis_generated": True,
                                "result": result
                            }).encode())
                        else:
                            logger.error(f"❌ Agent processing failed: {result.get('error', 'Unknown error')}")
                            self.send_response(400)
                            self.send_header('Content-type', 'application/json')
                            self.end_headers()
                            self.wfile.write(json.dumps({"error": "Analysis failed", "details": result}).encode())
                    else:
                        logger.warning("⚠️ No suitable agent found for alert")
                        self.send_response(400)
                        self.send_header('Content-type', 'application/json')
                        self.end_headers()
                        self.wfile.write(json.dumps({"error": "No suitable agent found for alert"}).encode())
                else:
                    logger.error("❌ Tradytics ecosystem not available")
                    self.send_response(503)
                    self.send_header('Content-type', 'application/json')
                    self.end_headers()
                    self.wfile.write(json.dumps({"error": "Tradytics system not available"}).encode())

            except json.JSONDecodeError as e:
                logger.error(f"❌ JSON decode error: {e}")
                self.send_response(400)
                self.send_header('Content-type', 'application/json')
                self.end_headers()
                self.wfile.write(json.dumps({"error": f"Invalid JSON: {str(e)}"}).encode())
            except Exception as e:
                logger.error(f"❌ Webhook processing error: {e}")
                import traceback
                logger.error(f"Traceback: {traceback.format_exc()}")
                self.send_response(500)
                self.send_header('Content-type', 'application/json')
                self.end_headers()
                self.wfile.write(json.dumps({"error": str(e)}).encode())

        else:
            self.send_response(404)
            self.send_header('Content-type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps({"error": "Endpoint not found"}).encode())

    def _select_tradytics_agent(self, analysis_payload):
        """Select appropriate Tradytics agent based on content"""
        content = analysis_payload.get('content', '').upper()
        bot_name = analysis_payload.get('author', {}).get('username', '').upper()

        logger.info(f"🔍 Selecting agent for content: {content[:100]}... (bot: {bot_name})")

        # Route based on bot name first (more reliable)
        if 'BULLSEYE' in bot_name or 'BULLS' in bot_name:
            # Bullseye sends trade ideas - use options agent
            logger.info("   → Routing to OptionsSweepsAgent (Bullseye bot)")
            return tradytics_agents.get('options_sweeps')
        elif 'DARKPOOL' in bot_name:
            logger.info("   → Routing to DarkpoolAgent (Darkpool bot)")
            return tradytics_agents.get('darkpool')
        elif 'SPIDEY' in bot_name:
            # Spidey sends options sweeps and analyst grades
            if 'SWEEP' in content or 'CALL' in content or 'PUT' in content:
                logger.info("   → Routing to OptionsSweepsAgent (Spidey - options)")
                return tradytics_agents.get('options_sweeps')
            elif 'ANALYST' in content or 'GRADE' in content:
                # Would use AnalystGradesAgent when implemented
                logger.info("   → Routing to OptionsSweepsAgent (Spidey - analyst, fallback)")
                return tradytics_agents.get('options_sweeps')
            else:
                logger.info("   → Routing to OptionsSweepsAgent (Spidey - default)")
                return tradytics_agents.get('options_sweeps')
        elif 'CAPTAIN' in bot_name or 'HOOK' in bot_name:
            # Captain Hook sends Trady Flow
            logger.info("   → Routing to OptionsSweepsAgent (Captain Hook - trady flow)")
            return tradytics_agents.get('options_sweeps')

        # Route based on content keywords
        if 'CALL' in content or 'PUT' in content or 'SWEEP' in content or 'OPTIONS' in content or 'GOLDEN' in content:
            logger.info("   → Routing to OptionsSweepsAgent (content keywords)")
            return tradytics_agents.get('options_sweeps')
        elif 'BLOCK' in content or 'DARKPOOL' in content or 'DARK POOL' in content or 'DARKPOOL SIGNAL' in content:
            logger.info("   → Routing to DarkpoolAgent (content keywords)")
            return tradytics_agents.get('darkpool')
        else:
            # Default to first available agent
            default_agent = next(iter(tradytics_agents.values()), None)
            logger.info(f"   → Routing to default agent: {default_agent.agent_name if default_agent else 'None'}")
            return default_agent

    def _send_synthesized_analysis(self, synthesis_result):
        """Send comprehensive analysis to Discord"""
        try:
            market_synthesis = synthesis_result.get('market_synthesis', {})
            overall_direction = market_synthesis.get('overall_direction', 'neutral')
            confidence = market_synthesis.get('overall_confidence', 0.5)

            # Create comprehensive Discord message
            embed = {
                "title": f"🧠 **SYNTHESIZED INTELLIGENCE** | {overall_direction.upper()}",
                "description": f"**Market Direction:** {overall_direction} ({confidence:.1%} confidence)\n**Signal Count:** {market_synthesis.get('signal_count', 0)}\n\n**Key Themes:** {', '.join(market_synthesis.get('market_themes', []))}",
                "color": 0x00ff00 if overall_direction == 'bullish' else 0xff0000 if overall_direction == 'bearish' else 0xffff00,
                "fields": [],
                "footer": {"text": "Tradytics Synthesis Engine | Real-time Intelligence"}
            }

            # Add key symbols
            key_symbols = market_synthesis.get('key_symbols', [])
            if key_symbols:
                symbol_text = "\n".join([f"**{s['symbol']}**: {s['direction']} ({s['strength']:.1%})" for s in key_symbols[:3]])
                embed["fields"].append({
                    "name": "🎯 Key Symbols",
                    "value": symbol_text,
                    "inline": True
                })

            # Add risk assessment
            risk = market_synthesis.get('risk_assessment', {})
            embed["fields"].append({
                "name": "⚠️ Risk Level",
                "value": f"**{risk.get('level', 'unknown').upper()}**\n{risk.get('rationale', '')}",
                "inline": True
            })

            # Send to Discord
            discord_webhook_url = os.getenv('DISCORD_WEBHOOK_URL')
            if discord_webhook_url:
                payload = {"embeds": [embed]}
                response = requests.post(discord_webhook_url, json=payload, timeout=10)
                if response.status_code == 204:
                    logger.info("✅ Synthesized analysis sent to Discord")
                else:
                    logger.warning(f"⚠️ Discord synthesis send failed: {response.status_code}")

        except Exception as e:
            logger.error(f"❌ Synthesis send error: {e}")

    def do_GET(self):
        global monitor

        if self.path == '/tradytics-forward':
            # Tradytics forwarding endpoint info - GET request
            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.end_headers()

            info = {
                "endpoint": "POST /tradytics-forward",
                "description": "Forward Discord webhooks to autonomous analysis",
                "webhook_url": f"https://{self.headers.get('Host', 'lotto-machine.onrender.com')}/tradytics-forward",
                "purpose": "Use this URL in place of Discord webhook URLs to get autonomous analysis",
                "how_it_works": [
                    "Discord webhook sends message to THIS URL instead of Discord",
                    "We analyze the message with savage LLM",
                    "We forward the analyzed message to your Discord channel",
                    "Result: Every alert gets instant institutional analysis"
                ],
                "discord_webhook_format": "Compatible with standard Discord webhook payloads",
                "status": "active",
                "note": "This endpoint accepts POST requests. Use POST method for webhook forwarding."
            }
            self.wfile.write(json.dumps(info, indent=2).encode())

        elif self.path == '/tradytics-webhook':
            # Tradytics webhook endpoint info - GET request
            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.end_headers()

            info = {
                "endpoint": "POST /tradytics-webhook",
                "description": "Receive Tradytics alerts for autonomous savage analysis",
                "webhook_url": f"https://{self.headers.get('Host', 'lotto-machine.onrender.com')}/tradytics-webhook",
                "expected_format": {
                    "content": "Alert message text (e.g., 'Bullseye: NVDA $950 CALL SWEEP - $2.3M PREMIUM')",
                    "author": {"username": "BotName (e.g., 'Bullseye', 'Darkpool')"},
                    "timestamp": "ISO timestamp (optional)"
                },
                "example_payload": {
                    "content": "Bullseye: NVDA $950 CALL SWEEP - $2.3M PREMIUM - Institutional buying detected",
                    "author": {"username": "Bullseye"},
                    "timestamp": "2025-12-07T06:00:00.000Z"
                },
                "how_to_use": [
                    "Configure your Tradytics webhook to POST to this URL",
                    "Or use Zapier/Make.com to forward Tradytics Discord messages",
                    "Every alert will get instant savage LLM analysis",
                    "Results posted back to your Discord channel"
                ],
                "status": "active",
                "last_processed": getattr(monitor, 'last_tradytics_analysis', None) if monitor else None
            }
            self.wfile.write(json.dumps(info, indent=2).encode())

        elif self.path == '/tradytics-forward':
            # Tradytics forwarding endpoint info - GET request
            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.end_headers()

            info = {
                "endpoint": "POST /tradytics-forward",
                "description": "Forward Discord webhooks to autonomous analysis",
                "webhook_url": f"https://{self.headers.get('Host', 'lotto-machine.onrender.com')}/tradytics-forward",
                "purpose": "Use this URL in place of Discord webhook URLs to get autonomous analysis",
                "how_it_works": [
                    "Discord webhook sends message to THIS URL instead of Discord",
                    "We analyze the message with savage LLM",
                    "We forward the analyzed message to your Discord channel",
                    "Result: Every alert gets instant institutional analysis"
                ],
                "discord_webhook_format": "Compatible with standard Discord webhook payloads",
                "status": "active"
            }
            self.wfile.write(json.dumps(info, indent=2).encode())

        elif self.path == '/webhook-debug':
            # Debug endpoint to check webhook configuration
            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.end_headers()

            debug_info = {
                "webhook_endpoints": {
                    "/tradytics-forward": "POST - Main forwarding endpoint (use this)",
                    "/tradytics-webhook": "POST - Direct webhook endpoint",
                    "/webhook-debug": "GET - This debug endpoint"
                },
                "configuration": {
                    "discord_webhook_url_set": bool(os.getenv('DISCORD_WEBHOOK_URL')),
                    "tradytics_ecosystem_available": tradytics_available,
                    "agents_loaded": len(tradytics_agents) if tradytics_available else 0,
                    "synthesis_engine_ready": synthesis_engine is not None if tradytics_available else False
                },
                "instructions": {
                    "step_1": "Replace all Tradytics webhook URLs with: https://lotto-machine.onrender.com/tradytics-forward",
                    "step_2": "Check Render logs for '📥 Received Tradytics webhook' messages",
                    "step_3": "Verify DISCORD_WEBHOOK_URL environment variable is set",
                    "step_4": "Test with: curl -X POST https://lotto-machine.onrender.com/tradytics-forward -H 'Content-Type: application/json' -d '{\"content\":\"Test alert\",\"username\":\"TestBot\"}'"
                },
                "troubleshooting": {
                    "no_alerts_received": "Check if Tradytics webhook URLs were actually changed",
                    "alerts_received_but_no_discord": "Check DISCORD_WEBHOOK_URL environment variable",
                    "analysis_failed": "Check Render logs for agent processing errors",
                    "check_logs": "Go to Render Dashboard → Logs tab → Look for '📥 Received Tradytics webhook'"
                }
            }
            self.wfile.write(json.dumps(debug_info, indent=2).encode())

        elif self.path == '/test-tradytics':
            # Test endpoint to verify Tradytics ecosystem works
            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.end_headers()

            test_results = {
                "test_status": "running",
                "timestamp": datetime.now().isoformat(),
                "tradytics_ecosystem": {
                    "available": tradytics_available,
                    "agents_loaded": len(tradytics_agents) if tradytics_available else 0,
                    "synthesis_engine": synthesis_engine is not None if tradytics_available else False
                },
                "test_alert": None,
                "test_result": None
            }

            # Run a test alert if ecosystem is available
            if tradytics_available and tradytics_agents:
                try:
                    # Test with sample options sweep alert
                    test_alert = "Bullseye: NVDA $950 CALL SWEEP - $2.3M PREMIUM - Institutional buying detected"
                    test_results["test_alert"] = test_alert

                    # Process with options agent
                    options_agent = tradytics_agents.get('options_sweeps')
                    if options_agent:
                        result = options_agent.process_alert(test_alert)
                        test_results["test_result"] = {
                            "success": result.get('success', False),
                            "agent": result.get('agent', 'unknown'),
                            "confidence": result.get('analysis', {}).get('confidence', 0),
                            "symbols": result.get('parsed_data', {}).get('symbols', []),
                            "recommendation": result.get('analysis', {}).get('recommendation', {})
                        }

                        # Test synthesis if available
                        if synthesis_engine:
                            synthesis = synthesis_engine.add_signal(result)
                            test_results["synthesis_test"] = {
                                "success": True,
                                "market_direction": synthesis.get('market_synthesis', {}).get('overall_direction', 'unknown'),
                                "confidence": synthesis.get('market_synthesis', {}).get('overall_confidence', 0)
                            }
                except Exception as e:
                    test_results["test_error"] = str(e)

            self.wfile.write(json.dumps(test_results, indent=2).encode())

        elif self.path == '/status':
            # Detailed status
            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.end_headers()
            
            status = {
                "service": "alpha-intelligence-monitor",
                "timestamp": datetime.now().isoformat(),
                "monitor": {
                    "running": monitor is not None and monitor.running if monitor else False,
                    "fed_enabled": getattr(monitor, 'fed_enabled', False) if monitor else False,
                    "trump_enabled": getattr(monitor, 'trump_enabled', False) if monitor else False,
                    "econ_enabled": getattr(monitor, 'econ_enabled', False) if monitor else False,
                },
                "environment": {
                    "discord_webhook": "✅" if os.getenv('DISCORD_WEBHOOK_URL') else "❌",
                    "perplexity_key": "✅" if os.getenv('PERPLEXITY_API_KEY') else "❌",
                    "chartexchange_key": "✅" if os.getenv('CHARTEXCHANGE_API_KEY') else "❌",
                    "fred_key": "✅" if os.getenv('FRED_API_KEY') else "❌",
                }
            }
            
            self.wfile.write(json.dumps(status, indent=2).encode())
            
        else:
            self.send_response(404)
            self.end_headers()
    
    def log_message(self, format, *args):
        # Suppress default logging
        pass


def main():
    """Main entry point."""
    global monitor
    
    print("=" * 80)
    print("🎯 ALPHA INTELLIGENCE - UNIFIED MONITOR (WEB SERVICE)")
    print("=" * 80)
    print("✅ This is run_all_monitors_web.py - Unified monitor with:")
    print("   🏦 Fed Watch Monitor")
    print("   🎯 Trump Intelligence")
    print("   📊 Economic Calendar + Learning Engine")
    print("=" * 80)
    
    logger.info("=" * 70)
    logger.info("🌐 ALPHA INTELLIGENCE - WEB SERVICE STARTING")
    logger.info("=" * 70)
    
    # Check environment variables
    discord_webhook = os.getenv('DISCORD_WEBHOOK_URL')
    if not discord_webhook:
        logger.error("❌ DISCORD_WEBHOOK_URL not set!")
        logger.error("   Set it in Render dashboard: Environment → Add Environment Variable")
        sys.exit(1)
    
    logger.info("✅ Environment variables:")
    logger.info(f"   Discord: {'✅' if discord_webhook else '❌'}")
    logger.info(f"   Perplexity: {'✅' if os.getenv('PERPLEXITY_API_KEY') else '❌'}")
    logger.info(f"   ChartExchange: {'✅' if os.getenv('CHARTEXCHANGE_API_KEY') else '❌'}")
    logger.info(f"   FRED: {'✅' if os.getenv('FRED_API_KEY') else '❌'}")
    
    # Send test Discord message to verify webhook works
    logger.info("📤 Sending test Discord message...")
    test_embed = {
        "title": "🧪 TEST ALERT - Unified Monitor Starting",
        "color": 3447003,
        "description": "If you see this, Discord webhook is working!",
        "fields": [
            {"name": "Service", "value": "alpha-intelligence-monitor", "inline": True},
            {"name": "Script", "value": "run_all_monitors_web.py", "inline": True},
            {"name": "Status", "value": "✅ Starting", "inline": True},
        ],
        "footer": {"text": "This is a test message to verify Discord integration"},
        "timestamp": datetime.now(timezone.utc).isoformat()
    }
    
    try:
        import requests
        webhook = os.getenv('DISCORD_WEBHOOK_URL')
        if webhook:
            response = requests.post(webhook, json={"embeds": [test_embed]}, timeout=10)
            if response.status_code in [200, 204]:
                logger.info("   ✅ Test Discord message sent successfully!")
            else:
                logger.error(f"   ❌ Test Discord failed: {response.status_code} - {response.text[:200]}")
        else:
            logger.error("   ❌ DISCORD_WEBHOOK_URL not set!")
    except Exception as e:
        logger.error(f"   ❌ Test Discord error: {e}")
    
    # Start monitor in background thread
    monitor_thread = threading.Thread(target=run_monitors, daemon=True)
    monitor_thread.start()
    logger.info("   ✅ Monitor thread started")
    
    # Start self-ping thread (keeps service awake on free tier)
    ping_thread = threading.Thread(target=self_ping, daemon=True)
    ping_thread.start()
    logger.info("   ✅ Self-ping thread started (pings every 10 min)")

    # Start Discord bot thread
    if discord_available:
        discord_thread = threading.Thread(target=run_discord_bot, daemon=True)
        discord_thread.start()
        logger.info("   ✅ Discord bot thread started")
    else:
        logger.error("   ❌ CRITICAL: Discord bot DISABLED - discord.py not available")
        logger.error("   ❌ This means the savage LLM Discord bot is not running!")
        logger.error("   ❌ Check Render logs for discord.py installation errors")
        logger.error("   ❌ Manual fix: Run 'pip install discord.py>=2.3.0' in Render shell")

    # Start HTTP server
    port = int(os.getenv('PORT', 8000))
    server = HTTPServer(('0.0.0.0', port), HealthHandler)
    
    logger.info(f"   ✅ HTTP server on port {port}")
    logger.info(f"   Health: http://localhost:{port}/health")
    logger.info(f"   Status: http://localhost:{port}/status")
    logger.info("=" * 70)
    logger.info("🚀 ALL SYSTEMS RUNNING!")
    logger.info("=" * 70)
    
    try:
        # Run server (blocks)
        server.serve_forever()
    except KeyboardInterrupt:
        logger.info("\n⚠️ Shutting down...")
        if monitor:
            monitor.running = False
        sys.exit(0)
    except Exception as e:
        logger.error(f"❌ Fatal error: {e}")
        import traceback
        logger.error(traceback.format_exc())
        sys.exit(1)


if __name__ == "__main__":
    main()

