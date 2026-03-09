# 🎯 FULL PIPELINE BACKTEST - FIX PLAN

**Issue:** `date_range_backtest.py` runs all detectors but doesn't convert squeeze/gamma/FTD/reddit signals to trades.

---

## ✅ WHAT EXISTS

1. **DateRangeBacktester** - Runs all detectors, gets signals
2. **SqueezeDetectorSimulator** - Converts squeeze signals to trades
3. **GammaDetectorSimulator** - Converts gamma signals to trades
4. **RedditSignalSimulator** - Converts reddit signals to trades
5. **BaseDetector.simulate_trade()** - Generic trade simulation

---

## 🔧 THE FIX

**Enhance `date_range_backtest.py` to:**

1. Keep using live detectors to get signals (already working)
2. Convert signals to trades using simulators or BaseDetector
3. Aggregate all trades into `DailyBacktestResult`

**For each detector type:**

### Squeeze
- Get signals from `_run_squeeze_detector()` (already returns Dict with 'details')
- Convert each signal to `Signal` object
- Use `SqueezeDetectorSimulator.simulate_trade()` OR `BaseDetector.simulate_trade()`
- Add trades to `result.squeeze_trades` (new field)

### Gamma
- Get signals from `_run_gamma_tracker()` (already returns Dict with 'details')
- Convert to `Signal` objects
- Use `GammaDetectorSimulator.simulate_trade()` OR `BaseDetector.simulate_trade()`
- Add trades to `result.gamma_trades` (new field)

### FTD
- Get signals from `_run_ftd_analyzer()` (already returns Dict with 'details')
- Convert to `Signal` objects
- Use `BaseDetector.simulate_trade()` (no FTD simulator exists)
- Add trades to `result.ftd_trades` (new field)

### Reddit
- Get signals from `_run_reddit_exploiter()` (already returns Dict with 'details')
- Convert to `Signal` objects
- Use `RedditSignalSimulator.simulate_trade()` OR `BaseDetector.simulate_trade()`
- Add trades to `result.reddit_trades` (new field)

---

## 📝 IMPLEMENTATION

Add method to `DateRangeBacktester`:

```python
def _convert_signals_to_trades(self, signals: List[Dict], signal_type: str, date_str: str, symbols: List[str]) -> List[TradeResult]:
    """Convert detector signals to trades using BaseDetector simulation"""
    trades = []
    
    # Get intraday data for the date
    for sig in signals:
        symbol = sig.get('symbol')
        if symbol not in symbols:
            continue
        
        # Get price data
        data = self._get_historical_data(symbol, date_str)
        if data.empty:
            continue
        
        # Create Signal object
        signal = Signal(
            symbol=symbol,
            timestamp=data.index[0],
            signal_type=signal_type,
            direction=sig.get('action', 'LONG'),
            entry_price=sig.get('entry', data['Close'].iloc[0]),
            stop_price=sig.get('entry', data['Close'].iloc[0]) * 0.98,  # 2% stop
            target_price=sig.get('entry', data['Close'].iloc[0]) * 1.04,  # 4% target
            confidence=sig.get('score', 70),
            reasoning=f"{signal_type}: {sig}",
            metadata=sig
        )
        
        # Simulate trade using BaseDetector
        detector = SelloffRallyDetector()  # Use as simulator
        trade = detector.simulate_trade(signal, data, 0)
        trades.append(trade)
    
    return trades
```

Then in `backtest_date()`:

```python
# After getting squeeze signals
if result.squeeze and result.squeeze.get('details'):
    squeeze_trades = self._convert_signals_to_trades(
        result.squeeze['details'], 'SQUEEZE', date_str, self.symbols
    )
    result.total_trades += len(squeeze_trades)
    result.total_wins += len([t for t in squeeze_trades if t.outcome == 'WIN'])
    result.total_losses += len([t for t in squeeze_trades if t.outcome == 'LOSS'])
    result.total_pnl += sum(t.pnl_pct for t in squeeze_trades)
```

---

## 🎯 RESULT

After fix:
- ✅ ALL detectors generate trades
- ✅ All trades aggregated in `DailyBacktestResult`
- ✅ Full pipeline backtest with win rates, P&L per detector type
- ✅ No more ignoring 6 out of 7 detectors!

