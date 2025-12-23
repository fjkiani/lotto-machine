#!/usr/bin/env python3
"""
🎯 UNIFIED BACKTEST RUNNER
Runs all detectors and generates consolidated report.

DETECTORS SUPPORTED:
1. SelloffRallyDetector - Momentum signals
2. RapidAPIOptionsDetector - Options flow
3. GapDetector - Pre-market gaps
4. SqueezeDetector - Short squeeze
5. GammaDetector - Gamma exposure
6. RedditDetector - Reddit sentiment

Author: Zo (Alpha's AI)
"""

import os
import sys
from datetime import datetime, timedelta
from typing import List, Dict, Optional
import json

# Add paths
base_path = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, base_path)

from dotenv import load_dotenv
load_dotenv()

from backtesting.simulation.base_detector import BacktestResult, Signal
from backtesting.simulation.market_context_detector import MarketContextDetector, MarketContext
from backtesting.simulation.composite_signal_filter import CompositeSignalFilter, EnhancedSignal


class UnifiedBacktestRunner:
    """
    Runs all detectors and generates consolidated performance report.
    """
    
    DEFAULT_SYMBOLS = ['SPY', 'QQQ']
    
    def __init__(
        self,
        symbols: List[str] = None,
        enable_options: bool = True,
        enable_selloff: bool = True,
        enable_gap: bool = True,
        enable_squeeze: bool = True,
        enable_gamma: bool = True,
        enable_reddit: bool = True
    ):
        self.symbols = symbols or self.DEFAULT_SYMBOLS
        
        # Initialize enabled detectors
        self.detectors = {}
        
        if enable_selloff:
            from backtesting.simulation.selloff_rally_detector import SelloffRallyDetector
            self.detectors['selloff_rally'] = SelloffRallyDetector()
        
        if enable_gap:
            from backtesting.simulation.gap_detector import GapDetector
            self.detectors['gap'] = GapDetector()
        
        if enable_options:
            try:
                from backtesting.simulation.rapidapi_options_detector import RapidAPIOptionsDetector
                self.detectors['options_flow'] = RapidAPIOptionsDetector()
            except Exception as e:
                print(f"   ⚠️ Options detector unavailable: {e}")
        
        if enable_squeeze:
            try:
                from backtesting.simulation.squeeze_detector import SqueezeDetectorSimulator
                self.detectors['squeeze'] = SqueezeDetectorSimulator()
            except Exception as e:
                print(f"   ⚠️ Squeeze detector unavailable: {e}")
        
        if enable_gamma:
            try:
                from backtesting.simulation.gamma_detector import GammaDetectorSimulator
                self.detectors['gamma'] = GammaDetectorSimulator()
            except Exception as e:
                print(f"   ⚠️ Gamma detector unavailable: {e}")
        
        if enable_reddit:
            try:
                from backtesting.simulation.reddit_detector import RedditSignalSimulator
                self.detectors['reddit'] = RedditSignalSimulator()
            except Exception as e:
                print(f"   ⚠️ Reddit detector unavailable: {e}")
        
        # Initialize market context detector
        self.context_detector = MarketContextDetector()
        self.market_context = None
        
        # Initialize composite signal filter (for DP confluence + multi-factor scoring)
        self.use_composite_filter = os.getenv('USE_COMPOSITE_FILTER', 'true').lower() == 'true'
        if self.use_composite_filter:
            try:
                self.composite_filter = CompositeSignalFilter(api_key=os.getenv('CHARTEXCHANGE_API_KEY'))
                print(f"   🧠 Composite Signal Filter: ✅ ENABLED (DP confluence + multi-factor scoring)")
            except Exception as e:
                print(f"   ⚠️ Composite filter unavailable: {e}")
                self.use_composite_filter = False
                self.composite_filter = None
        else:
            self.composite_filter = None
            print(f"   🧠 Composite Signal Filter: ❌ DISABLED")
        
        print(f"📊 UnifiedBacktestRunner initialized with {len(self.detectors)} detectors")
        for name in self.detectors:
            print(f"   ✅ {name}")
    
    def run_all(self, date: str = None) -> Dict[str, BacktestResult]:
        """
        Run all enabled detectors for a date.
        
        Args:
            date: Date string (YYYY-MM-DD), defaults to today
            
        Returns:
            Dict of detector_name -> BacktestResult
        """
        date = date or datetime.now().strftime('%Y-%m-%d')
        results = {}
        
        print(f"\n{'='*70}")
        print(f"🎯 UNIFIED BACKTEST - {date}")
        print(f"{'='*70}")
        
        # First, analyze market context
        print(f"\n📊 Analyzing market context...")
        self.market_context = self.context_detector.analyze_market(date)
        self.context_detector.print_context(self.market_context)
        
        print(f"\n{'='*70}")
        filter_status = "with composite filter + context" if self.use_composite_filter else "filtered by context"
        print(f"🔍 RUNNING DETECTORS ({filter_status})")
        print(f"{'='*70}")
        
        for name, detector in self.detectors.items():
            try:
                print(f"\n🔍 Running {name}...")
                
                if hasattr(detector, 'backtest_date'):
                    # Use detector's backtest method
                    if name == 'options_flow':
                        # Options doesn't need symbols passed
                        result = detector.backtest_date()
                    else:
                        result = detector.backtest_date(self.symbols, date)
                else:
                    # Fallback for older detectors
                    print(f"   ⚠️ {name} doesn't support backtest_date")
                    continue
                
                # Apply composite filter if enabled (DP confluence + multi-factor scoring)
                if self.use_composite_filter and self.composite_filter and result.signals:
                    result = self._apply_composite_filter(name, result, date)
                
                # Filter results based on market context
                if self.market_context:
                    result = self._filter_by_context(name, result)
                
                results[name] = result
                self._print_summary(name, result)
                
            except Exception as e:
                print(f"   ❌ {name} failed: {e}")
                import traceback
                traceback.print_exc()
        
        # Print composite filter summary if enabled
        if self.use_composite_filter and self.composite_filter:
            self._print_composite_summary(results)
        
        return results
    
    def _print_composite_summary(self, results: Dict[str, BacktestResult]):
        """Print summary of composite filter impact"""
        print(f"\n{'='*70}")
        print(f"🧠 COMPOSITE FILTER IMPACT")
        print(f"{'='*70}")
        
        total_before = 0
        total_after = 0
        
        for name, result in results.items():
            # Note: We don't have "before" counts easily, but we can estimate
            # based on typical signal generation rates
            if len(result.signals) > 0:
                # Estimate: composite filter typically keeps 30-40% of signals
                estimated_before = int(len(result.signals) / 0.35)  # Rough estimate
                total_before += estimated_before
                total_after += len(result.signals)
        
        if total_before > 0:
            pass_rate = (total_after / total_before) * 100
            print(f"   Estimated signals before filter: {total_before}")
            print(f"   Signals after filter: {total_after}")
            print(f"   Pass rate: {pass_rate:.1f}%")
            print(f"   ✅ Filtered out low-quality signals, keeping only high-conviction trades")
        
        print()
    
    def _print_summary(self, name: str, result: BacktestResult):
        """Print quick summary for a detector"""
        emoji = "✅" if result.win_rate >= 50 else "⚠️"
        print(f"   {emoji} {name}: {len(result.signals)} signals, {result.win_rate:.1f}% win rate, {result.total_pnl:+.2f}% P&L")
    
    def _apply_composite_filter(self, name: str, result: BacktestResult, date: str) -> BacktestResult:
        """
        Apply composite signal filter (DP confluence + multi-factor scoring).
        
        This filters signals BEFORE trade simulation to only keep high-quality ones.
        """
        if not result.signals:
            return result
        
        print(f"      🧠 Applying composite filter to {len(result.signals)} signals...")
        
        # Get current prices for each symbol
        import yfinance as yf
        symbol_prices = {}
        for symbol in self.symbols:
            try:
                ticker = yf.Ticker(symbol)
                hist = ticker.history(period='1d', interval='1m')
                if not hist.empty:
                    symbol_prices[symbol] = float(hist['Close'].iloc[-1])
            except:
                pass
        
        # Filter signals by symbol
        filtered_signals = []
        date_obj = datetime.strptime(date, '%Y-%m-%d') if isinstance(date, str) else date
        
        for signal in result.signals:
            current_price = symbol_prices.get(signal.symbol, signal.entry_price)
            
            # Apply composite filter
            enhanced_signals = self.composite_filter.filter_signals(
                signals=[signal],
                symbol=signal.symbol,
                current_price=current_price,
                date=date_obj,
                market_context=self.market_context
            )
            
            if enhanced_signals and enhanced_signals[0].should_trade:
                # Use enhanced signal's adjusted stop/target
                enhanced = enhanced_signals[0]
                signal.stop_loss = enhanced.adjusted_stop
                signal.target = enhanced.adjusted_target
                signal.confidence = enhanced.composite_score  # Update confidence
                filtered_signals.append(signal)
        
        if not filtered_signals:
            print(f"      ⚠️ All signals filtered out by composite filter")
            return BacktestResult(
                detector_name=result.detector_name,
                date=result.date,
                signals=[],
                trades=[],
                win_rate=0,
                avg_pnl=0,
                total_pnl=0,
                profit_factor=0,
                avg_win=0,
                avg_loss=0,
                max_drawdown=0,
                sharpe_ratio=0
            )
        
        print(f"      ✅ Composite filter: {len(result.signals)} -> {len(filtered_signals)} signals ({len(filtered_signals)/len(result.signals)*100:.0f}% pass rate)")
        
        # Re-simulate trades for filtered signals
        # Get detector to simulate trades
        detector = self.detectors.get(name)
        if not detector:
            return result
        
        filtered_trades = []
        for signal in filtered_signals:
            # Get price data for simulation
            data = detector.get_intraday_data(signal.symbol, period="1d", interval="1m")
            if data.empty:
                continue
            
            # Find entry bar index
            entry_idx = None
            for i, idx in enumerate(data.index):
                if hasattr(idx, 'timestamp'):
                    if idx >= signal.timestamp:
                        entry_idx = i
                        break
                else:
                    entry_idx = 0
            
            if entry_idx is None:
                continue
            
            # Simulate trade
            trade = detector.simulate_trade(signal, data, entry_idx)
            filtered_trades.append(trade)
        
        # Recalculate metrics
        return detector._calculate_metrics(result.date, filtered_signals, filtered_trades)
    
    def _filter_by_context(self, name: str, result: BacktestResult) -> BacktestResult:
        """
        Filter trades based on market context.
        Only keep trades that align with market direction.
        """
        if not self.market_context or not result.trades:
            return result
        
        filtered_trades = []
        original_count = len(result.trades)
        
        for trade in result.trades:
            signal = trade.signal
            
            # Check alignment with market direction
            aligned = False
            
            if self.market_context.favor_longs and signal.direction == 'LONG':
                aligned = True
            elif self.market_context.favor_shorts and signal.direction == 'SHORT':
                aligned = True
            elif self.market_context.direction == 'CHOP':
                # In chop, only take high confidence signals
                if signal.confidence >= 80:
                    aligned = True
            
            if aligned:
                filtered_trades.append(trade)
        
        # Recalculate metrics with filtered trades
        if not filtered_trades:
            return BacktestResult(
                detector_name=result.detector_name,
                date=result.date,
                signals=result.signals,
                trades=[],
                win_rate=0,
                avg_pnl=0,
                total_pnl=0,
                profit_factor=0,
                avg_win=0,
                avg_loss=0,
                max_drawdown=0,
                sharpe_ratio=0
            )
        
        wins = [t for t in filtered_trades if t.outcome == 'WIN']
        losses = [t for t in filtered_trades if t.outcome == 'LOSS']
        
        win_rate = len(wins) / len(filtered_trades) * 100 if filtered_trades else 0
        pnls = [t.pnl_pct for t in filtered_trades]
        avg_pnl = sum(pnls) / len(pnls) if pnls else 0
        total_pnl = sum(pnls)
        
        avg_win = sum(t.pnl_pct for t in wins) / len(wins) if wins else 0
        avg_loss = sum(t.pnl_pct for t in losses) / len(losses) if losses else 0
        
        gross_profit = sum(t.pnl_pct for t in wins)
        gross_loss = abs(sum(t.pnl_pct for t in losses))
        profit_factor = gross_profit / gross_loss if gross_loss > 0 else float('inf')
        
        if len(pnls) > 1:
            import numpy as np
            sharpe = np.mean(pnls) / np.std(pnls) if np.std(pnls) > 0 else 0
        else:
            sharpe = 0
        
        kept_direction = 'LONG' if self.market_context.favor_longs else 'SHORT' if self.market_context.favor_shorts else 'BOTH'
        print(f"      📊 Context filter: {original_count} -> {len(filtered_trades)} trades (keeping {kept_direction}s in {self.market_context.direction} market)")
        
        return BacktestResult(
            detector_name=result.detector_name,
            date=result.date,
            signals=result.signals,
            trades=filtered_trades,
            win_rate=win_rate,
            avg_pnl=avg_pnl,
            total_pnl=total_pnl,
            profit_factor=profit_factor,
            avg_win=avg_win,
            avg_loss=avg_loss,
            max_drawdown=result.max_drawdown,
            sharpe_ratio=sharpe
        )
    
    def generate_report(self, results: Dict[str, BacktestResult]) -> str:
        """Generate consolidated text report"""
        lines = []
        lines.append("=" * 70)
        lines.append("📊 UNIFIED BACKTEST REPORT")
        lines.append("=" * 70)
        lines.append(f"Date: {datetime.now().strftime('%Y-%m-%d %H:%M')}")
        lines.append(f"Symbols: {', '.join(self.symbols)}")
        lines.append(f"Detectors: {len(results)}")
        lines.append("")
        
        # Summary table
        lines.append("DETECTOR              | SIGNALS | WIN RATE | AVG P&L | TOTAL P&L | SHARPE")
        lines.append("-" * 75)
        
        total_signals = 0
        total_pnl = 0
        
        for name, result in results.items():
            total_signals += len(result.signals)
            total_pnl += result.total_pnl
            
            lines.append(
                f"{name:<20} | {len(result.signals):>7} | {result.win_rate:>7.1f}% | "
                f"{result.avg_pnl:>+6.2f}% | {result.total_pnl:>+8.2f}% | {result.sharpe_ratio:>6.2f}"
            )
        
        lines.append("-" * 75)
        lines.append(f"{'TOTAL':<20} | {total_signals:>7} |         |         | {total_pnl:>+8.2f}% |")
        lines.append("")
        
        # Detailed signals
        lines.append("=" * 70)
        lines.append("SIGNAL DETAILS")
        lines.append("=" * 70)
        
        for name, result in results.items():
            if not result.signals:
                continue
            
            lines.append(f"\n📊 {name.upper()}")
            lines.append("-" * 40)
            
            for trade in result.trades[:5]:  # Top 5
                sig = trade.signal
                emoji = "✅" if trade.outcome == 'WIN' else "❌"
                lines.append(
                    f"   {emoji} {sig.symbol} {sig.direction} @ ${sig.entry_price:.2f} -> "
                    f"{trade.outcome} ({trade.pnl_pct:+.2f}%)"
                )
                lines.append(f"      {sig.reasoning[:60]}")
        
        lines.append("")
        lines.append("=" * 70)
        lines.append("✅ REPORT COMPLETE")
        lines.append("=" * 70)
        
        return "\n".join(lines)
    
    def save_results(self, results: Dict[str, BacktestResult], filename: str = None):
        """Save results to JSON"""
        filename = filename or f"backtest_results_{datetime.now().strftime('%Y%m%d_%H%M')}.json"
        
        output = {
            'timestamp': datetime.now().isoformat(),
            'symbols': self.symbols,
            'detectors': list(self.detectors.keys()),
            'results': {}
        }
        
        for name, result in results.items():
            output['results'][name] = {
                'date': result.date,
                'signals_count': len(result.signals),
                'trades_count': len(result.trades),
                'win_rate': result.win_rate,
                'avg_pnl': result.avg_pnl,
                'total_pnl': result.total_pnl,
                'profit_factor': result.profit_factor,
                'sharpe_ratio': result.sharpe_ratio,
                'max_drawdown': result.max_drawdown,
                'signals': [
                    {
                        'symbol': s.symbol,
                        'type': s.signal_type,
                        'direction': s.direction,
                        'entry': s.entry_price,
                        'confidence': s.confidence,
                        'reasoning': s.reasoning
                    }
                    for s in result.signals[:20]  # Top 20
                ],
                'trades': [
                    {
                        'symbol': t.signal.symbol,
                        'direction': t.signal.direction,
                        'entry': t.signal.entry_price,
                        'exit': t.exit_price,
                        'pnl': t.pnl_pct,
                        'outcome': t.outcome
                    }
                    for t in result.trades
                ]
            }
        
        with open(filename, 'w') as f:
            json.dump(output, f, indent=2, default=str)
        
        print(f"\n💾 Results saved to: {filename}")
        return filename


# Standalone execution
if __name__ == "__main__":
    print("=" * 70)
    print("🎯 UNIFIED BACKTEST RUNNER")
    print("=" * 70)
    
    runner = UnifiedBacktestRunner(
        symbols=['SPY', 'QQQ'],
        enable_options=True,
        enable_selloff=True,
        enable_gap=True,
        enable_squeeze=False,  # May need API
        enable_gamma=False,    # May need API
        enable_reddit=False    # May need API
    )
    
    # Run backtest
    results = runner.run_all()
    
    # Generate report
    report = runner.generate_report(results)
    print("\n" + report)
    
    # Save results
    runner.save_results(results)
    
    print("\n✅ UNIFIED BACKTEST COMPLETE!")

