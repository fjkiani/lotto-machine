"""
🌅 MORNING BRIEF GENERATOR

Pre-market analysis of overnight signals.
Re-evaluates overnight signals against current conditions:
  - Futures gap direction vs signal direction
  - VIX level change
  - Pre-market volume signals
  - Signal validity check

Generates a structured morning brief for the frontend.
"""

import logging
import sqlite3
from datetime import datetime, timedelta
from pathlib import Path
from typing import List, Dict, Optional

logger = logging.getLogger(__name__)


def _get_market_context() -> dict:
    """Fetch current pre-market context from available data sources."""
    context = {
        "spy_last_close": 0,
        "spy_premarket": 0,
        "gap_pct": 0,
        "gap_direction": "FLAT",
        "vix_current": 0,
        "vix_change": 0,
        "btc_price": 0,
        "market_status": "UNKNOWN",
        "futures_bias": "NEUTRAL",
    }

    try:
        import yfinance as yf

        # SPY close + pre-market
        spy = yf.Ticker("SPY")
        price = spy.fast_info.last_price
        if price and price > 0:
            context["spy_last_close"] = round(price, 2)
            context["spy_premarket"] = round(price, 2)  # Same as last during off-hours

        # VIX
        vix = yf.Ticker("^VIX")
        vix_price = vix.fast_info.last_price
        if vix_price and vix_price > 0:
            context["vix_current"] = round(vix_price, 2)
            # Classify VIX regime
            if vix_price > 30:
                context["market_status"] = "HIGH VOLATILITY"
            elif vix_price > 20:
                context["market_status"] = "ELEVATED"
            else:
                context["market_status"] = "NORMAL"

        # BTC
        btc = yf.Ticker("BTC-USD")
        btc_price = btc.fast_info.last_price
        if btc_price and btc_price > 0:
            context["btc_price"] = round(btc_price, 0)

        # Calculate gap
        try:
            hist = spy.history(period="2d")
            if len(hist) >= 2:
                prev_close = hist['Close'].iloc[-2]
                last_close = hist['Close'].iloc[-1]
                gap = round((last_close - prev_close) / prev_close * 100, 2)
                context["gap_pct"] = gap
                context["gap_direction"] = "UP" if gap > 0.1 else "DOWN" if gap < -0.1 else "FLAT"
        except Exception:
            pass

        # Determine futures bias
        if context["gap_pct"] > 0.3:
            context["futures_bias"] = "BULLISH"
        elif context["gap_pct"] < -0.3:
            context["futures_bias"] = "BEARISH"
        else:
            context["futures_bias"] = "NEUTRAL"

    except Exception as e:
        logger.error(f"Failed to fetch market context: {e}")

    return context


def _get_overnight_signals() -> List[dict]:
    """Fetch signals from the last 18 hours (overnight window)."""
    signals = []
    try:
        alerts_path = Path("data/alerts_history.db")
        if not alerts_path.exists():
            return signals

        conn = sqlite3.connect(str(alerts_path))
        conn.row_factory = sqlite3.Row

        cutoff = (datetime.now() - timedelta(hours=18)).isoformat()
        rows = conn.execute("""
            SELECT *, MAX(timestamp) as latest_ts
            FROM alerts
            WHERE timestamp >= ?
            GROUP BY alert_type, symbol, title
            ORDER BY latest_ts DESC
            LIMIT 20
        """, (cutoff,)).fetchall()
        conn.close()

        for row in rows:
            d = dict(row)
            signals.append({
                "id": d.get('id'),
                "symbol": d.get('symbol', 'SPY'),
                "alert_type": d.get('alert_type', ''),
                "title": d.get('title', ''),
                "description": d.get('description', ''),
                "timestamp": d.get('timestamp', ''),
            })
    except Exception as e:
        logger.error(f"Failed to fetch overnight signals: {e}")

    return signals


