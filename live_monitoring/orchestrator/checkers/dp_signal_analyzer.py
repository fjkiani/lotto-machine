"""
DP Signal Analyzer — Pure signal analysis logic.

Extracted from dp_divergence_checker.py. Contains:
- DP bias calculation (volume-weighted support/resistance)
- Confluence signal generation (89.8% WR proven edge)
- Options divergence detection (contrarian edge)
- dp_learning.db stats reader

All functions are pure (no side effects beyond logging).
Testable in isolation with 5-10 lines of pytest.
"""

import logging
import sqlite3
from typing import List, Dict, Optional, Tuple

from .dp_signal_models import DPDivergenceSignal, DP_SIGNAL_CONFIG

logger = logging.getLogger(__name__)


def calculate_dp_bias(
    levels: List[Dict],
    current_price: float,
    config: Dict = None,
) -> Tuple[str, float, Optional[Dict]]:
    """
    Calculate DP bias based on support/resistance volume.

    Args:
        levels: List of DP level dicts (keys: 'level', 'volume')
        current_price: Current market price
        config: Override config (defaults to DP_SIGNAL_CONFIG)

    Returns:
        (bias: str, strength: float, nearest_level: Optional[Dict])
    """
    cfg = config or DP_SIGNAL_CONFIG
    support_vol = 0
    resistance_vol = 0
    nearest_level = None
    min_distance = float('inf')

    for level in levels[:50]:  # Top 50 levels
        level_price = float(level.get('level', 0))
        vol = int(level.get('volume', 0))

        if vol < cfg['min_dp_volume']:
            continue

        distance = abs(current_price - level_price) / current_price

        # Track nearest level
        if distance < min_distance and distance < cfg['max_distance_pct'] / 100:
            min_distance = distance
            nearest_level = level

        if level_price < current_price:
            support_vol += vol
        else:
            resistance_vol += vol

    total_vol = support_vol + resistance_vol
    if total_vol == 0:
        return 'NEUTRAL', 0.5, None

    support_pct = support_vol / total_vol

    if support_pct > 0.55:
        return 'BULLISH', support_pct, nearest_level
    elif support_pct < 0.45:
        return 'BEARISH', 1 - support_pct, nearest_level
    else:
        return 'NEUTRAL', 0.5, nearest_level


def generate_confluence_signal(
    symbol: str,
    current_price: float,
    dp_bias: str,
    dp_strength: float,
    nearest_level: Optional[Dict],
    config: Dict = None,
) -> Optional[DPDivergenceSignal]:
    """
    Generate a DP CONFLUENCE signal (89.8% WR strategy).

    This is the PROVEN edge - trading WITH DP levels.
    """
    cfg = config or DP_SIGNAL_CONFIG

    if not nearest_level:
        return None

    level_price = float(nearest_level.get('level', 0))
    level_vol = int(nearest_level.get('volume', 0))
    distance_pct = abs(current_price - level_price) / current_price * 100

    # Only signal when approaching a level
    if distance_pct > 0.3:
        return None

    # Determine direction based on DP bias
    if dp_bias == 'BULLISH':
        direction = 'LONG'
        reasoning = f"DP CONFLUENCE: Price near support ${level_price:.2f} ({level_vol:,} shares). 89.8% bounce rate proven."
    else:
        direction = 'SHORT'
        reasoning = f"DP CONFLUENCE: Price near resistance ${level_price:.2f} ({level_vol:,} shares). 89.8% rejection rate proven."

    # Calculate confidence based on DP strength
    base_confidence = 75  # High base confidence (proven edge)
    strength_boost = int((dp_strength - 0.5) * 40)  # +0-20 for strong bias
    confidence = min(95, base_confidence + strength_boost)

    return DPDivergenceSignal(
        symbol=symbol,
        direction=direction,
        signal_type='DP_CONFLUENCE',
        confidence=confidence,
        entry_price=current_price,
        stop_pct=cfg['stop_pct'],
        target_pct=cfg['target_pct'],
        reasoning=reasoning,
        dp_bias=dp_bias,
        dp_strength=dp_strength,
        has_divergence=False
    )


