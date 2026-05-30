"""
/debug/memory  — in-process RSS burn monitor endpoints.

Reads memory directly from the running process via psutil (or /proc/self/status
as fallback). No external API, no auth, ground truth from inside the container.

Endpoints:
  GET /debug/memory          — current snapshot (rss_mb, vms_mb, percent)
  GET /debug/memory/history  — full burn curve deque from startup to now
"""

from fastapi import APIRouter
from fastapi.responses import JSONResponse

router = APIRouter(tags=["memstats"])


def _read_rss():
    """Return (rss_bytes, vms_bytes) using psutil or /proc fallback."""
    try:
        import psutil, os
        p = psutil.Process(os.getpid())
        mi = p.memory_info()
        return mi.rss, mi.vms
    except Exception:
        pass
    # /proc/self/status fallback (Linux only)
    try:
        rss_kb = vms_kb = 0
        with open("/proc/self/status") as f:
            for line in f:
                if line.startswith("VmRSS:"):
                    rss_kb = int(line.split()[1])
                elif line.startswith("VmSize:"):
                    vms_kb = int(line.split()[1])
        return rss_kb * 1024, vms_kb * 1024
    except Exception:
        return 0, 0


@router.get("/debug/memory")
async def memory_snapshot():
    """Current RSS + VMS in MB, read directly from the process."""
    rss, vms = _read_rss()
    return {
        "rss_mb": round(rss / 1024 / 1024, 2),
        "vms_mb": round(vms / 1024 / 1024, 2),
        "rss_bytes": rss,
        "note": "psutil or /proc/self/status — in-process, ground truth",
    }


@router.get("/debug/memory/history")
async def memory_history():
    """Full RSS burn curve from startup to now (1-min samples, max 200 entries ~3.3h)."""
    from backend.app.main import _rss_history  # imported at call time to avoid circular
    rows = list(_rss_history)
    if not rows:
        return JSONResponse({"error": "no data yet — logger starts 10s after startup", "rows": []})

    first_rss = rows[0]["rss_mb"]
    last_rss  = rows[-1]["rss_mb"]
    return {
        "count": len(rows),
        "first_rss_mb": first_rss,
        "last_rss_mb": last_rss,
        "growth_mb": round(last_rss - first_rss, 2),
        "elapsed_min": rows[-1]["elapsed_min"],
        "rows": rows,
    }
