"""
brief/cache.py — Module-level TTL cache + asyncio compute mutex.

Only ONE /brief/master computation may run at a time.
Concurrent requests wait for in-flight compute then serve from cache.
Prevents 2x ThreadPoolExecutor spikes from OOM-ing Render's 512MB instance.
"""
import asyncio
import time
import logging

logger = logging.getLogger(__name__)

BRIEF_CACHE_TTL = 120  # 2-minute TTL

_brief_cache:      dict | None = None
_brief_cache_time: float | None = None
_brief_lock = asyncio.Lock()

# ── Lazy singletons for heavy objects (init once per process, reuse) ─────────
_singletons: dict = {}


def lazy(key: str, factory):
    """Return cached singleton; create via factory() on first call."""
    if key not in _singletons:
        _singletons[key] = factory()
    return _singletons[key]


def get_cache() -> dict | None:
    """Return cached brief if still within TTL, else None."""
    global _brief_cache, _brief_cache_time
    if _brief_cache and _brief_cache_time:
        age = time.time() - _brief_cache_time
        if age < BRIEF_CACHE_TTL:
            logger.info(f"📋 Brief cache hit ({age:.0f}s old)")
            return _brief_cache
    return None


def set_cache(result: dict) -> None:
    """Persist result to cache."""
    global _brief_cache, _brief_cache_time
    _brief_cache      = result
    _brief_cache_time = time.time()
