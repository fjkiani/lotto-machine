"""
Monitor source — pulls live signals from the UnifiedMonitor signal buffer.
These are selloff/rally signals generated in real time by the intraday guardian.
"""
import logging
from typing import List, Optional

logger = logging.getLogger(__name__)


def fetch_monitor_signals(
    monitor,
    symbol: Optional[str] = None,
    signal_type: Optional[str] = None,
    master_only: bool = False,
) -> List[dict]:
    """Extract active signals from the live monitor buffer.

    Returns an empty list if the monitor isn't active or has no signals.
    Never raises.
    """
    results = []
    try:
        if not monitor or not hasattr(monitor, "get_active_signals"):
            return results

        raw_signals = monitor.get_active_signals()
        for signal in raw_signals:
            if symbol and signal.symbol != symbol:
                continue
            if signal_type and signal.signal_type.value != signal_type:
                continue
            if master_only and not signal.is_master_signal:
                continue

            results.append({
                "id": f"{signal.symbol}_{signal.signal_type.value}_{signal.timestamp.isoformat()}",
                "symbol": signal.symbol,
                "type": signal.signal_type.value,
                "action": signal.action.value,
                "confidence": round(signal.confidence * 100, 1),
                "entry_price": signal.entry_price,
                "stop_price": signal.stop_price,
                "target_price": signal.target_price,
                "risk_reward": signal.risk_reward_ratio,
                "reasoning": signal.supporting_factors,
                "warnings": signal.warnings,
                "timestamp": signal.timestamp.isoformat(),
                "source": "LiveMonitor",
                "is_master": signal.is_master_signal,
                "position_size_pct": signal.position_size_pct,
            })
    except Exception as exc:
        logger.warning(f"fetch_monitor_signals error: {exc}")

    return results
