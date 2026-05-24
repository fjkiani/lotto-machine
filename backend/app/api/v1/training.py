"""
Training snapshot pipeline — POST /api/v1/training/snapshot

Captures the current kill chain payload as a labeled OpenAI fine-tune JSONL record.
No live fine-tuning API call — data collection only. Export JSONL when you have 50+ records.

Bugs fixed vs agent's draft:
  1. datetime imported correctly
  2. Pydantic model used (not raw Request)
  3. Path defaults to /mnt/shared-workspace/training/ on Render (persistent S3-backed),
     ./data/training/ locally — configurable via TRAINING_JSONL_PATH env var
  4. File opened with context manager (no leak)
  5. GET /training/export endpoint included
  6. Router has no prefix — wired with prefix="/api/v1" in main.py
"""
from __future__ import annotations

import json
import os
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi import APIRouter
from fastapi.responses import FileResponse
from pydantic import BaseModel

logger = logging.getLogger(__name__)
router = APIRouter()

# ── Storage path ──────────────────────────────────────────────────────────────
# On Render: use /mnt/shared-workspace (S3-backed, survives deploys).
# Locally: ./data/training/
_DEFAULT_PATH = (
    "/mnt/shared-workspace/training/kill_chain_snapshots.jsonl"
    if os.getenv("RENDER")
    else "./data/training/kill_chain_snapshots.jsonl"
)
TRAINING_FILE = Path(os.getenv("TRAINING_JSONL_PATH", _DEFAULT_PATH))


def _ensure_dir() -> None:
    TRAINING_FILE.parent.mkdir(parents=True, exist_ok=True)


def _count_records() -> int:
    if not TRAINING_FILE.exists():
        return 0
    with TRAINING_FILE.open("r") as f:
        return sum(1 for line in f if line.strip())


# ── Request model ─────────────────────────────────────────────────────────────

class SnapshotRequest(BaseModel):
    payload: Dict[str, Any]
    label: str
    note: str = ""


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.post("/training/snapshot")
async def save_snapshot(req: SnapshotRequest):
    """
    Append one labeled kill chain snapshot as an OpenAI fine-tune JSONL record.
    Returns { saved, total_records, export_path }.
    """
    _ensure_dir()

    # Build OpenAI fine-tune record
    record = {
        "messages": [
            {
                "role": "system",
                "content": (
                    "You are a kill chain signal analyst. "
                    "Given a structured market snapshot, output the reconciled verdict and reasoning."
                ),
            },
            {
                "role": "user",
                "content": json.dumps(req.payload, default=str),
            },
            {
                "role": "assistant",
                "content": json.dumps(
                    {
                        "reconciled_verdict": req.label,
                        "reconciliation_reasons": req.payload.get("reconciliation_reasons", []),
                    },
                    default=str,
                ),
            },
        ],
        "metadata": {
            "captured_at": datetime.now(timezone.utc).isoformat(),
            "label": req.label,
            "note": req.note,
        },
    }

    with TRAINING_FILE.open("a") as f:
        f.write(json.dumps(record, default=str) + "\n")

    total = _count_records()
    logger.info("training snapshot saved: label=%s total=%d path=%s", req.label, total, TRAINING_FILE)

    return {
        "saved": True,
        "total_records": total,
        "export_path": str(TRAINING_FILE),
        "message": f"Snapshot saved ({total} total). Export JSONL when you have 50+ records.",
    }


@router.get("/training/export")
async def export_snapshots():
    """
    Download the full JSONL training file.
    Returns 404 if no snapshots have been saved yet.
    """
    if not TRAINING_FILE.exists() or TRAINING_FILE.stat().st_size == 0:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="No training snapshots saved yet.")

    return FileResponse(
        path=str(TRAINING_FILE),
        media_type="application/jsonl",
        filename="kill_chain_snapshots.jsonl",
        headers={"Content-Disposition": "attachment; filename=kill_chain_snapshots.jsonl"},
    )


@router.get("/training/status")
async def training_status():
    """How many records saved, path, last record timestamp."""
    total = _count_records()
    last_ts: Optional[str] = None
    if TRAINING_FILE.exists() and total > 0:
        # Read last non-empty line
        with TRAINING_FILE.open("r") as f:
            lines = [l.strip() for l in f if l.strip()]
        if lines:
            try:
                last_ts = json.loads(lines[-1]).get("metadata", {}).get("captured_at")
            except Exception:
                pass
    return {
        "total_records": total,
        "export_path": str(TRAINING_FILE),
        "last_captured_at": last_ts,
        "ready_for_finetune": total >= 50,
    }
