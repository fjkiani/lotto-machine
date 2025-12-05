"""
Narrative Validation Layer

Implements 3 critical fixes from feedback.mdc:
1. Real-time price verification (don't trust predictions)
2. Dark pool fallback logic (when DP data unavailable)
3. Cross-asset validation (Bitcoin crash overrides equity bullish)

These validators ensure narrative engine doesn't make catastrophic calls like:
"BULLISH, HIGH CONVICTION, RISK_ON" when market is actually in selloff mode.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any, Dict, Optional, Tuple

import yfinance as yf

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Data models
# ---------------------------------------------------------------------------

@dataclass
class PriceVerification:
    """Result of real-time price verification"""
    verified: bool
    actual_direction: str  # "BULLISH" | "BEARISH" | "NEUTRAL"
    pct_change: float
    error: Optional[str] = None


@dataclass
class DirectionOverride:
    """Result of cross-asset validation override"""
    override: bool
    new_direction: Optional[str] = None
    new_risk_env: Optional[str] = None
    reason: Optional[str] = None
    severity: str = "MEDIUM"


# ---------------------------------------------------------------------------
# Fix #1: Real-Time Price Verification
# ---------------------------------------------------------------------------

class PriceVerificationEngine:
    """
    Verify narrative predictions against actual price action.
    
    PROBLEM: Engine used "QQQ expected to gap +$9" as fact without checking.
    SOLUTION: Fetch real-time price and verify if prediction matches reality.
    """
    
    def __init__(self):
        self.cache: Dict[str, Dict[str, Any]] = {}
        self.cache_ttl = 300  # 5 min cache
    
    def verify_narrative_with_price(
        self, 
        symbol: str, 
        narrative_direction: str,
        date: Optional[str] = None
    ) -> PriceVerification:
        """
        Verify if narrative direction matches actual price action.
        
        Args:
            symbol: Ticker (SPY, QQQ, etc.)
            narrative_direction: "BULLISH" | "BEARISH" | "NEUTRAL"
            date: Date to verify (defaults to today)
        
        Returns:
            PriceVerification with verified flag and actual direction
        """
        symbol = symbol.upper()
        narrative_direction = narrative_direction.upper()
        
        if date is None:
            date = datetime.now().strftime("%Y-%m-%d")
        
        logger.info(f"🔍 Verifying narrative {narrative_direction} for {symbol} on {date}")
        
        try:
            # Get current price and previous close
            ticker = yf.Ticker(symbol)
            hist = ticker.history(period="5d", interval="1d")
            
            if hist.empty or len(hist) < 2:
                logger.warning(f"⚠️  Insufficient price data for {symbol}")
                return PriceVerification(
                    verified=False,
                    actual_direction="UNKNOWN",
                    pct_change=0.0,
                    error="Insufficient price data"
                )
            
            # Get today's close and previous close
            current_price = float(hist['Close'].iloc[-1])
            prev_close = float(hist['Close'].iloc[-2])
            
            # Calculate actual % change
            pct_change = ((current_price / prev_close) - 1) * 100.0
            
            # Determine actual direction
            if pct_change > 0.5:
                actual_direction = "BULLISH"
            elif pct_change < -0.5:
                actual_direction = "BEARISH"
            else:
                actual_direction = "NEUTRAL"
            
            # Check if narrative matches reality
            verified = True
            error = None
            
            if narrative_direction == "BULLISH" and actual_direction == "BEARISH":
                verified = False
                error = f"Predicted BULLISH, but {symbol} down {pct_change:.2f}%"
            elif narrative_direction == "BEARISH" and actual_direction == "BULLISH":
                verified = False
                error = f"Predicted BEARISH, but {symbol} up {pct_change:.2f}%"
            elif narrative_direction == "BULLISH" and actual_direction == "NEUTRAL":
                verified = False
                error = f"Predicted BULLISH, but {symbol} flat {pct_change:.2f}%"
            
            result = PriceVerification(
                verified=verified,
                actual_direction=actual_direction,
                pct_change=pct_change,
                error=error
            )
            
            if not verified:
                logger.warning(f"❌ Price verification FAILED: {error}")
            else:
                logger.info(f"✅ Price verification PASSED: {symbol} {pct_change:+.2f}% matches {narrative_direction}")
            
            return result
            
        except Exception as e:
            logger.error(f"Error verifying price for {symbol}: {e}")
            return PriceVerification(
                verified=False,
                actual_direction="UNKNOWN",
                pct_change=0.0,
                error=str(e)
            )


# ---------------------------------------------------------------------------
# Fix #2: Dark Pool Fallback Logic
# ---------------------------------------------------------------------------

class DarkPoolFallbackEngine:
    """
    Generate direction when dark pool data unavailable.
    
    PROBLEM: Engine said "no DP data, so BULLISH based on prior strength"
    SOLUTION: Use alternative signals (Bitcoin, PMI, price trend, VIX) to determine direction
    """
    
    def generate_direction_without_dp(
        self,
        symbol: str,
        date: str,
        macro_data: Dict[str, Any],
        cross_asset_data: Dict[str, Any],
        price_action: Dict[str, Any]
    ) -> Tuple[str, str, str]:
        """
        Determine direction without dark pool data.
        
        Args:
            symbol: Ticker
            date: Date
            macro_data: Economic data (PMI, consumer sentiment, etc.)
            cross_asset_data: Bitcoin, VIX, etc.
            price_action: Price trend data
        
        Returns:
            Tuple of (direction, risk_environment, conviction)
        """
        logger.info(f"🔄 Generating direction without DP data for {symbol} on {date}")
        
        risk_score = 0
        reasons = []
        
        # Check Bitcoin (leading indicator)
        btc_10day_change = cross_asset_data.get('btc_10day_change', 0)
        if btc_10day_change < -20:
            risk_score -= 30
            reasons.append(f"BTC down {btc_10day_change:.1f}% in 10 days (forced liquidations)")
        elif btc_10day_change < -10:
            risk_score -= 15
            reasons.append(f"BTC down {btc_10day_change:.1f}% in 10 days (risk-off)")
        elif btc_10day_change > 10:
            risk_score += 15
            reasons.append(f"BTC up {btc_10day_change:.1f}% in 10 days (risk-on)")
        
        # Check PMI misses
        if macro_data.get('pmi_services_miss', False):
            risk_score -= 10
            reasons.append("PMI Services missed expectations")
        if macro_data.get('pmi_manufacturing_miss', False):
            risk_score -= 10
            reasons.append("PMI Manufacturing missed expectations")
        
        # Check consumer sentiment
        consumer_sentiment = macro_data.get('consumer_sentiment', None)
        if consumer_sentiment and consumer_sentiment < 55:
            risk_score -= 10
            reasons.append(f"Consumer sentiment low ({consumer_sentiment})")
        
        # Check price trend (3-day)
        price_trend = price_action.get('spy_3day_trend', 'NEUTRAL')
        if price_trend == 'DOWN':
            risk_score -= 20
            reasons.append(f"{symbol} 3-day trend DOWN")
        elif price_trend == 'UP':
            risk_score += 15
            reasons.append(f"{symbol} 3-day trend UP")
        
        # Check VIX spike
        vix = cross_asset_data.get('vix', 0)
        if vix > 25:
            risk_score -= 20
            reasons.append(f"VIX spike ({vix:.1f}) = fear")
        elif vix < 15:
            risk_score += 10
            reasons.append(f"VIX low ({vix:.1f}) = complacency")
        
        # Check Bitcoin consecutive losses (5+ days = capitulation)
        btc_losses = cross_asset_data.get('btc_consecutive_losses', 0)
        if btc_losses >= 5:
            risk_score -= 20
            reasons.append(f"BTC {btc_losses} consecutive red days (capitulation)")
        
        # Determine direction based on risk_score
        if risk_score < -30:
            direction = 'BEARISH'
            risk_env = 'RISK_OFF'
            conviction = 'HIGH'
        elif risk_score < -10:
            direction = 'NEUTRAL'
            risk_env = 'NEUTRAL'
            conviction = 'MEDIUM'
        elif risk_score > 20:
            direction = 'BULLISH'
            risk_env = 'RISK_ON'
            conviction = 'HIGH'
        else:
            direction = 'NEUTRAL'
            risk_env = 'NEUTRAL'
            conviction = 'LOW'
        
        logger.info(f"📊 Fallback direction: {direction} ({risk_env}, {conviction})")
        logger.info(f"   Risk score: {risk_score}")
        for reason in reasons:
            logger.info(f"   - {reason}")
        
        return direction, risk_env, conviction


# ---------------------------------------------------------------------------
# Fix #3: Cross-Asset Validation
# ---------------------------------------------------------------------------

class CrossAssetValidator:
    """
    Validate narrative against cross-asset signals.
    
    PROBLEM: Engine called "BULLISH" when Bitcoin down -24% (forced liquidations)
    SOLUTION: Bitcoin crash overrides equity bullish, VIX spike overrides bullish
    """
    
    def validate_narrative_cross_asset(
        self,
        equity_direction: str,
        equity_risk_env: str,
        cross_asset_data: Dict[str, Any]
    ) -> DirectionOverride:
        """
        Check if cross-asset signals override equity narrative.
        
        Args:
            equity_direction: Equity narrative direction
            equity_risk_env: Equity risk environment
            cross_asset_data: Bitcoin, VIX, etc.
        
        Returns:
            DirectionOverride with override flag and new direction if needed
        """
        logger.info(f"🔗 Validating narrative with cross-asset data")
        logger.info(f"   Equity: {equity_direction} / {equity_risk_env}")
        
        overrides = []
        
        # Override #1: Bitcoin crash (>20% drawdown from high)
        btc_drawdown = cross_asset_data.get('btc_drawdown_from_high', 0)
        if btc_drawdown > 20:
            if equity_direction == 'BULLISH':
                overrides.append(DirectionOverride(
                    override=True,
                    new_direction='NEUTRAL',
                    new_risk_env='RISK_OFF',
                    reason=f"BTC down {btc_drawdown:.1f}% from high = forced liquidations, not risk-on",
                    severity='CRITICAL'
                ))
        
        # Override #2: VIX spike (>25 = fear dominates)
        vix = cross_asset_data.get('vix', 0)
        if vix > 25 and equity_direction == 'BULLISH':
            overrides.append(DirectionOverride(
                override=True,
                new_direction='BEARISH',
                new_risk_env='RISK_OFF',
                reason=f"VIX at {vix:.1f} = fear, not bullish environment",
                severity='HIGH'
            ))
        
        # Override #3: Bitcoin 5+ day losing streak (capitulation)
        btc_losses = cross_asset_data.get('btc_consecutive_losses', 0)
        if btc_losses >= 5:
            if equity_direction == 'BULLISH':
                overrides.append(DirectionOverride(
                    override=True,
                    new_direction='BEARISH',
                    new_risk_env='RISK_OFF',
                    reason=f"BTC {btc_losses} consecutive red days = capitulation, not rally",
                    severity='HIGH'
                ))
        
        # Override #4: Bitcoin + Equities simultaneous drop (liquidity crisis)
        btc_change = cross_asset_data.get('btc_1day_change', 0)
        spy_change = cross_asset_data.get('spy_1day_change', 0)
        if btc_change < -3 and spy_change < -2:
            if equity_direction == 'BULLISH' or equity_risk_env == 'RISK_ON':
                overrides.append(DirectionOverride(
                    override=True,
                    new_direction='BEARISH',
                    new_risk_env='RISK_OFF',
                    reason=f"BTC {btc_change:.1f}% + SPY {spy_change:.1f}% = forced liquidations across assets",
                    severity='CRITICAL'
                ))
        
        # If multiple overrides, take most severe
        if overrides:
            # Sort by severity: CRITICAL > HIGH > MEDIUM
            severity_order = {'CRITICAL': 0, 'HIGH': 1, 'MEDIUM': 2}
            overrides.sort(key=lambda x: severity_order.get(x.severity, 99))
            
            override = overrides[0]
            logger.warning(f"⚠️  OVERRIDE TRIGGERED: {override.reason}")
            return override
        
        logger.info("✅ No cross-asset overrides")
        return DirectionOverride(override=False)


# ---------------------------------------------------------------------------
# Validation orchestrator
# ---------------------------------------------------------------------------

class NarrativeValidationOrchestrator:
    """
    Orchestrates all 3 validation engines.
    
    Usage:
        validator = NarrativeValidationOrchestrator()
        validated_narrative = validator.validate_narrative(
            symbol, date, narrative_direction, narrative_risk_env,
            macro_data, cross_asset_data, price_action, has_dp_data
        )
    """
    
    def __init__(self):
        self.price_verifier = PriceVerificationEngine()
        self.dp_fallback = DarkPoolFallbackEngine()
        self.cross_asset_validator = CrossAssetValidator()
    
    def validate_narrative(
        self,
        symbol: str,
        date: str,
        narrative_direction: str,
        narrative_risk_env: str,
        narrative_conviction: str,
        macro_data: Dict[str, Any],
        cross_asset_data: Dict[str, Any],
        price_action: Dict[str, Any],
        has_dp_data: bool = True
    ) -> Dict[str, Any]:
        """
        Full validation pipeline.
        
        Returns:
            Dict with:
            - final_direction
            - final_risk_env
            - final_conviction
            - validation_errors (list)
            - validation_warnings (list)
            - overrides_applied (list)
        """
        logger.info("=" * 80)
        logger.info(f"🎯 NARRATIVE VALIDATION STARTING: {symbol} on {date}")
        logger.info("=" * 80)
        
        errors = []
        warnings = []
        overrides = []
        
        final_direction = narrative_direction
        final_risk_env = narrative_risk_env
        final_conviction = narrative_conviction
        
        # Step 1: Price verification (always run)
        price_check = self.price_verifier.verify_narrative_with_price(
            symbol, narrative_direction, date
        )
        
        if not price_check.verified:
            errors.append(price_check.error)
            # Override with actual direction
            final_direction = price_check.actual_direction
            overrides.append({
                'type': 'PRICE_VERIFICATION_OVERRIDE',
                'reason': price_check.error,
                'old_direction': narrative_direction,
                'new_direction': final_direction
            })
        
        # Step 2: Dark pool fallback (if no DP data)
        if not has_dp_data:
            warnings.append("No dark pool data available - using fallback logic")
            fallback_dir, fallback_risk, fallback_conv = self.dp_fallback.generate_direction_without_dp(
                symbol, date, macro_data, cross_asset_data, price_action
            )
            
            # If fallback contradicts narrative, override
            if fallback_dir != final_direction:
                overrides.append({
                    'type': 'DARK_POOL_FALLBACK_OVERRIDE',
                    'reason': f"No DP data, fallback logic says {fallback_dir}",
                    'old_direction': final_direction,
                    'new_direction': fallback_dir
                })
                final_direction = fallback_dir
                final_risk_env = fallback_risk
                final_conviction = fallback_conv
        
        # Step 3: Cross-asset validation
        cross_asset_override = self.cross_asset_validator.validate_narrative_cross_asset(
            final_direction, final_risk_env, cross_asset_data
        )
        
        if cross_asset_override.override:
            overrides.append({
                'type': 'CROSS_ASSET_OVERRIDE',
                'reason': cross_asset_override.reason,
                'severity': cross_asset_override.severity,
                'old_direction': final_direction,
                'new_direction': cross_asset_override.new_direction
            })
            final_direction = cross_asset_override.new_direction or final_direction
            final_risk_env = cross_asset_override.new_risk_env or final_risk_env
            # Lower conviction if overridden
            if final_conviction == 'HIGH':
                final_conviction = 'MEDIUM'
        
        # Log final results
        logger.info("=" * 80)
        logger.info("🎯 NARRATIVE VALIDATION COMPLETE")
        logger.info("=" * 80)
        logger.info(f"Original: {narrative_direction} / {narrative_risk_env} / {narrative_conviction}")
        logger.info(f"Final:    {final_direction} / {final_risk_env} / {final_conviction}")
        
        if overrides:
            logger.info(f"Overrides applied: {len(overrides)}")
            for ov in overrides:
                logger.info(f"  - {ov['type']}: {ov['reason']}")
        
        if errors:
            logger.warning(f"Validation errors: {len(errors)}")
            for err in errors:
                logger.warning(f"  - {err}")
        
        if warnings:
            logger.warning(f"Validation warnings: {len(warnings)}")
            for warn in warnings:
                logger.warning(f"  - {warn}")
        
        return {
            'final_direction': final_direction,
            'final_risk_env': final_risk_env,
            'final_conviction': final_conviction,
            'validation_errors': errors,
            'validation_warnings': warnings,
            'overrides_applied': overrides,
            'price_verification': {
                'verified': price_check.verified,
                'actual_direction': price_check.actual_direction,
                'pct_change': price_check.pct_change
            }
        }


def _demo() -> None:
    """
    Test validation with Nov 20-21 scenario
    """
    import json
    
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
    
    # Nov 20-21 scenario: Market selloff, BTC crash, but narrative said "BULLISH"
    validator = NarrativeValidationOrchestrator()
    
    # Mock data for Nov 21
    result = validator.validate_narrative(
        symbol='SPY',
        date='2025-11-21',
        narrative_direction='BULLISH',
        narrative_risk_env='RISK_ON',
        narrative_conviction='HIGH',
        macro_data={
            'pmi_services_miss': True,
            'pmi_manufacturing_miss': True,
            'consumer_sentiment': 51.0
        },
        cross_asset_data={
            'btc_10day_change': -24.0,
            'btc_drawdown_from_high': 24.0,
            'btc_consecutive_losses': 5,
            'btc_1day_change': -1.32,
            'spy_1day_change': -1.5,
            'vix': 18.5
        },
        price_action={
            'spy_3day_trend': 'DOWN'
        },
        has_dp_data=False
    )
    
    print("\n" + "=" * 80)
    print("VALIDATION RESULT:")
    print("=" * 80)
    print(json.dumps(result, indent=2))


if __name__ == '__main__':
    _demo()

