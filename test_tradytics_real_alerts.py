#!/usr/bin/env python3
"""
🧪 REAL TRADYTICS ALERT TESTING
Tests with actual alert formats from your Discord channel
"""

import sys
import json
from datetime import datetime

# Add paths
sys.path.insert(0, '.')

def test_darkpool_alerts():
    """Test Darkpool agent with real SPY alerts"""
    print("=" * 70)
    print("🔒 TEST 1: DARKPOOL ALERTS")
    print("=" * 70)
    
    from tradytics_agents import DarkpoolAgent
    
    agent = DarkpoolAgent()
    
    # Real darkpool alerts from your Discord
    alerts = [
        "SPY Darkpool Signal - Large Darkpool Activity - Price: 685.831 - Shares: 1.4M - Amount: 960.16M",
        "SPY Darkpool Signal - Large Darkpool Activity - Price: 685.831 - Shares: 887.04K - Amount: 608.36M",
        "SPY Darkpool Signal - Large Darkpool Activity - Price: 685.831 - Shares: 1.13M - Amount: 775.51M"
    ]
    
    for i, alert in enumerate(alerts, 1):
        print(f"\n📥 Alert {i}: {alert[:60]}...")
        result = agent.process_alert(alert)
        
        if result['success']:
            analysis = result['analysis']
            rec = analysis['recommendation']
            
            print(f"✅ Parsed Successfully")
            print(f"   Symbol: {result['parsed_data']['symbols']}")
            print(f"   Trade Size: ${result['parsed_data'].get('trade_size', 0)/1_000_000:.2f}M")
            print(f"   Direction: {analysis.get('institutional_bias', 'neutral')}")
            print(f"   Confidence: {analysis['confidence']:.1%}")
            print(f"   Signal Strength: {analysis['signal_strength']}")
            print(f"   Recommendation: {rec['action']} - {rec['rationale']}")
        else:
            print(f"❌ Failed: {result.get('error', 'Unknown error')}")

def test_bullseye_alerts():
    """Test Bullseye agent with real trade ideas"""
    print("\n" + "=" * 70)
    print("🎯 TEST 2: BULLSEYE TRADE IDEAS")
    print("=" * 70)
    
    from tradytics_agents import BaseTradyticsAgent
    
    # Create a simple agent for Bullseye (we'll enhance this)
    class BullseyeAgent(BaseTradyticsAgent):
        def __init__(self):
            super().__init__("BullseyeAgent", "bullseye")
        
        def parse_alert(self, alert_text):
            return {'alert_type': 'bullseye_trade_idea'}
        
        def analyze_signal(self, parsed_data):
            return {'signal_strength': 'medium', 'direction': 'bullish'}
        
        def _calculate_agent_confidence(self, signal_data):
            return 0.65
    
    agent = BullseyeAgent()
    
    alerts = [
        "Bullseye Trade Idea - Symbol: VALE - Strike: 12.0 - Expiration: 3/20/2026 - Call/Put: Call - AI Confidence: 62.72% - Prems Spent: 919.33K - Volume: 7665 - OI: 113003",
        "Bullseye Trade Idea - Symbol: ETHA - Strike: 25.0 - Expiration: 1/16/2026 - Call/Put: Call - AI Confidence: 68.89% - Prems Spent: 199.18K - Volume: 1397 - OI: 12992",
        "Bullseye Trade Idea - Symbol: HIMS - Strike: 40.0 - Expiration: 12/12/2025 - Call/Put: Call - AI Confidence: 55.71% - Prems Spent: 357.9K - Volume: 2247 - OI: 4803"
    ]
    
    for i, alert in enumerate(alerts, 1):
        print(f"\n📥 Alert {i}: {alert[:60]}...")
        result = agent.process_alert(alert)
        
        if result['success']:
            print(f"✅ Parsed Successfully")
            print(f"   Symbols: {result['parsed_data']['symbols']}")
            print(f"   Confidence: {result['analysis']['confidence']:.1%}")
        else:
            print(f"❌ Failed: {result.get('error', 'Unknown error')}")

