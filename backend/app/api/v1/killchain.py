"""
🐺 Kill Chain API Endpoints

Exposes the Kill Chain Engine's 5-layer intelligence scan to the frontend.
Layers: FedWatch | Dark Pool (Stockgrid) | COT (CFTC) | GEX (CBOE) | 13F (SEC EDGAR)
"""

import logging
import sys
from pathlib import Path
from datetime import datetime
from typing import Optional
from fastapi import APIRouter, HTTPException, Query

# Add project root to path
project_root = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(project_root))

logger = logging.getLogger(__name__)
router = APIRouter()

# Lazy-init engine (heavy imports, shared instance)
_engine = None


def _get_engine():
    global _engine
    if _engine is None:
        try:
            from live_monitoring.enrichment.apis.kill_chain_engine import KillChainEngine
            _engine = KillChainEngine()
            logger.info(f"🐺 KillChainEngine initialized: {len(_engine.registry.available_layers)} layers")
        except Exception as e:
            logger.error(f"Failed to initialize KillChainEngine: {e}", exc_info=True)
            raise HTTPException(status_code=503, detail=f"Kill Chain Engine unavailable: {e}")
    return _engine


@router.get("/killchain/scan")
async def kill_chain_scan():
    """
    Run full Kill Chain scan — all 5 layers.
    Returns alert level, layer data, mismatches, and narrative.
    """
    engine = _get_engine()

    try:
        import time as _time
        t0 = _time.time()
        report = engine.run_full_scan()
        scan_time = _time.time() - t0

        # Assemble layer data from individual report attributes
        layers = {}
        layer_names = ["fedwatch", "dark_pool", "cot", "gex", "sec_13f"]
        for name in layer_names:
            data = getattr(report, name, None)
            if data:
                # Strip narrative from layer data (it's in the main narrative)
                layers[name] = {k: v for k, v in data.items() if k != "narrative"}

        # Serialize mismatches
        mismatches = []
        for m in (report.mismatches or []):
            mismatches.append({
                "severity": m.severity if hasattr(m, 'severity') else str(m.get("severity", "YELLOW")),
                "description": m.description if hasattr(m, 'description') else str(m.get("description", "")),
                "layer": m.title if hasattr(m, 'title') else str(m.get("layer", "unknown")),
            })

        response = {
            "alert_level": report.alert_level,
            "timestamp": report.timestamp or datetime.utcnow().isoformat(),
            "scan_time_seconds": round(scan_time, 1),
            "layers_active": report.layers_active,
            "layers_total": 5,
            "layers_failed": report.layers_failed,
            "narrative": report.narrative,
            "mismatches": mismatches,
            "layers": layers,
        }

        return response

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Kill chain scan failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Scan failed: {e}")


@router.get("/killchain/gex/{symbol}")
async def kill_chain_gex(
    symbol: str,
    as_levels: bool = Query(True, description="Return as TradingView-compatible DPLevel format"),
):
    """
    Get GEX (Gamma Exposure) data for a symbol.
    When as_levels=true, returns gamma walls as DPLevel[] compatible with TradingViewChart.
    """
    try:
        from live_monitoring.enrichment.apis.gex_calculator import GEXCalculator

        calc = GEXCalculator()
        result = calc.compute_gex(symbol.upper())

        if result is None:
            raise HTTPException(status_code=404, detail=f"No GEX data for {symbol}")

        if as_levels:
            # Convert gamma walls to TradingView-compatible DPLevel format
            levels = []

            # Gamma walls as SUPPORT levels (positive GEX = dealers absorb moves)
            for wall in (result.gamma_walls or [])[:5]:
                levels.append({
                    "price": wall.strike,
                    "volume": abs(int(wall.gex)),
                    "type": "SUPPORT",
                    "strength": "STRONG" if abs(wall.gex) > 200000 else "MODERATE" if abs(wall.gex) > 100000 else "WEAK",
                    "source": "GEX_WALL",
                    "gex": wall.gex,
                })

            # Negative zones as RESISTANCE levels (negative GEX = dealers amplify)
            for zone in (result.negative_zones or [])[:3]:
                levels.append({
                    "price": zone.strike,
                    "volume": abs(int(zone.gex)),
                    "type": "RESISTANCE",
                    "strength": "STRONG" if abs(zone.gex) > 500000 else "MODERATE" if abs(zone.gex) > 200000 else "WEAK",
                    "source": "GEX_NEGATIVE",
                    "gex": zone.gex,
                })

            return {
                "symbol": symbol.upper(),
                "spot_price": result.spot_price,
                "total_gex": result.total_gex,
                "gamma_regime": result.gamma_regime,
                "gamma_flip": result.gamma_flip,
                "max_pain": result.max_pain,
                "levels": levels,
                "timestamp": datetime.utcnow().isoformat(),
            }
        else:
            # Raw GEX data
            return {
                "symbol": symbol.upper(),
                "spot_price": result.spot_price,
                "total_gex": result.total_gex,
                "gamma_regime": result.gamma_regime,
                "gamma_flip": result.gamma_flip,
                "max_pain": result.max_pain,
                "gamma_walls": [
                    {"strike": w.strike, "gex": w.gex, "signal": w.signal}
                    for w in (result.gamma_walls or [])
                ],
                "negative_zones": [
                    {"strike": z.strike, "gex": z.gex}
                    for z in (result.negative_zones or [])
                ],
                "contracts_analyzed": result.contracts_analyzed,
                "timestamp": datetime.utcnow().isoformat(),
            }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"GEX calculation failed for {symbol}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"GEX failed: {e}")


@router.get("/killchain/narrative")
async def kill_chain_narrative():
    """Get the unified shadow narrative from the latest Kill Chain scan."""
    engine = _get_engine()

    try:
        report = engine.run_full_scan()
        return {
            "narrative": report.narrative,
            "alert_level": report.alert_level,
            "mismatches_count": len(report.mismatches or []),
            "timestamp": report.timestamp.isoformat() if report.timestamp else datetime.utcnow().isoformat(),
        }
    except Exception as e:
        logger.error(f"Narrative generation failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Narrative failed: {e}")