def check_options_divergence(
    symbol: str,
    current_price: float,
    dp_bias: str,
    dp_strength: float,
    nearest_level: Optional[Dict],
    options_client=None,
    config: Dict = None,
) -> Optional[DPDivergenceSignal]:
    """
    Check for OPTIONS DIVERGENCE signal (contrarian edge).

    When Options and DP disagree, the DIVERGENCE is the edge:
    - Options BULLISH + DP BEARISH = LONG (smart money accumulating)
    - Options BEARISH + DP BULLISH = SHORT (over-crowded longs)
    """
    cfg = config or DP_SIGNAL_CONFIG

    if not options_client:
        return None

    try:
        # Get options sentiment
        sentiment = options_client.get_market_sentiment(symbol)
        if not sentiment:
            return None

        pc_ratio = sentiment.get('put_call_ratio', 1.0)

        # Determine options bias
        if pc_ratio < 0.7:
            options_bias = 'BULLISH'
        elif pc_ratio > 1.3:
            options_bias = 'BEARISH'
        else:
            options_bias = 'NEUTRAL'

        # Check for DIVERGENCE
        if options_bias == dp_bias or options_bias == 'NEUTRAL':
            return None  # No divergence

        # DIVERGENCE DETECTED!
        # Options BULLISH + DP BEARISH = LONG (smart money sees something)
        # Options BEARISH + DP BULLISH = SHORT (over-crowded, squeeze risk)

        if options_bias == 'BULLISH' and dp_bias == 'BEARISH':
            direction = 'LONG'
            reasoning = f"OPTIONS DIVERGENCE: Options bullish (P/C {pc_ratio:.2f}) but DP bearish. Smart money accumulating!"
        elif options_bias == 'BEARISH' and dp_bias == 'BULLISH':
            direction = 'SHORT'
            reasoning = f"OPTIONS DIVERGENCE: Options bearish (P/C {pc_ratio:.2f}) but DP bullish. Crowded longs, reversal risk!"
        else:
            return None

        # Divergence signals get lower confidence (50% WR base)
        confidence = 65 + int((dp_strength - 0.5) * 20)

        return DPDivergenceSignal(
            symbol=symbol,
            direction=direction,
            signal_type='OPTIONS_DIVERGENCE',
            confidence=confidence,
            entry_price=current_price,
            stop_pct=cfg['divergence_stop_pct'],
            target_pct=cfg['divergence_target_pct'],
            reasoning=reasoning,
            dp_bias=dp_bias,
            options_bias=options_bias,
            dp_strength=dp_strength,
            has_divergence=True
        )

    except Exception as e:
        logger.debug(f"Error checking options divergence for {symbol}: {e}")
        return None


def get_dp_learning_stats(db_path: str = 'data/dp_learning.db') -> Dict:
    """
    Get statistics from dp_learning.db to show proven edge.

    Returns:
        Dict with win_rate, total, bounces, breaks, breakeven_rr
    """
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()

        cursor.execute('''
            SELECT outcome, COUNT(*) 
            FROM dp_interactions 
            WHERE outcome IN ('BOUNCE', 'BREAK')
            GROUP BY outcome
        ''')

        results = dict(cursor.fetchall())
        bounces = results.get('BOUNCE', 0)
        breaks = results.get('BREAK', 0)
        total = bounces + breaks

        conn.close()

        if total == 0:
            return {'win_rate': 0, 'total': 0, 'bounces': 0, 'breaks': 0}

        return {
            'win_rate': bounces / total * 100,
            'total': total,
            'bounces': bounces,
            'breaks': breaks,
            'breakeven_rr': breaks / bounces if bounces > 0 else 0
        }

    except Exception as e:
        logger.error(f"Error getting DP learning stats: {e}")
        return {'win_rate': 0, 'total': 0, 'bounces': 0, 'breaks': 0}