def test_options_sweeps():
    """Test Options Sweeps agent with real golden sweeps"""
    print("\n" + "=" * 70)
    print("⚡ TEST 3: OPTIONS GOLDEN SWEEPS")
    print("=" * 70)
    
    from tradytics_agents import OptionsSweepsAgent
    
    agent = OptionsSweepsAgent()
    
    alerts = [
        "Options Golden Sweep - Put Golden Sweep - Symbol: GOOG - Strike: 315.0 - Expiration: 1/16/2026 - Premiums: 1.13M",
        "Options Golden Sweep - Call Golden Sweep - Symbol: SLV - Strike: 60.0 - Expiration: 6/18/2026 - Premiums: 1.06M",
        "Options Golden Sweep - Call Golden Sweep - Symbol: GOOGL - Strike: 335.0 - Expiration: 8/21/2026 - Premiums: 1.81M",
        "Options Golden Sweep - Call Golden Sweep - Symbol: MSTR - Strike: 180.0 - Expiration: 1/2/2026 - Premiums: 1.51M"
    ]
    
    for i, alert in enumerate(alerts, 1):
        print(f"\n📥 Alert {i}: {alert[:60]}...")
        result = agent.process_alert(alert)
        
        if result['success']:
            analysis = result['analysis']
            rec = analysis['recommendation']
            
            print(f"✅ Parsed Successfully")
            print(f"   Symbol: {result['parsed_data']['symbols']}")
            print(f"   Option Type: {result['parsed_data'].get('option_type', 'unknown')}")
            print(f"   Strike: ${result['parsed_data'].get('strike_price', 0):.2f}")
            print(f"   Premium: ${result['parsed_data'].get('premium', 0)/1_000_000:.2f}M")
            print(f"   GEX Impact: {analysis.get('gex_impact', 'unknown')}")
            print(f"   Confidence: {analysis['confidence']:.1%}")
            print(f"   Recommendation: {rec['action']}")
        else:
            print(f"❌ Failed: {result.get('error', 'Unknown error')}")

def test_analyst_grades():
    """Test Analyst Grades parsing"""
    print("\n" + "=" * 70)
    print("📊 TEST 4: ANALYST GRADES")
    print("=" * 70)
    
    from tradytics_agents import BaseTradyticsAgent
    
    class AnalystGradesAgent(BaseTradyticsAgent):
        def __init__(self):
            super().__init__("AnalystGradesAgent", "analyst_grades")
        
        def parse_alert(self, alert_text):
            import re
            parsed = {'grades': []}
            
            # Extract symbol
            symbol_match = re.search(r'Analyst Grades for (\w+)', alert_text)
            if symbol_match:
                parsed['symbol'] = symbol_match.group(1)
            
            # Extract grade changes
            grade_pattern = r'Company: (\w+).*?From Grade: (\w+).*?To Grade: (\w+).*?Action: (\w+)'
            grades = re.findall(grade_pattern, alert_text, re.DOTALL)
            
            for grade in grades:
                parsed['grades'].append({
                    'company': grade[0],
                    'from': grade[1],
                    'to': grade[2],
                    'action': grade[3]
                })
            
            return parsed
        
        def analyze_signal(self, parsed_data):
            grades = parsed_data.get('grades', [])
            upgrades = sum(1 for g in grades if g['action'] == 'Up')
            downgrades = sum(1 for g in grades if g['action'] == 'Down')
            
            if upgrades > downgrades:
                direction = 'bullish'
            elif downgrades > upgrades:
                direction = 'bearish'
            else:
                direction = 'neutral'
            
            return {
                'direction': direction,
                'upgrade_count': upgrades,
                'downgrade_count': downgrades,
                'total_grades': len(grades)
            }
        
        def _calculate_agent_confidence(self, signal_data):
            grades = signal_data.get('grades', [])
            if len(grades) >= 5:
                return 0.8
            elif len(grades) >= 3:
                return 0.6
            else:
                return 0.4
    
    agent = AnalystGradesAgent()
    
    alerts = [
        "Analyst Grades for ULTA - Latest analyst grades - Grade # 1: Company: UBS - From Grade: Buy - To Grade: Buy - Action: Main - Grade # 2: Company: Evercore ISI Group - From Grade: Outperform - To Grade: Outperform - Action: Main - Grade # 3: Company: Oppenheimer - From Grade: Outperform - To Grade: Outperform - Action: Main",
        "Analyst Grades for VRTX - Latest analyst grades - Grade # 1: Company: Morgan Stanley - From Grade: Equal-Weight - To Grade: Overweight - Action: Up"
    ]
    
    for i, alert in enumerate(alerts, 1):
        print(f"\n📥 Alert {i}: {alert[:60]}...")
        result = agent.process_alert(alert)
        
        if result['success']:
            analysis = result['analysis']
            print(f"✅ Parsed Successfully")
            print(f"   Symbol: {result['parsed_data'].get('symbol', 'unknown')}")
            print(f"   Total Grades: {analysis.get('total_grades', 0)}")
            print(f"   Upgrades: {analysis.get('upgrade_count', 0)}")
            print(f"   Direction: {analysis['direction']}")
            print(f"   Confidence: {result['analysis']['confidence']:.1%}")
        else:
            print(f"❌ Failed: {result.get('error', 'Unknown error')}")

