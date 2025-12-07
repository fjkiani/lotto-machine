"""
Institutional Data Loader

Fetches institutional context (dark pool, max pain, crypto correlation).
Isolates data fetching from narrative logic.
"""
import logging
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)


def load_institutional_context(
    symbol: str,
    date: str,
    crypto_regime: Optional[str] = None
) -> Dict[str, Any]:
    """
    Load institutional context for a ticker on a specific date.
    
    Args:
        symbol: Ticker symbol
        date: Date string in 'YYYY-MM-DD' format
        crypto_regime: Optional crypto regime to include
        
    Returns:
        Dictionary with institutional data:
        - dark_pool: {pct: float, ...}
        - lit_exchange: {pct: float, ...}
        - max_pain: float or None
        - crypto_regime: str
        - has_dp_data: bool
    """
    try:
        from live_monitoring.enrichment.institutional_narrative import (
            load_institutional_context as _load_inst_ctx
        )
        
        ctx = _load_inst_ctx(symbol, date)
        
        # Add crypto regime if provided
        if crypto_regime:
            ctx["crypto_regime"] = crypto_regime
        
        # Flag if we have dark pool data
        dp_pct = ctx.get("dark_pool", {}).get("pct")
        ctx["has_dp_data"] = dp_pct is not None and dp_pct > 0
        
        logger.info(
            "🏦 Institutional context: DP %.1f%%, Max Pain %s, Has DP: %s",
            dp_pct or 0.0,
            ctx.get("max_pain", "N/A"),
            ctx["has_dp_data"]
        )
        
        return ctx
        
    except Exception as e:
        logger.error("Error loading institutional context: %s", e)
        return {
            "dark_pool": {"pct": None},
            "lit_exchange": {"pct": None},
            "max_pain": None,
            "crypto_regime": crypto_regime or "UNKNOWN",
            "has_dp_data": False,
        }


def detect_divergences(
    symbol: str,
    inst_ctx: Dict[str, Any],
    perplexity_narratives: Dict[str, Any]
) -> Dict[str, Any]:
    """
    Detect divergences between institutional data and mainstream narratives.
    
    Args:
        symbol: Ticker symbol
        inst_ctx: Institutional context from load_institutional_context
        perplexity_narratives: Narratives from Perplexity
        
    Returns:
        Dictionary with divergence analysis:
        - detected: List[str] (divergence types)
        - summary: str (narrative summary)
    """
    try:
        from live_monitoring.enrichment.institutional_narrative import (
            DivergenceDetector
        )
        
        detector = DivergenceDetector()
        
        # Extract macro narrative for divergence detection
        macro_text = perplexity_narratives.get("macro", "")
        
        # Get trading date from inst_ctx if available
        trading_date = inst_ctx.get("date", "")
        
        divergences = detector.detect_manipulation(
            symbol=symbol,
            date=trading_date,
            news_narrative=macro_text,
            institutional_data=inst_ctx
        )
        
        logger.info("🔍 Divergences detected: %d", len(divergences))
        
        return {
            "detected": divergences,
            "summary": f"Detected {len(divergences)} institutional divergences"
        }
        
    except Exception as e:
        logger.error("Error detecting divergences: %s", e)
        return {
            "detected": [],
            "summary": "Unable to detect divergences"
        }


def synthesize_institutional_narrative(
    symbol: str,
    inst_ctx: Dict[str, Any],
    divergences: list
) -> str:
    """
    Synthesize institutional-first narrative.
    
    Args:
        symbol: Ticker symbol
        inst_ctx: Institutional context
        divergences: List of detected divergences
        
    Returns:
        Institutional narrative string
    """
    try:
        from live_monitoring.enrichment.institutional_narrative import (
            InstitutionalNarrativeSynthesizer
        )
        
        synthesizer = InstitutionalNarrativeSynthesizer()
        
        # generate_real_narrative returns a dict, not a string
        result = synthesizer.generate_real_narrative(
            symbol=symbol,
            date=inst_ctx.get("date", ""),
            institutional_data=inst_ctx,
            news_narrative="",  # Will be filled by pipeline
            divergences=divergences
        )
        
        narrative_text = result.get("institutional_reality", {}).get("summary", "")
        
        logger.info("📝 Institutional narrative synthesized (%d chars)", len(narrative_text))
        
        return narrative_text
        
    except Exception as e:
        logger.error("Error synthesizing institutional narrative: %s", e)
        return "Unable to synthesize institutional narrative"