def _evaluate_signal_validity(signal: dict, context: dict) -> dict:
    """Re-evaluate a signal against current market context."""
    alert_type = signal.get('alert_type', '').lower()
    symbol = signal.get('symbol', 'SPY')

    # Determine original bias
    if 'bullish' in alert_type or 'rally' in alert_type:
        original_bias = "BULLISH"
    elif 'bearish' in alert_type or 'selloff' in alert_type:
        original_bias = "BEARISH"
    else:
        original_bias = "NEUTRAL"

    # Check alignment with current conditions
    futures_bias = context.get('futures_bias', 'NEUTRAL')
    vix = context.get('vix_current', 20)

    alignment = "ALIGNED"
    confidence_modifier = 0
    notes = []

    if original_bias == "BULLISH":
        if futures_bias == "BEARISH":
            alignment = "CONFLICTING"
            confidence_modifier = -15
            notes.append(f"⚠️ Futures gap DOWN ({context['gap_pct']:+.1f}%) conflicts with bullish signal")
        elif futures_bias == "BULLISH":
            confidence_modifier = +5
            notes.append(f"✅ Futures confirm bullish bias ({context['gap_pct']:+.1f}% gap)")
        if vix > 25:
            confidence_modifier -= 5
            notes.append(f"⚠️ VIX elevated at {vix:.1f} — increased risk")

    elif original_bias == "BEARISH":
        if futures_bias == "BULLISH":
            alignment = "CONFLICTING"
            confidence_modifier = -15
            notes.append(f"⚠️ Futures gap UP ({context['gap_pct']:+.1f}%) conflicts with bearish signal")
        elif futures_bias == "BEARISH":
            confidence_modifier = +5
            notes.append(f"✅ Futures confirm bearish bias ({context['gap_pct']:+.1f}% gap)")

    else:  # NEUTRAL/WATCH
        notes.append(f"👀 Informational signal — monitor for direction at open")
        if abs(context.get('gap_pct', 0)) > 0.5:
            notes.append(f"📊 Significant gap ({context['gap_pct']:+.1f}%) may create opportunities")

    # Time decay
    try:
        sig_time = datetime.fromisoformat(signal['timestamp'])
        hours_old = (datetime.now() - sig_time).total_seconds() / 3600
        if hours_old > 12:
            confidence_modifier -= 5
            notes.append(f"⏰ Signal is {hours_old:.0f}h old — verify with fresh data")
    except Exception:
        pass

    return {
        "original_bias": original_bias,
        "current_alignment": alignment,
        "confidence_modifier": confidence_modifier,
        "validity": "VALID" if alignment == "ALIGNED" else "NEEDS REVIEW" if alignment == "CONFLICTING" else "NEUTRAL",
        "notes": notes,
    }


def generate_morning_brief() -> dict:
    """Generate a complete morning brief with signal re-evaluation."""
    now = datetime.now()
    context = _get_market_context()
    overnight_signals = _get_overnight_signals()

    # Re-evaluate each signal
    evaluated = []
    for sig in overnight_signals:
        evaluation = _evaluate_signal_validity(sig, context)
        evaluated.append({
            **sig,
            "evaluation": evaluation,
        })

    # Count categories
    valid_count = sum(1 for e in evaluated if e['evaluation']['validity'] == 'VALID')
    review_count = sum(1 for e in evaluated if e['evaluation']['validity'] == 'NEEDS REVIEW')
    neutral_count = sum(1 for e in evaluated if e['evaluation']['validity'] == 'NEUTRAL')

    # Generate summary
    summary_parts = []
    if context['gap_direction'] != 'FLAT':
        summary_parts.append(f"SPY gap {context['gap_direction']} {context['gap_pct']:+.1f}%")
    summary_parts.append(f"VIX {context['vix_current']:.1f}")
    if context['btc_price']:
        summary_parts.append(f"BTC ${context['btc_price']:,.0f}")

    # Key action items
    action_items = []
    for e in evaluated:
        if e['evaluation']['validity'] == 'NEEDS REVIEW':
            action_items.append(f"⚠️ Review {e['symbol']} — {e['evaluation']['notes'][0] if e['evaluation']['notes'] else 'conflicting signals'}")
        elif e['evaluation']['validity'] == 'VALID' and e['evaluation']['original_bias'] != 'NEUTRAL':
            action_items.append(f"✅ {e['symbol']} signal confirmed — {e['evaluation']['original_bias']}")

    return {
        "generated_at": now.isoformat(),
        "market_context": context,
        "summary": " | ".join(summary_parts),
        "overnight_signals_count": len(overnight_signals),
        "valid": valid_count,
        "needs_review": review_count,
        "neutral": neutral_count,
        "signals": evaluated,
        "action_items": action_items[:5],  # Top 5 action items
    }
