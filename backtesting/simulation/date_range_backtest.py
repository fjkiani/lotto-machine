#!/usr/bin/env python3
"""
🎯 DATE RANGE BACKTEST
Run comprehensive backtests for specific date ranges using ALL detectors.

Integrates with the backtesting framework:
- Uses BaseDetector for standardized signal/trade handling
- Generates proper BacktestResult with metrics
- Saves results to reports/

Usage:
    python -m backtesting.simulation.date_range_backtest --start 2025-12-23 --end 2025-12-24
    python -m backtesting.simulation.date_range_backtest --today
    python -m backtesting.simulation.date_range_backtest --days 5

Author: Zo (Alpha's AI)
Date: 2025-12-25
"""

import os
import sys
import json
import argparse
from datetime import datetime, timedelta
from dataclasses import dataclass, field, asdict
from typing import List, Dict, Optional, Any
import pandas as pd

# Add paths
base_path = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, base_path)

from dotenv import load_dotenv
load_dotenv()

# Framework imports
from backtesting.simulation.base_detector import Signal, TradeResult, BacktestResult


@dataclass
class DailyBacktestResult:
    """Complete backtest result for a single day"""
    date: str
    market_direction: str  # UP, DOWN, CHOP
    market_strength: float
    vix: float
    
    # Per-detector results
    selloff_rally: Optional[BacktestResult] = None
    dark_pool: Optional[Dict] = None
    squeeze: Optional[Dict] = None
    gamma: Optional[Dict] = None
    reddit: Optional[Dict] = None
    options_flow: Optional[BacktestResult] = None
    premarket_gap: Optional[Dict] = None
    
    # Aggregated metrics
    total_signals: int = 0
    total_trades: int = 0
    total_wins: int = 0
    total_losses: int = 0
    win_rate: float = 0.0
    total_pnl: float = 0.0
    
    def to_dict(self) -> Dict:
        """Convert to dictionary for JSON serialization"""
        result = {
            'date': self.date,
            'market_direction': self.market_direction,
            'market_strength': self.market_strength,
            'vix': self.vix,
            'total_signals': self.total_signals,
            'total_trades': self.total_trades,
            'win_rate': self.win_rate,
            'total_pnl': self.total_pnl,
        }
        
        if self.selloff_rally:
            result['selloff_rally'] = {
                'signals': len(self.selloff_rally.signals),
                'trades': len(self.selloff_rally.trades),
                'win_rate': self.selloff_rally.win_rate,
                'pnl': self.selloff_rally.total_pnl,
            }
        
        if self.options_flow:
            result['options_flow'] = {
                'signals': len(self.options_flow.signals),
                'trades': len(self.options_flow.trades),
                'win_rate': self.options_flow.win_rate,
                'pnl': self.options_flow.total_pnl,
            }
        
        return result


@dataclass
class RangeBacktestResult:
    """Complete backtest result for a date range"""
    start_date: str
    end_date: str
    trading_days: int
    
    # Per-day results
    daily_results: List[DailyBacktestResult] = field(default_factory=list)
    
    # Aggregated metrics across all days
    total_signals: int = 0
    total_trades: int = 0
    total_wins: int = 0
    total_losses: int = 0
    win_rate: float = 0.0
    total_pnl: float = 0.0
    avg_daily_pnl: float = 0.0
    max_drawdown: float = 0.0
    sharpe_ratio: float = 0.0
    profit_factor: float = 0.0
    
    # By signal type
    selloff_rally_signals: int = 0
    selloff_rally_win_rate: float = 0.0
    selloff_rally_pnl: float = 0.0
    
    options_flow_signals: int = 0
    options_flow_win_rate: float = 0.0
    options_flow_pnl: float = 0.0
    
    dark_pool_alerts: int = 0
    squeeze_candidates: int = 0
    
    # Validation
    passed_validation: bool = False
    validation_notes: List[str] = field(default_factory=list)


