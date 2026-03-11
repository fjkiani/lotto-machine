"""
Technical Analysis Consensus API

GET /ta/{symbol}/consensus  → multi-indicator oversold/overbought consensus
"""

import logging
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional

logger = logging.getLogger(__name__)
router = APIRouter()


class IndicatorValue(BaseModel):
    name: str
    value: float
    signal: str  # "OVERSOLD", "OVERBOUGHT", "NEUTRAL", "BEARISH", "BULLISH"
    category: str  # "momentum", "volatility", "trend"


class TAConsensusResponse(BaseModel):
    symbol: str
    indicators: list[IndicatorValue]
    oversold_count: int
    total_indicators: int
    consensus: str  # "OVERSOLD", "OVERBOUGHT", "NEUTRAL", "MIXED"
    bb_squeeze: bool
    above_ichimoku_cloud: bool
    narrative: str


@router.get("/ta/{symbol}/consensus", response_model=TAConsensusResponse)
async def get_ta_consensus(symbol: str):
    """Get multi-indicator technical analysis consensus."""
    try:
        import ta
        import yfinance as yf

        hist = yf.Ticker(symbol.upper()).history(period="1y")
        if hist.empty:
            raise HTTPException(status_code=404, detail=f"No price data for {symbol}")

        indicators = []

        # ── Momentum ──
        rsi = ta.momentum.RSIIndicator(hist['Close']).rsi().iloc[-1]
        indicators.append(IndicatorValue(
            name="RSI(14)", value=round(rsi, 1), category="momentum",
            signal="OVERSOLD" if rsi < 30 else "OVERBOUGHT" if rsi > 70 else "NEUTRAL",
        ))

        stoch = ta.momentum.StochasticOscillator(hist['High'], hist['Low'], hist['Close']).stoch().iloc[-1]
        indicators.append(IndicatorValue(
            name="Stochastic %K", value=round(stoch, 1), category="momentum",
            signal="OVERSOLD" if stoch < 20 else "OVERBOUGHT" if stoch > 80 else "NEUTRAL",
        ))

        wr = ta.momentum.WilliamsRIndicator(hist['High'], hist['Low'], hist['Close']).williams_r().iloc[-1]
        indicators.append(IndicatorValue(
            name="Williams %R", value=round(wr, 1), category="momentum",
            signal="OVERSOLD" if wr < -80 else "OVERBOUGHT" if wr > -20 else "NEUTRAL",
        ))

        macd_hist = ta.trend.MACD(hist['Close']).macd_diff().iloc[-1]
        indicators.append(IndicatorValue(
            name="MACD Hist", value=round(macd_hist, 2), category="momentum",
            signal="BEARISH" if macd_hist < 0 else "BULLISH",
        ))

        # ── Volatility ──
        atr_val = ta.volatility.AverageTrueRange(hist['High'], hist['Low'], hist['Close']).average_true_range().iloc[-1]
        indicators.append(IndicatorValue(
            name="ATR(14)", value=round(atr_val, 2), category="volatility",
            signal="NEUTRAL",
        ))

        bb = ta.volatility.BollingerBands(hist['Close'])
        bb_upper = bb.bollinger_hband().iloc[-1]
        bb_lower = bb.bollinger_lband().iloc[-1]
        bb_pct = (hist['Close'].iloc[-1] - bb_lower) / (bb_upper - bb_lower) if bb_upper != bb_lower else 0.5
        indicators.append(IndicatorValue(
            name="BB %B", value=round(bb_pct, 2), category="volatility",
            signal="OVERSOLD" if bb_pct < 0.2 else "OVERBOUGHT" if bb_pct > 0.8 else "NEUTRAL",
        ))

        # ── Trend ──
        adx_val = ta.trend.ADXIndicator(hist['High'], hist['Low'], hist['Close']).adx().iloc[-1]
        indicators.append(IndicatorValue(
            name="ADX", value=round(adx_val, 1), category="trend",
            signal="BULLISH" if adx_val > 25 else "NEUTRAL",
        ))

        cci = ta.trend.CCIIndicator(hist['High'], hist['Low'], hist['Close']).cci().iloc[-1]
        indicators.append(IndicatorValue(
            name="CCI", value=round(cci, 1), category="trend",
            signal="OVERSOLD" if cci < -100 else "OVERBOUGHT" if cci > 100 else "NEUTRAL",
        ))

        # ── Squeeze detection ──
        kc = ta.volatility.KeltnerChannel(hist['High'], hist['Low'], hist['Close'])
        kc_upper = kc.keltner_channel_hband().iloc[-1]
        kc_lower = kc.keltner_channel_lband().iloc[-1]
        bb_squeeze = bb_upper < kc_upper and bb_lower > kc_lower

        # ── Ichimoku ──
        ichi = ta.trend.IchimokuIndicator(hist['High'], hist['Low'])
        span_a = ichi.ichimoku_a().iloc[-1]
        span_b = ichi.ichimoku_b().iloc[-1]
        above_cloud = float(hist['Close'].iloc[-1]) > max(span_a, span_b)

        # ── Consensus ──
        oversold_count = sum(1 for ind in indicators if ind.signal == "OVERSOLD")
        overbought_count = sum(1 for ind in indicators if ind.signal == "OVERBOUGHT")

        if oversold_count >= 3:
            consensus = "OVERSOLD"
        elif overbought_count >= 3:
            consensus = "OVERBOUGHT"
        elif oversold_count >= 1 or overbought_count >= 1:
            consensus = "MIXED"
        else:
            consensus = "NEUTRAL"

        # ── Narrative ──
        parts = [f"TA {symbol.upper()}: {consensus}"]
        parts.append(f"{oversold_count}/{len(indicators)} oversold")
        if bb_squeeze:
            parts.append("BB SQUEEZE ACTIVE 🔥")
        parts.append(f"Ichimoku: {'above ☁️' if above_cloud else 'below ☁️'}")
        narrative = " | ".join(parts)

        return TAConsensusResponse(
            symbol=symbol.upper(),
            indicators=indicators,
            oversold_count=oversold_count,
            total_indicators=len(indicators),
            consensus=consensus,
            bb_squeeze=bb_squeeze,
            above_ichimoku_cloud=above_cloud,
            narrative=narrative,
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"TA consensus error: {e}")
        raise HTTPException(status_code=500, detail=str(e))
