"""
COT Positioning API — CFTC Commitments of Traders

GET /cot/positioning  → all 6 contracts with divergence signals
"""

import logging
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import List, Optional

logger = logging.getLogger(__name__)
router = APIRouter()


class ContractPosition(BaseModel):
    contract_key: str
    contract_name: str
    report_date: str
    specs_net: int
    comm_net: int
    nonrep_net: int
    open_interest: int
    specs_ratio: float  # specs_net / OI
    specs_side: str  # "LONG" or "SHORT"
    comm_side: str
    divergent: bool
    divergence_direction: str
    divergence_magnitude: int
    divergence_description: str


class COTResponse(BaseModel):
    contracts: List[ContractPosition]
    total_divergent: int
    narrative: str


@router.get("/cot/positioning", response_model=COTResponse)
async def get_cot_positioning():
    """Get COT positioning for all tracked contracts."""
    try:
        from live_monitoring.enrichment.apis.cot_client import COTClient

        client = COTClient(cache_ttl=300)
        contracts = []
        keys = ["ES", "NQ", "TY", "GC", "CL", "VX"]

        for key in keys:
            pos = client.get_position(key)
            if not pos:
                continue

            div = client.get_divergence_signal(key)

            contracts.append(ContractPosition(
                contract_key=key,
                contract_name=pos.contract_name,
                report_date=pos.report_date,
                specs_net=pos.specs_net,
                comm_net=pos.comm_net,
                nonrep_net=pos.nonrep_net,
                open_interest=pos.open_interest,
                specs_ratio=round(pos.specs_ratio, 4),
                specs_side="SHORT" if pos.specs_net < 0 else "LONG",
                comm_side="LONG" if pos.comm_net > 0 else "SHORT",
                divergent=div.get("divergent", False),
                divergence_direction=div.get("direction", "unknown"),
                divergence_magnitude=div.get("magnitude", 0),
                divergence_description=div.get("description", ""),
            ))

        # Use source's rich narrative for each contract
        per_contract_narratives = []
        for key in keys:
            try:
                narr = client.get_narrative(key)
                if narr and "unavailable" not in narr.lower():
                    per_contract_narratives.append(narr)
            except Exception:
                pass
        div_count = sum(1 for c in contracts if c.divergent)
        if per_contract_narratives:
            narrative = " | ".join(per_contract_narratives)
        else:
            # Fallback to simple narrative
            parts = [f"{c.contract_key}: Specs {c.specs_net:+,} {c.specs_side}" for c in contracts]
            narrative = f"COT: {div_count}/{len(contracts)} divergent | " + " | ".join(parts)

        return COTResponse(
            contracts=contracts,
            total_divergent=div_count,
            narrative=narrative,
        )

    except Exception as e:
        logger.error(f"COT endpoint error: {e}")
        raise HTTPException(status_code=500, detail=str(e))
