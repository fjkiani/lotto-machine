"""
Training snapshot pipeline — supervised fine-tuning data collection.

Endpoints:
  POST /training/snapshot          → save labeled snapshot, returns snapshot_id
  POST /training/outcome           → record WIN/LOSS outcome N days later
  GET  /training/pending-outcomes  → snapshots older than outcome_window_days with no outcome
  GET  /training/export            → download JSONL (fine-tune ready)
  GET  /training/status            → count, last timestamp, pending count

Design:
  - Each snapshot gets a unique snapshot_id (UTC timestamp + hash)
  - Snapshot includes regime label (UPTREND/DOWNTREND/CHOPPY) from caller
  - Outcome is recorded separately and merged into the JSONL record
  - Records without outcome are excluded from fine-tune export (incomplete labels)
  - outcome_window_days default = 3 (configurable via OUTCOME_WINDOW_DAYS env var)

Storage:
  - Render: /mnt/shared-workspace/training/ (S3-backed, survives deploys)
  - Local:  ./data/training/
  - Configurable via TRAINING_JSONL_PATH env var
"""
from __future__ import annotations

import hashlib
import json
import os
import logging
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel

logger = logging.getLogger(__name__)
router = APIRouter()

# ── Storage paths ─────────────────────────────────────────────────────────────
_IS_RENDER = bool(os.getenv("RENDER"))
_BASE_DIR = (
    Path("/mnt/shared-workspace/training")
    if _IS_RENDER
    else Path("./data/training")
)
_DEFAULT_JSONL = _BASE_DIR / "kill_chain_snapshots.jsonl"
_PENDING_DB    = _BASE_DIR / "pending_outcomes.json"   # lightweight index

TRAINING_FILE   = Path(os.getenv("TRAINING_JSONL_PATH", str(_DEFAULT_JSONL)))
OUTCOME_WINDOW  = int(os.getenv("OUTCOME_WINDOW_DAYS", "3"))


def _ensure_dir() -> None:
    TRAINING_FILE.parent.mkdir(parents=True, exist_ok=True)
    _PENDING_DB.parent.mkdir(parents=True, exist_ok=True)


def _make_snapshot_id(captured_at: str, label: str) -> str:
    """Stable 12-char ID from timestamp + label."""
    raw = f"{captured_at}:{label}"
    return hashlib.sha256(raw.encode()).hexdigest()[:12]


def _load_pending() -> Dict[str, Any]:
    """Load pending outcomes index {snapshot_id: {captured_at, label, symbol, regime, ...}}."""
    if not _PENDING_DB.exists():
        return {}
    try:
        with _PENDING_DB.open("r") as f:
            return json.load(f)
    except Exception:
        return {}


def _save_pending(pending: Dict[str, Any]) -> None:
    with _PENDING_DB.open("w") as f:
        json.dump(pending, f, indent=2, default=str)


def _count_records() -> int:
    if not TRAINING_FILE.exists():
        return 0
    with TRAINING_FILE.open("r") as f:
        return sum(1 for line in f if line.strip())


def _count_complete() -> int:
    """Records that have an outcome recorded (usable for fine-tuning)."""
    if not TRAINING_FILE.exists():
        return 0
    count = 0
    with TRAINING_FILE.open("r") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                rec = json.loads(line)
                if rec.get("metadata", {}).get("outcome") is not None:
                    count += 1
            except Exception:
                pass
    return count


# ── Request / Response models ─────────────────────────────────────────────────

class SnapshotRequest(BaseModel):
    payload: Dict[str, Any]
    label: str                          # reconciled_verdict at time of snapshot
    note: str = ""
    regime: str = "UNKNOWN"             # UPTREND / DOWNTREND / CHOPPY / STRONG_UPTREND etc.
    symbol: str = "SPY"
    confidence: Optional[float] = None  # kill chain confidence score 0-100
    signal_type: Optional[str] = None   # FROM_OPEN / ROLLING / DP_BOUNCE etc.
    direction: Optional[str] = None     # LONG / SHORT