class DateRangeBacktester:
    """
    Runs comprehensive backtests for date ranges using all detectors.
    """
    
    VALIDATION_CRITERIA = {
        'min_trades': 10,
        'min_win_rate': 0.50,
        'max_drawdown': 0.15,
    }
    
    def __init__(self, symbols: List[str] = None):
        self.symbols = symbols or ['SPY', 'QQQ']
        self.api_key = os.getenv('CHARTEXCHANGE_API_KEY')
        self.rapidapi_key = os.getenv('RAPIDAPI_KEY')
        
        # Initialize detectors
        self._init_detectors()
    
    def _init_detectors(self):
        """Initialize all available detectors"""
        self.detectors = {}
        
        # Selloff/Rally
        try:
            from backtesting.simulation.selloff_rally_detector import SelloffRallyDetector
            self.detectors['selloff_rally'] = SelloffRallyDetector()
            print("✅ SelloffRallyDetector loaded")
        except Exception as e:
            print(f"❌ SelloffRallyDetector: {e}")
        
        # Gap
        try:
            from backtesting.simulation.gap_detector import GapDetector
            self.detectors['gap'] = GapDetector()
            print("✅ GapDetector loaded")
        except Exception as e:
            print(f"❌ GapDetector: {e}")
        
        # Options Flow
        try:
            from backtesting.simulation.rapidapi_options_detector import RapidAPIOptionsDetector
            self.detectors['options_flow'] = RapidAPIOptionsDetector()
            print("✅ OptionsFlowDetector loaded")
        except Exception as e:
            print(f"❌ OptionsFlowDetector: {e}")
        
        # Market Context
        try:
            from backtesting.simulation.market_context_detector import MarketContextDetector
            self.context_detector = MarketContextDetector()
            print("✅ MarketContextDetector loaded")
        except Exception as e:
            self.context_detector = None
            print(f"❌ MarketContextDetector: {e}")
        
        # ChartExchange client for DP/Squeeze/Reddit
        if self.api_key:
            try:
                from core.data.ultimate_chartexchange_client import UltimateChartExchangeClient
                self.ce_client = UltimateChartExchangeClient(api_key=self.api_key)
                print("✅ ChartExchangeClient loaded")
            except Exception as e:
                self.ce_client = None
                print(f"❌ ChartExchangeClient: {e}")
        else:
            self.ce_client = None
            print("⚠️ No ChartExchange API key")
    
    def _get_historical_data(self, symbol: str, date_str: str) -> pd.DataFrame:
        """Fetch intraday data for a specific date"""
        import yfinance as yf
        
        try:
            date = datetime.strptime(date_str, '%Y-%m-%d')
            today = datetime.now()
            days_ago = (today - date).days
            
            ticker = yf.Ticker(symbol)
            
            if days_ago <= 7:
                data = ticker.history(period=f"{days_ago + 1}d", interval="1m")
            else:
                data = ticker.history(start=date_str, end=(date + timedelta(days=1)).strftime('%Y-%m-%d'), interval="5m")
            
            if data.empty:
                return pd.DataFrame()
            
            return data[data.index.date.astype(str) == date_str]
            
        except Exception as e:
            return pd.DataFrame()
    
    def _check_dark_pool(self, date_str: str) -> Dict:
        """Check DP levels for the date"""
        if not self.ce_client:
            return {'alerts': 0, 'levels': []}
        
        try:
            date_obj = datetime.strptime(date_str, '%Y-%m-%d')
            prev_date = (date_obj - timedelta(days=1)).strftime('%Y-%m-%d')
            
            all_levels = []
            
            for symbol in self.symbols:
                data = self._get_historical_data(symbol, date_str)
                if data.empty:
                    continue
                
                day_high = data['High'].max()
                day_low = data['Low'].min()
                
                levels = self.ce_client.get_dark_pool_levels(symbol, prev_date)
                if not levels:
                    continue
                
                level_list = levels.get('levels', levels) if isinstance(levels, dict) else levels
                
                for level_data in level_list[:20]:
                    level = float(level_data.get('level', level_data.get('price', 0)))
                    volume = int(level_data.get('volume', level_data.get('total_volume', 0)))
                    
                    if day_low <= level <= day_high and volume >= 500000:
                        all_levels.append({
                            'symbol': symbol,
                            'level': level,
                            'volume': volume,
                            'touched': True
                        })
            
            return {
                'alerts': len(all_levels),
                'levels': all_levels
            }
            
        except Exception as e:
            return {'alerts': 0, 'levels': [], 'error': str(e)}
    
    def _check_squeeze(self, date_str: str) -> Dict:
        """Check squeeze candidates for the date"""
        if not self.ce_client:
            return {'candidates': 0, 'stocks': []}
        
        try:
            date_obj = datetime.strptime(date_str, '%Y-%m-%d')
            prev_date = (date_obj - timedelta(days=1)).strftime('%Y-%m-%d')
            
            candidates = []
            universe = ['SPY', 'QQQ', 'GME', 'AMC', 'TSLA', 'NVDA', 'AAPL']
            
            for symbol in universe:
                try:
                    short_data = self.ce_client.get_short_interest(symbol, prev_date)
                    if not short_data:
                        continue
                    
                    si_pct = 0
                    if isinstance(short_data, dict):
                        si_pct = float(short_data.get('short_interest_pct', short_data.get('si_pct', 0)))
                    elif isinstance(short_data, list) and len(short_data) > 0:
                        si_pct = float(short_data[0].get('short_interest_pct', 0))
                    
                    if si_pct >= 10:
                        candidates.append({
                            'symbol': symbol,
                            'si_pct': si_pct,
                        })
                except:
                    continue
            
            return {
                'candidates': len(candidates),
                'stocks': candidates
            }
            
        except Exception as e:
            return {'candidates': 0, 'stocks': [], 'error': str(e)}
    
    def backtest_date(self, date_str: str) -> DailyBacktestResult:
        """Run full backtest for a single date"""
        print(f"\n{'='*60}")
        print(f"📅 BACKTESTING: {date_str}")
        print(f"{'='*60}")
        
        # Get market context
        market_direction = 'UNKNOWN'
        market_strength = 0.0
        vix = 0.0
        
        if self.context_detector:
            try:
                context = self.context_detector.analyze_market(date_str)
                market_direction = context.direction
                market_strength = getattr(context, 'trend_strength', 0.0)
                vix = getattr(context, 'vix_level', 0.0)
                self.context_detector.print_context(context)
            except Exception as e:
                print(f"   ⚠️ Context failed: {e}")
        
        result = DailyBacktestResult(
            date=date_str,
            market_direction=market_direction,
            market_strength=market_strength,
            vix=vix,
        )
        
        # Run selloff/rally detector
        print("\n📉📈 SELLOFF/RALLY:")
        if 'selloff_rally' in self.detectors:
            try:
                sr_result = self.detectors['selloff_rally'].backtest_date(self.symbols, date_str)
                result.selloff_rally = sr_result
                print(f"   ✅ {len(sr_result.signals)} signals | {sr_result.win_rate:.1f}% WR | {sr_result.total_pnl:+.2f}% P&L")
                
                for trade in sr_result.trades[:5]:
                    emoji = "✅" if trade.outcome == 'WIN' else "❌"
                    print(f"      {emoji} {trade.signal.symbol} {trade.signal.direction} @ ${trade.signal.entry_price:.2f} -> {trade.pnl_pct:+.2f}%")
            except Exception as e:
                print(f"   ❌ Failed: {e}")
        
        # Run options flow detector
        print("\n📊 OPTIONS FLOW:")
        if 'options_flow' in self.detectors:
            try:
                of_result = self.detectors['options_flow'].backtest_date()
                result.options_flow = of_result
                print(f"   ✅ {len(of_result.signals)} signals | {of_result.win_rate:.1f}% WR | {of_result.total_pnl:+.2f}% P&L")
                
                bullish = [s for s in of_result.signals if s.direction == 'LONG']
                bearish = [s for s in of_result.signals if s.direction == 'SHORT']
                print(f"      📈 Bullish: {len(bullish)} | 📉 Bearish: {len(bearish)}")
            except Exception as e:
                print(f"   ❌ Failed: {e}")
        
        # Run gap detector
        print("\n🌅 GAP:")
        if 'gap' in self.detectors:
            try:
                gap_result = self.detectors['gap'].backtest_date(self.symbols, date_str)
                if gap_result.signals:
                    print(f"   ✅ {len(gap_result.signals)} gap signals")
                else:
                    print(f"   ⚠️ No significant gaps")
            except Exception as e:
                print(f"   ❌ Failed: {e}")
        
        # Check DP levels
        print("\n🔒 DARK POOL:")
        result.dark_pool = self._check_dark_pool(date_str)
        if result.dark_pool['alerts'] > 0:
            print(f"   ✅ {result.dark_pool['alerts']} significant levels touched")
            for level in result.dark_pool['levels'][:5]:
                print(f"      🎯 {level['symbol']} @ ${level['level']:.2f} ({level['volume']:,} shares)")
        else:
            print(f"   ⚠️ No significant DP activity")
        
        # Check squeeze
        print("\n🔥 SQUEEZE:")
        result.squeeze = self._check_squeeze(date_str)
        if result.squeeze['candidates'] > 0:
            print(f"   ✅ {result.squeeze['candidates']} squeeze candidates")
            for stock in result.squeeze['stocks']:
                print(f"      🔥 {stock['symbol']}: {stock['si_pct']:.1f}% SI")
        else:
            print(f"   ⚠️ No squeeze candidates")
        
        # Aggregate metrics
        if result.selloff_rally:
            result.total_signals += len(result.selloff_rally.signals)
            result.total_trades += len(result.selloff_rally.trades)
            result.total_wins += len([t for t in result.selloff_rally.trades if t.outcome == 'WIN'])
            result.total_losses += len([t for t in result.selloff_rally.trades if t.outcome == 'LOSS'])
            result.total_pnl += result.selloff_rally.total_pnl
        
        if result.options_flow:
            result.total_signals += len(result.options_flow.signals)
            result.total_trades += len(result.options_flow.trades)
            result.total_wins += len([t for t in result.options_flow.trades if t.outcome == 'WIN'])
            result.total_losses += len([t for t in result.options_flow.trades if t.outcome == 'LOSS'])
            result.total_pnl += result.options_flow.total_pnl
        
        if result.total_trades > 0:
            result.win_rate = result.total_wins / result.total_trades * 100
        
        return result
    
    def backtest_range(self, start_date: str, end_date: str) -> RangeBacktestResult:
        """Run backtest for a date range"""
        print("=" * 70)
        print(f"🎯 DATE RANGE BACKTEST: {start_date} to {end_date}")
        print("=" * 70)
        print(f"Symbols: {', '.join(self.symbols)}")
        print(f"Detectors: {', '.join(self.detectors.keys())}")
        
        result = RangeBacktestResult(
            start_date=start_date,
            end_date=end_date,
            trading_days=0,
        )
        
        # Generate date range
        current = datetime.strptime(start_date, '%Y-%m-%d')
        end = datetime.strptime(end_date, '%Y-%m-%d')
        
        while current <= end:
            # Skip weekends
            if current.weekday() < 5:
                daily = self.backtest_date(current.strftime('%Y-%m-%d'))
                result.daily_results.append(daily)
                result.trading_days += 1
            
            current += timedelta(days=1)
        
        # Aggregate results
        self._aggregate_results(result)
        
        # Validate
        self._validate_results(result)
        
        return result
    
    def _aggregate_results(self, result: RangeBacktestResult):
        """Aggregate metrics across all days"""
        all_pnls = []
        
        for daily in result.daily_results:
            result.total_signals += daily.total_signals
            result.total_trades += daily.total_trades
            result.total_wins += daily.total_wins
            result.total_losses += daily.total_losses
            result.total_pnl += daily.total_pnl
            all_pnls.append(daily.total_pnl)
            
            if daily.selloff_rally:
                result.selloff_rally_signals += len(daily.selloff_rally.signals)
                result.selloff_rally_pnl += daily.selloff_rally.total_pnl
            
            if daily.options_flow:
                result.options_flow_signals += len(daily.options_flow.signals)
                result.options_flow_pnl += daily.options_flow.total_pnl
            
            if daily.dark_pool:
                result.dark_pool_alerts += daily.dark_pool.get('alerts', 0)
            
            if daily.squeeze:
                result.squeeze_candidates += daily.squeeze.get('candidates', 0)
        
        # Calculate aggregate metrics
        if result.total_trades > 0:
            result.win_rate = result.total_wins / result.total_trades * 100
        
        if result.trading_days > 0:
            result.avg_daily_pnl = result.total_pnl / result.trading_days
        
        # Calculate drawdown
        if all_pnls:
            cumulative = 0
            peak = 0
            max_dd = 0
            for pnl in all_pnls:
                cumulative += pnl
                peak = max(peak, cumulative)
                dd = peak - cumulative
                max_dd = max(max_dd, dd)
            result.max_drawdown = max_dd
        
        # Calculate Sharpe (simplified)
        if len(all_pnls) > 1:
            import statistics
            avg = statistics.mean(all_pnls)
            std = statistics.stdev(all_pnls)
            result.sharpe_ratio = avg / std if std > 0 else 0
        
        # Calculate profit factor
        gross_profit = sum(d.total_pnl for d in result.daily_results if d.total_pnl > 0)
        gross_loss = abs(sum(d.total_pnl for d in result.daily_results if d.total_pnl < 0))
        result.profit_factor = gross_profit / gross_loss if gross_loss > 0 else float('inf')
        
        # Per-detector win rates
        sr_wins = sum(len([t for t in d.selloff_rally.trades if t.outcome == 'WIN']) 
                     for d in result.daily_results if d.selloff_rally)
        sr_trades = sum(len(d.selloff_rally.trades) 
                       for d in result.daily_results if d.selloff_rally)
        result.selloff_rally_win_rate = sr_wins / sr_trades * 100 if sr_trades > 0 else 0
        
        of_wins = sum(len([t for t in d.options_flow.trades if t.outcome == 'WIN']) 
                     for d in result.daily_results if d.options_flow)
        of_trades = sum(len(d.options_flow.trades) 
                       for d in result.daily_results if d.options_flow)
        result.options_flow_win_rate = of_wins / of_trades * 100 if of_trades > 0 else 0
    
    def _validate_results(self, result: RangeBacktestResult):
        """Validate against criteria"""
        notes = []
        passed = True
        
        if result.total_trades < self.VALIDATION_CRITERIA['min_trades']:
            notes.append(f"❌ Only {result.total_trades} trades (need {self.VALIDATION_CRITERIA['min_trades']}+)")
            passed = False
        else:
            notes.append(f"✅ {result.total_trades} trades (meets minimum)")
        
        if result.win_rate < self.VALIDATION_CRITERIA['min_win_rate'] * 100:
            notes.append(f"❌ Win rate {result.win_rate:.1f}% < {self.VALIDATION_CRITERIA['min_win_rate']*100}%")
            passed = False
        else:
            notes.append(f"✅ Win rate {result.win_rate:.1f}% (meets minimum)")
        
        if result.max_drawdown > self.VALIDATION_CRITERIA['max_drawdown'] * 100:
            notes.append(f"⚠️ Max DD {result.max_drawdown:.2f}% > {self.VALIDATION_CRITERIA['max_drawdown']*100}%")
        else:
            notes.append(f"✅ Max DD {result.max_drawdown:.2f}% (within limits)")
        
        if result.total_pnl > 0:
            notes.append(f"✅ Profitable: {result.total_pnl:+.2f}%")
        else:
            notes.append(f"❌ Unprofitable: {result.total_pnl:+.2f}%")
            passed = False
        
        result.passed_validation = passed
        result.validation_notes = notes
    
    def generate_report(self, result: RangeBacktestResult) -> str:
        """Generate text report"""
        lines = []
        lines.append("=" * 70)
        lines.append("📊 BACKTEST REPORT")
        lines.append("=" * 70)
        lines.append(f"Date Range: {result.start_date} to {result.end_date}")
        lines.append(f"Trading Days: {result.trading_days}")
        lines.append(f"Symbols: {', '.join(self.symbols)}")
        lines.append("")
        
        lines.append("📈 PERFORMANCE SUMMARY")
        lines.append("-" * 40)
        lines.append(f"Total Signals: {result.total_signals}")
        lines.append(f"Total Trades: {result.total_trades}")
        lines.append(f"Win Rate: {result.win_rate:.1f}%")
        lines.append(f"Total P&L: {result.total_pnl:+.2f}%")
        lines.append(f"Avg Daily P&L: {result.avg_daily_pnl:+.2f}%")
        lines.append(f"Max Drawdown: {result.max_drawdown:.2f}%")
        lines.append(f"Sharpe Ratio: {result.sharpe_ratio:.2f}")
        lines.append(f"Profit Factor: {result.profit_factor:.2f}")
        lines.append("")
        
        lines.append("📊 BY SIGNAL TYPE")
        lines.append("-" * 40)
        lines.append(f"Selloff/Rally: {result.selloff_rally_signals} signals | {result.selloff_rally_win_rate:.1f}% WR | {result.selloff_rally_pnl:+.2f}% P&L")
        lines.append(f"Options Flow: {result.options_flow_signals} signals | {result.options_flow_win_rate:.1f}% WR | {result.options_flow_pnl:+.2f}% P&L")
        lines.append(f"Dark Pool Alerts: {result.dark_pool_alerts}")
        lines.append(f"Squeeze Candidates: {result.squeeze_candidates}")
        lines.append("")
        
        lines.append("📅 DAILY BREAKDOWN")
        lines.append("-" * 40)
        for daily in result.daily_results:
            emoji = "🟢" if daily.total_pnl >= 0 else "🔴"
            lines.append(f"   {emoji} {daily.date}: {daily.total_signals} signals | {daily.win_rate:.0f}% WR | {daily.total_pnl:+.2f}% P&L | {daily.market_direction}")
        lines.append("")
        
        lines.append("✅ VALIDATION")
        lines.append("-" * 40)
        for note in result.validation_notes:
            lines.append(f"   {note}")
        lines.append("")
        
        status = "✅ PASSED" if result.passed_validation else "❌ FAILED"
        lines.append(f"RESULT: {status}")
        lines.append("=" * 70)
        
        return "\n".join(lines)
    
    def save_results(self, result: RangeBacktestResult, filename: str = None) -> str:
        """Save results to JSON"""
        reports_dir = os.path.join(base_path, 'backtesting', 'reports')
        os.makedirs(reports_dir, exist_ok=True)
        
        filename = filename or f"backtest_{result.start_date}_{result.end_date}.json"
        filepath = os.path.join(reports_dir, filename)
        
        output = {
            'timestamp': datetime.now().isoformat(),
            'start_date': result.start_date,
            'end_date': result.end_date,
            'trading_days': result.trading_days,
            'symbols': self.symbols,
            'summary': {
                'total_signals': result.total_signals,
                'total_trades': result.total_trades,
                'win_rate': result.win_rate,
                'total_pnl': result.total_pnl,
                'avg_daily_pnl': result.avg_daily_pnl,
                'max_drawdown': result.max_drawdown,
                'sharpe_ratio': result.sharpe_ratio,
                'profit_factor': result.profit_factor,
            },
            'by_signal_type': {
                'selloff_rally': {
                    'signals': result.selloff_rally_signals,
                    'win_rate': result.selloff_rally_win_rate,
                    'pnl': result.selloff_rally_pnl,
                },
                'options_flow': {
                    'signals': result.options_flow_signals,
                    'win_rate': result.options_flow_win_rate,
                    'pnl': result.options_flow_pnl,
                },
                'dark_pool_alerts': result.dark_pool_alerts,
                'squeeze_candidates': result.squeeze_candidates,
            },
            'daily_results': [d.to_dict() for d in result.daily_results],
            'validation': {
                'passed': result.passed_validation,
                'notes': result.validation_notes,
            }
        }
        
        with open(filepath, 'w') as f:
            json.dump(output, f, indent=2, default=str)
        
        print(f"\n💾 Results saved to: {filepath}")
        return filepath


