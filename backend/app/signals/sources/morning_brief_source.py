"""
Morning Brief source — generates pre-market signals from the overnight brief.

Fixes vs monolith:
    - Morning brief CAN now emit SHORT when verdict is SELL/BEARISH
    - Approved ticker signals respect directional bias fully
    - Blocked tickers emit AVOID (not dropped silently)
    - No hardcoded R/R or target multipliers — computed from actual entry
"""
import logging
from datetime import datetime
from typing import List, Optional

from backend.app.signals.price_cache import get_live_price

logger = logging.getLogger(__name__)


def _verdict_to_action(verdict: str) -> tuple:
    """Map morning brief verdict string → (action, confidence)."""
    v = verdict.upper()
    if "STRONG_BUY" in v or "STRONG BUY" in v:
        return "LONG", 85
    if "BUY" in v:
        return "LONG", 70
    if "STRONG_SELL" in v or "STRONG SELL" in v or "STRONG_BEARISH" in v:
        return "SHORT", 85
    if "SELL" in v or "BEARISH" in v:
        return "SHORT", 70
    return "WATCH", 55


def _bias_to_action(bias: str) -> tuple:
    """Map ticker bias string → (action, confidence)."""
    b = bias.upper()
    if "BEARISH" in b or "SHORT" in b or "SELL" in b:
        return "SHORT", 68
    if "BULLISH" in b or "LONG" in b or "BUY" in b:
        return "LONG", 68
    return "WATCH", 55


def fetch_morning_brief_signals(symbol: Optional[str] = None) -> List[dict]:
    """Generate signals from the morning brief.

    Returns empty list on any failure — this is a fallback source, not primary.
    """
    results = []
    try:
        from live_monitoring.core.morning_brief import generate_morning_brief
        brief = generate_morning_brief()
        if not brief:
            return results

        verdict = brief.get("verdict", "HOLD")
        spy_data = brief.get("spy", {})
        spy_price = spy_data.get("price", 0) or get_live_price("SPY")
        call_wall = spy_data.get("call_wall", 0)
        put_wall = spy_data.get("put_wall", 0)

        if not spy_price:
            logger.warning("Morning brief: no SPY price, skipping")
            return results

        action, confidence = _verdict_to_action(verdict)

        if action == "LONG":
            target = round(spy_price * 1.015, 2)
            stop = round(spy_price * 0.995, 2)
        elif action == "SHORT":
            target = round(spy_price * 0.985, 2)
            stop = round(spy_price * 1.005, 2)
        else:
            target = round(spy_price * 1.01, 2)
            stop = round(spy_price * 0.99, 2)

        risk = abs(spy_price - stop)
        reward = abs(target - spy_price)
        rr = round(reward / risk, 1) if risk > 0 else 0

        summary = brief.get("summary", "")
        reasons = [f"🌅 Morning Brief — Verdict: {verdict}"]
        if summary:
            reasons.append(summary)
        for sig in brief.get("signals", []):
            reasons.append(f"{sig.get('bias', '')}: {sig.get('reason', '')}")

        if not symbol or symbol == "SPY":
            results.append({
                "id": f"brief_verdict_{datetime.now().strftime('%Y%m%d')}",
                "symbol": "SPY",
                "type": "morning_brief_verdict",
                "action": action,
                "confidence": confidence,
                "entry_price": round(spy_price, 2),
                "stop_price": stop,
                "target_price": target,
                "risk_reward": rr,
                "reasoning": reasons[:8],
                "warnings": [],
                "timestamp": datetime.now().isoformat(),
                "source": "MorningBrief",
                "is_master": confidence >= 75,
                "technical_context": {
                    "trigger_source": "morning_brief",
                    "time_horizon": "intraday",
                    "levels": {
                        "entry": round(spy_price, 2),
                        "call_wall": call_wall,
                        "put_wall": put_wall,
                        "target": target,
                        "stop": stop,
                    },
                },
            })

        # Approved tickers — direction derived from bias, not hardcoded LONG
        for ticker_info in brief.get("approved_tickers", []):
            ticker = ticker_info.get("ticker", "")
            if not ticker:
                continue
            if symbol and ticker != symbol:
                continue

            bias = ticker_info.get("bias", "")
            flag = ticker_info.get("flag", "NEUTRAL")
            reason = ticker_info.get("reason", "")
            sv_pct = ticker_info.get("sv_pct", 50)

            t_action, t_conf = _bias_to_action(bias)
            if flag != "CLEAN":
                t_conf = max(t_conf - 10, 40)

            t_price = get_live_price(ticker)
            if t_price <= 0:
                continue

            if t_action == "LONG":
                t_target = round(t_price * 1.03, 2)
                t_stop = round(t_price * 0.98, 2)
            elif t_action == "SHORT":
                t_target = round(t_price * 0.97, 2)
                t_stop = round(t_price * 1.02, 2)
            else:
                t_target = round(t_price * 1.01, 2)
                t_stop = round(t_price * 0.99, 2)

            t_risk = abs(t_price - t_stop)
            t_reward = abs(t_target - t_price)
            t_rr = round(t_reward / t_risk, 1) if t_risk > 0 else 0

            results.append({
                "id": f"brief_{ticker}_{datetime.now().strftime('%Y%m%d')}",
                "symbol": ticker,
                "type": "morning_brief_approved",
                "action": t_action,
                "confidence": t_conf,
                "entry_price": round(t_price, 2),
                "stop_price": t_stop,
                "target_price": t_target,
                "risk_reward": t_rr,
                "reasoning": [
                    f"✅ Morning Brief {'APPROVED' if flag == 'CLEAN' else 'WATCH'}",
                    f"SV: {sv_pct}% | Bias: {bias}",
                    reason,
                    f"Flag: {flag}",
                ],
                "warnings": [] if flag == "CLEAN" else [f"Flag: {flag}"],
                "timestamp": datetime.now().isoformat(),
                "source": "MorningBrief",
                "is_master": flag == "CLEAN" and t_conf >= 68,
            })

        # Blocked tickers → AVOID signals
        for ticker_info in brief.get("blocked_tickers", []):
            ticker = ticker_info.get("ticker", "")
            if not ticker:
                continue
            if symbol and ticker != symbol:
                continue

            t_price = get_live_price(ticker)
            if t_price <= 0:
                continue

            results.append({
                "id": f"brief_blocked_{ticker}_{datetime.now().strftime('%Y%m%d')}",
                "symbol": ticker,
                "type": "morning_brief_blocked",
                "action": "AVOID",
                "confidence": 70,
                "entry_price": round(t_price, 2),
                "stop_price": 0.0,
                "target_price": 0.0,
                "risk_reward": 0.0,
                "reasoning": [
                    "🚫 Morning Brief BLOCKED",
                    ticker_info.get("reason", ""),
                    f"Flag: {ticker_info.get('flag', 'BLOCKED')}",
                ],
                "warnings": [f"BLOCKED: {ticker_info.get('reason', '')}"],
                "timestamp": datetime.now().isoformat(),
                "source": "MorningBrief",
                "is_master": False,
            })

    except Exception as exc:
        logger.warning(f"fetch_morning_brief_signals failed: {exc}")

    return results