class OutcomeRequest(BaseModel):
    snapshot_id: str
    outcome: str        # WIN / LOSS / NEUTRAL
    pnl_pct: float      # actual P&L percentage (positive = profit)
    days_elapsed: int   # days since snapshot was taken
    exit_price: Optional[float] = None
    note: str = ""


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.post("/training/snapshot")
async def save_snapshot(req: SnapshotRequest):
    """
    Append one labeled kill chain snapshot as an OpenAI fine-tune JSONL record.
    Returns { saved, snapshot_id, total_records, outcome_due_date }.

    The snapshot is saved WITHOUT an outcome — outcome must be recorded via
    POST /training/outcome after OUTCOME_WINDOW_DAYS (default 3 days).
    Only snapshots WITH outcomes are included in the fine-tune export.
    """
    _ensure_dir()

    captured_at = datetime.now(timezone.utc).isoformat()
    snapshot_id = _make_snapshot_id(captured_at, req.label)
    outcome_due = (datetime.now(timezone.utc) + timedelta(days=OUTCOME_WINDOW)).isoformat()

    # Build OpenAI fine-tune record (outcome field left null until recorded)
    record = {
        "messages": [
            {
                "role": "system",
                "content": (
                    "You are a kill chain signal analyst. "
                    "Given a structured market snapshot with regime context, "
                    "output the reconciled verdict, reasoning, and expected outcome."
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
                        "regime": req.regime,
                        "direction": req.direction,
                        "signal_type": req.signal_type,
                        "confidence": req.confidence,
                        "reconciliation_reasons": req.payload.get("reconciliation_reasons", []),
                        "outcome": None,        # filled in by /training/outcome
                        "pnl_pct": None,        # filled in by /training/outcome
                    },
                    default=str,
                ),
            },
        ],
        "metadata": {
            "snapshot_id":   snapshot_id,
            "captured_at":   captured_at,
            "outcome_due":   outcome_due,
            "outcome_window_days": OUTCOME_WINDOW,
            "label":         req.label,
            "regime":        req.regime,
            "symbol":        req.symbol,
            "confidence":    req.confidence,
            "signal_type":   req.signal_type,
            "direction":     req.direction,
            "note":          req.note,
            "outcome":       None,   # None until /training/outcome is called
            "pnl_pct":       None,
            "outcome_recorded_at": None,
        },
    }

    with TRAINING_FILE.open("a") as f:
        f.write(json.dumps(record, default=str) + "\n")

    # Register in pending index
    pending = _load_pending()
    pending[snapshot_id] = {
        "captured_at":   captured_at,
        "outcome_due":   outcome_due,
        "label":         req.label,
        "regime":        req.regime,
        "symbol":        req.symbol,
        "direction":     req.direction,
        "confidence":    req.confidence,
        "signal_type":   req.signal_type,
    }
    _save_pending(pending)

    total = _count_records()
    complete = _count_complete()
    logger.info(
        "training snapshot saved: id=%s label=%s regime=%s total=%d complete=%d",
        snapshot_id, req.label, req.regime, total, complete
    )

    return {
        "saved":            True,
        "snapshot_id":      snapshot_id,
        "total_records":    total,
        "complete_records": complete,
        "outcome_due_date": outcome_due,
        "outcome_window_days": OUTCOME_WINDOW,
        "message": (
            f"Snapshot {snapshot_id} saved. "
            f"Record outcome in {OUTCOME_WINDOW} days via POST /training/outcome. "
            f"{complete} complete records ready for fine-tuning."
        ),
    }


