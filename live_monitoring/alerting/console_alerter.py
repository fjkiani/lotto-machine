#!/usr/bin/env python3
"""
CONSOLE ALERTER - Beautiful terminal output
- Color-coded alerts
- Clear formatting
"""

from datetime import datetime
import sys
from pathlib import Path

sys.path.append(str(Path(__file__).parent.parent / 'core'))
from signal_generator import LiveSignal

# ANSI color codes
class Colors:
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    RED = '\033[91m'
    BLUE = '\033[94m'
    CYAN = '\033[96m'
    BOLD = '\033[1m'
    END = '\033[0m'

class ConsoleAlerter:
    """Alert to terminal/console"""
    
    def __init__(self, use_colors: bool = True):
        self.use_colors = use_colors
    
    def alert_signal(self, signal: LiveSignal):
        """Alert a trading signal"""
        if self.use_colors:
            self._alert_signal_colored(signal)
        else:
            self._alert_signal_plain(signal)
    
    def _alert_signal_colored(self, signal: LiveSignal):
        """Colored signal alert"""
        print(f"\n{Colors.BOLD}{'='*80}{Colors.END}")
        
        if signal.is_master_signal:
            print(f"{Colors.GREEN}{Colors.BOLD}🎯 MASTER SIGNAL{Colors.END}")
        else:
            print(f"{Colors.YELLOW}{Colors.BOLD}📊 HIGH CONFIDENCE SIGNAL{Colors.END}")
        
        print(f"{Colors.BOLD}{'='*80}{Colors.END}")
        
        print(f"\n{Colors.CYAN}Symbol:{Colors.END} {Colors.BOLD}{signal.symbol}{Colors.END}")
        print(f"{Colors.CYAN}Type:{Colors.END} {signal.signal_type}")
        print(f"{Colors.CYAN}Action:{Colors.END} {Colors.GREEN if signal.action == 'BUY' else Colors.RED}{signal.action}{Colors.END}")
        print(f"{Colors.CYAN}Time:{Colors.END} {signal.timestamp.strftime('%Y-%m-%d %H:%M:%S')}")
        
        print(f"\n{Colors.BLUE}PRICES:{Colors.END}")
        print(f"  Current:  ${signal.current_price:.2f}")
        print(f"  Entry:    ${signal.entry_price:.2f}")
        print(f"  Stop:     ${signal.stop_loss:.2f}")
        print(f"  Target:   ${signal.take_profit:.2f}")
        
        print(f"\n{Colors.BLUE}METRICS:{Colors.END}")
        print(f"  Confidence:  {signal.confidence:.0%}")
        print(f"  Risk/Reward: 1:{signal.risk_reward_ratio:.1f}")
        print(f"  Position:    {signal.position_size_pct:.1%} of account")
        print(f"  Inst Score:  {signal.institutional_score:.0%}")
        
        print(f"\n{Colors.BLUE}REASONING:{Colors.END}")
        print(f"  {signal.primary_reason}")
        
        if signal.supporting_factors:
            print(f"\n{Colors.BLUE}SUPPORTING:{Colors.END}")
            for factor in signal.supporting_factors:
                if factor:  # Skip empty strings
                    print(f"  • {factor}")
        
        if signal.warnings:
            print(f"\n{Colors.YELLOW}⚠️  WARNINGS:{Colors.END}")
            for warning in signal.warnings:
                print(f"  • {warning}")
        
        print(f"\n{Colors.BOLD}{'='*80}{Colors.END}\n")
    
    def _alert_signal_plain(self, signal: LiveSignal):
        """Plain signal alert (no colors)"""
        print("\n" + "="*80)
        print(f"🎯 {'MASTER' if signal.is_master_signal else 'HIGH CONFIDENCE'} SIGNAL")
        print("="*80)
        print(f"\nSymbol: {signal.symbol}")
        print(f"Type: {signal.signal_type}")
        print(f"Action: {signal.action}")
        print(f"Time: {signal.timestamp.strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"\nPRICES:")
        print(f"  Current: ${signal.current_price:.2f}")
        print(f"  Entry:   ${signal.entry_price:.2f}")
        print(f"  Stop:    ${signal.stop_loss:.2f}")
        print(f"  Target:  ${signal.take_profit:.2f}")
        print(f"\nMETRICS:")
        print(f"  Confidence:  {signal.confidence:.0%}")
        print(f"  Risk/Reward: 1:{signal.risk_reward_ratio:.1f}")
        print(f"  Position:    {signal.position_size_pct:.1%} of account")
        print(f"\nREASONING:")
        print(f"  {signal.primary_reason}")
        print("\n" + "="*80 + "\n")
    
    def alert_info(self, message: str):
        """Info message"""
        if self.use_colors:
            print(f"{Colors.BLUE}ℹ️  {message}{Colors.END}")
        else:
            print(f"ℹ️  {message}")
    
    def alert_warning(self, message: str):
        """Warning message"""
        if self.use_colors:
            print(f"{Colors.YELLOW}⚠️  {message}{Colors.END}")
        else:
            print(f"⚠️  {message}")
    
    def alert_error(self, message: str):
        """Error message"""
        if self.use_colors:
            print(f"{Colors.RED}❌ {message}{Colors.END}")
        else:
            print(f"❌ {message}")