def test_trady_flow():
    """Test Trady Flow alerts"""
    print("\n" + "=" * 70)
    print("📊 TEST 5: TRADY FLOW")
    print("=" * 70)
    
    from tradytics_agents import BaseTradyticsAgent
    
    class TradyFlowAgent(BaseTradyticsAgent):
        def __init__(self):
            super().__init__("TradyFlowAgent", "trady_flow")
        
        def parse_alert(self, alert_text):
            import re
            parsed = {}
            
            # Extract symbol
            symbol_match = re.search(r'Symbol\s+(\w+)', alert_text)
            if symbol_match:
                parsed['symbol'] = symbol_match.group(1)
            
            # Extract call/put
            if 'CALL' in alert_text.upper():
                parsed['option_type'] = 'call'
            elif 'PUT' in alert_text.upper():
                parsed['option_type'] = 'put'
            
            # Extract premiums
            prem_match = re.search(r'Total Prems:\s*([\d.]+)([MK])', alert_text)
            if prem_match:
                value = float(prem_match.group(1))
                unit = prem_match.group(2)
                parsed['premiums'] = value * (1_000_000 if unit == 'M' else 1_000)
            
            return parsed
        
        def analyze_signal(self, parsed_data):
            premiums = parsed_data.get('premiums', 0)
            direction = 'bullish' if parsed_data.get('option_type') == 'call' else 'bearish'
            
            return {
                'direction': direction,
                'signal_strength': 'strong' if premiums > 1_000_000 else 'medium',
                'institutional_flow': 'high' if premiums > 2_000_000 else 'moderate'
            }
        
        def _calculate_agent_confidence(self, signal_data):
            premiums = signal_data.get('numbers', {}).get('volume', 0)
            if premiums > 2_000_000:
                return 0.8
            elif premiums > 1_000_000:
                return 0.65
            else:
                return 0.5
    
    agent = TradyFlowAgent()
    
    alerts = [
        "Trady flow for INTC - Symbol: INTC - Orders Today: 16 - Call/Put: CALL - Strike: 45.0 - Expiration: 2/20/2026 - Total Prems: 2.35M - Total Vol: 6.96K",
        "Trady flow for S - Symbol: S - Orders Today: 6 - Call/Put: CALL - Strike: 18.0 - Expiration: 6/18/2026 - Total Prems: 1.1M - Total Vol: 7.98K",
        "Trady flow for C - Symbol: C - Orders Today: 6 - Call/Put: PUT - Strike: 108.0 - Expiration: 12/12/2025 - Total Prems: 714.53K - Total Vol: 5.73K"
    ]
    
    for i, alert in enumerate(alerts, 1):
        print(f"\n📥 Alert {i}: {alert[:60]}...")
        result = agent.process_alert(alert)
        
        if result['success']:
            analysis = result['analysis']
            print(f"✅ Parsed Successfully")
            print(f"   Symbol: {result['parsed_data'].get('symbol', 'unknown')}")
            print(f"   Option Type: {result['parsed_data'].get('option_type', 'unknown')}")
            print(f"   Premiums: ${result['parsed_data'].get('premiums', 0)/1_000_000:.2f}M")
            print(f"   Direction: {analysis['direction']}")
            print(f"   Signal Strength: {analysis['signal_strength']}")
            print(f"   Confidence: {result['analysis']['confidence']:.1%}")
        else:
            print(f"❌ Failed: {result.get('error', 'Unknown error')}")