@router.post("/training/outcome")
async def record_outcome(req: OutcomeRequest):
    """
    Record the actual WIN/LOSS outcome for a previously saved snapshot.
    Patches the JSONL record in-place (rewrites file).
    Removes snapshot from pending index.

    This is what converts a raw snapshot into a supervised training example.
    """
    if req.outcome not in ("WIN", "LOSS", "NEUTRAL"):
        raise HTTPException(status_code=400, detail="outcome must be WIN, LOSS, or NEUTRAL")

    if not TRAINING_FILE.exists():
        raise HTTPException(status_code=404, detail="No training snapshots found.")

    # Read all records, patch the matching one
    recorded_at = datetime.now(timezone.utc).isoformat()
    found = False
    updated_lines = []

    with TRAINING_FILE.open("r") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                rec = json.loads(line)
                if rec.get("metadata", {}).get("snapshot_id") == req.snapshot_id:
                    # Patch metadata
                    rec["metadata"]["outcome"]              = req.outcome
                    rec["metadata"]["pnl_pct"]              = req.pnl_pct
                    rec["metadata"]["outcome_recorded_at"]  = recorded_at
                    rec["metadata"]["days_elapsed"]         = req.days_elapsed
                    rec["metadata"]["exit_price"]           = req.exit_price
                    rec["metadata"]["outcome_note"]         = req.note

                    # Patch assistant message content
                    for msg in rec.get("messages", []):
                        if msg.get("role") == "assistant":
                            try:
                                content = json.loads(msg["content"])
                                content["outcome"] = req.outcome
                                content["pnl_pct"] = req.pnl_pct
                                msg["content"] = json.dumps(content, default=str)
                            except Exception:
                                pass
                    found = True
            except Exception:
                pass
            updated_lines.append(json.dumps(rec, default=str) if found and not updated_lines.__contains__(line) else line)

    if not found:
        raise HTTPException(status_code=404, detail=f"Snapshot {req.snapshot_id} not found.")

    # Rewrite file atomically
    tmp = TRAINING_FILE.with_suffix(".tmp")
    with tmp.open("w") as f:
        # Re-read and patch properly (the loop above has a bug with the contains check)
        pass

    # Clean rewrite
    with TRAINING_FILE.open("r") as f:
        all_lines = [l.strip() for l in f if l.strip()]

    patched_lines = []
    for line in all_lines:
        try:
            rec = json.loads(line)
            if rec.get("metadata", {}).get("snapshot_id") == req.snapshot_id:
                rec["metadata"]["outcome"]              = req.outcome
                rec["metadata"]["pnl_pct"]              = req.pnl_pct
                rec["metadata"]["outcome_recorded_at"]  = recorded_at
                rec["metadata"]["days_elapsed"]         = req.days_elapsed
                rec["metadata"]["exit_price"]           = req.exit_price
                rec["metadata"]["outcome_note"]         = req.note
                for msg in rec.get("messages", []):
                    if msg.get("role") == "assistant":
                        try:
                            content = json.loads(msg["content"])
                            content["outcome"] = req.outcome
                            content["pnl_pct"] = req.pnl_pct
                            msg["content"] = json.dumps(content, default=str)
                        except Exception:
                            pass
            patched_lines.append(json.dumps(rec, default=str))
        except Exception:
            patched_lines.append(line)

    with TRAINING_FILE.open("w") as f:
        f.write("\n".join(patched_lines) + "\n")

    # Remove from pending index
    pending = _load_pending()
    pending.pop(req.snapshot_id, None)
    _save_pending(pending)

    complete = _count_complete()
    logger.info(
        "outcome recorded: id=%s outcome=%s pnl=%.2f%% complete=%d",
        req.snapshot_id, req.outcome, req.pnl_pct, complete
    )

    return {
        "recorded":         True,
        "snapshot_id":      req.snapshot_id,
        "outcome":          req.outcome,
        "pnl_pct":          req.pnl_pct,
        "complete_records": complete,
        "ready_for_finetune": complete >= 50,
        "message": (
            f"Outcome {req.outcome} ({req.pnl_pct:+.2f}%) recorded for {req.snapshot_id}. "
            f"{complete} complete records ready for fine-tuning."
        ),
    }