def main():
    parser = argparse.ArgumentParser(description='Run date range backtest')
    parser.add_argument('--start', type=str, help='Start date (YYYY-MM-DD)')
    parser.add_argument('--end', type=str, help='End date (YYYY-MM-DD)')
    parser.add_argument('--today', action='store_true', help='Backtest today only')
    parser.add_argument('--days', type=int, help='Backtest last N days')
    parser.add_argument('--symbols', type=str, default='SPY,QQQ', help='Comma-separated symbols')
    parser.add_argument('--no-options', action='store_true', help='Disable options flow (broken)')
    parser.add_argument('--only-profitable', action='store_true', help='Only run profitable signals (selloff/rally)')
    
    args = parser.parse_args()
    
    # Determine date range
    if args.today:
        start_date = end_date = datetime.now().strftime('%Y-%m-%d')
    elif args.days:
        end_date = datetime.now().strftime('%Y-%m-%d')
        start_date = (datetime.now() - timedelta(days=args.days)).strftime('%Y-%m-%d')
    elif args.start and args.end:
        start_date = args.start
        end_date = args.end
    else:
        # Default: yesterday and today
        end_date = datetime.now().strftime('%Y-%m-%d')
        start_date = (datetime.now() - timedelta(days=1)).strftime('%Y-%m-%d')
    
    symbols = args.symbols.split(',')
    
    # Run backtest
    backtester = DateRangeBacktester(symbols=symbols)
    
    # Disable broken detectors if requested
    if args.no_options or args.only_profitable:
        if 'options_flow' in backtester.detectors:
            del backtester.detectors['options_flow']
            print("⚠️ OPTIONS FLOW DISABLED (broken - 0% win rate)")
    
    if args.only_profitable:
        # Keep only selloff/rally
        keep = ['selloff_rally']
        for det in list(backtester.detectors.keys()):
            if det not in keep:
                del backtester.detectors[det]
        print("✅ Running ONLY profitable signals (selloff/rally)")
    
    result = backtester.backtest_range(start_date, end_date)
    
    # Generate report
    report = backtester.generate_report(result)
    print("\n" + report)
    
    # Save results
    backtester.save_results(result)
    
    print("\n✅ BACKTEST COMPLETE!")


if __name__ == "__main__":
    main()