def test_synthesis():
    """Test synthesis engine with multiple alerts"""
    print("\n" + "=" * 70)
    print("🧠 TEST 6: SYNTHESIS ENGINE")
    print("=" * 70)
    
    from tradytics_agents import TradyticsSynthesisEngine, DarkpoolAgent, OptionsSweepsAgent
    
    synthesis = TradyticsSynthesisEngine()
    darkpool_agent = DarkpoolAgent()
    options_agent = OptionsSweepsAgent()
    
    # Process multiple alerts
    alerts = [
        ("SPY Darkpool Signal - Large Darkpool Activity - Price: 685.831 - Shares: 1.4M - Amount: 960.16M", darkpool_agent),
        ("Options Golden Sweep - Call Golden Sweep - Symbol: GOOGL - Strike: 335.0 - Expiration: 8/21/2026 - Premiums: 1.81M", options_agent),
        ("SPY Darkpool Signal - Large Darkpool Activity - Price: 685.831 - Shares: 1.13M - Amount: 775.51M", darkpool_agent)
    ]
    
    print("\n📥 Processing 3 alerts...")
    for alert_text, agent in alerts:
        result = agent.process_alert(alert_text)
        if result['success']:
            synthesis_result = synthesis.add_signal(result)
            print(f"✅ Processed: {result['agent']}")
    
    # Get comprehensive market view
    market_view = synthesis.get_comprehensive_market_view()
    
    print("\n🧠 SYNTHESIZED MARKET INTELLIGENCE:")
    print(f"   Overall Direction: {market_view['synthesis']['overall_direction'].upper()}")
    print(f"   Confidence: {market_view['synthesis']['overall_confidence']:.1%}")
    print(f"   Signal Count: {market_view['synthesis']['signal_count']}")
    print(f"   Market Themes: {', '.join(market_view['synthesis'].get('market_themes', []))}")
    
    if market_view['synthesis'].get('key_symbols'):
        print(f"\n🎯 Key Symbols:")
        for symbol in market_view['synthesis']['key_symbols'][:3]:
            print(f"   {symbol['symbol']}: {symbol['direction']} ({symbol['strength']:.1%}) - {symbol['signal_count']} signals")
    
    print(f"\n⚠️ Risk Level: {market_view['synthesis']['risk_assessment']['level'].upper()}")
    print(f"   {market_view['synthesis']['risk_assessment']['rationale']}")

if __name__ == "__main__":
    print("🚀 TRADYTICS REAL ALERT TESTING SUITE")
    print("=" * 70)
    
    try:
        test_darkpool_alerts()
        test_bullseye_alerts()
        test_options_sweeps()
        test_analyst_grades()
        test_trady_flow()
        test_synthesis()
        
        print("\n" + "=" * 70)
        print("✅ ALL TESTS COMPLETED!")
        print("=" * 70)
        
    except Exception as e:
        print(f"\n❌ TEST ERROR: {e}")
        import traceback
        traceback.print_exc()