@router.get("/training/pending-outcomes")
async def pending_outcomes():
    """
    Return snapshots that are past their outcome_due date but have no outcome recorded.
    Frontend uses this to show 'Record Outcome' prompts to the operator.
    """
    pending = _load_pending()
    now = datetime.now(timezone.utc)
    overdue = []
    upcoming = []

    for sid, meta in pending.items():
        try:
            due = datetime.fromisoformat(meta["outcome_due"])
            days_overdue = (now - due).days
            entry = {**meta, "snapshot_id": sid, "days_overdue": days_overdue}
            if now >= due:
                overdue.append(entry)
            else:
                days_until = (due - now).days
                entry["days_until_due"] = days_until
                upcoming.append(entry)
        except Exception:
            overdue.append({**meta, "snapshot_id": sid, "days_overdue": 0})

    overdue.sort(key=lambda x: x.get("days_overdue", 0), reverse=True)
    upcoming.sort(key=lambda x: x.get("days_until_due", 99))

    return {
        "overdue_count":  len(overdue),
        "upcoming_count": len(upcoming),
        "overdue":        overdue,
        "upcoming":       upcoming,
        "outcome_window_days": OUTCOME_WINDOW,
    }


@router.get("/training/export")
async def export_snapshots(complete_only: bool = True):
    """
    Download the JSONL training file.
    complete_only=true (default): only records with outcomes (fine-tune ready).
    complete_only=false: all records including pending.
    """
    if not TRAINING_FILE.exists() or TRAINING_FILE.stat().st_size == 0:
        raise HTTPException(status_code=404, detail="No training snapshots saved yet.")

    if not complete_only:
        return FileResponse(
            path=str(TRAINING_FILE),
            media_type="application/jsonl",
            filename="kill_chain_snapshots.jsonl",
            headers={"Content-Disposition": "attachment; filename=kill_chain_snapshots.jsonl"},
        )

    # Filter to complete records only
    complete_lines = []
    with TRAINING_FILE.open("r") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                rec = json.loads(line)
                if rec.get("metadata", {}).get("outcome") is not None:
                    complete_lines.append(line)
            except Exception:
                pass

    if not complete_lines:
        raise HTTPException(
            status_code=404,
            detail="No complete records yet. Record outcomes via POST /training/outcome first."
        )

    # Write filtered file to temp location
    _ensure_dir()
    export_path = TRAINING_FILE.parent / "kill_chain_snapshots_complete.jsonl"
    with export_path.open("w") as f:
        f.write("\n".join(complete_lines) + "\n")

    return FileResponse(
        path=str(export_path),
        media_type="application/jsonl",
        filename="kill_chain_snapshots_complete.jsonl",
        headers={"Content-Disposition": "attachment; filename=kill_chain_snapshots_complete.jsonl"},
    )


@router.get("/training/status")
async def training_status():
    """Snapshot counts, pending outcomes, fine-tune readiness."""
    total    = _count_records()
    complete = _count_complete()
    pending  = _load_pending()
    now      = datetime.now(timezone.utc)

    overdue_count = sum(
        1 for meta in pending.values()
        if datetime.fromisoformat(meta.get("outcome_due", now.isoformat())) <= now
    )

    last_ts: Optional[str] = None
    if TRAINING_FILE.exists() and total > 0:
        with TRAINING_FILE.open("r") as f:
            lines = [l.strip() for l in f if l.strip()]
        if lines:
            try:
                last_ts = json.loads(lines[-1]).get("metadata", {}).get("captured_at")
            except Exception:
                pass

    return {
        "total_records":        total,
        "complete_records":     complete,
        "pending_outcome_count": len(pending),
        "overdue_outcome_count": overdue_count,
        "export_path":          str(TRAINING_FILE),
        "last_captured_at":     last_ts,
        "outcome_window_days":  OUTCOME_WINDOW,
        "ready_for_finetune":   complete >= 50,
        "finetune_progress":    f"{complete}/50" if complete < 50 else f"{complete} (ready)",
    }
