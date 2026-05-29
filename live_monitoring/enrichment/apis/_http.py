"""
Shared HTTP session singleton.

All outbound REST calls in live_monitoring MUST go through get_session().
This replaces bare requests.get() calls that created a new TCP connection
(and ~3.5MB of socket/SSL overhead) on every invocation.

Thread-safe: uses threading.local() so each thread gets its own session,
but each thread reuses the same session across all calls.

Pool is bounded at 8 connections per host — prevents unbounded socket growth
under concurrent brain polls + alpha graph runs.

Phase 1 fix — The Leak Killers (2026-05-29)
"""

import threading
import requests
from requests.adapters import HTTPAdapter

_thread_local = threading.local()

_POOL_CONNECTIONS = 4   # number of connection pools (one per unique host)
_POOL_MAXSIZE = 8       # max connections per pool
_POOL_BLOCK = False     # don't block when pool is full — raise instead


def get_session() -> requests.Session:
    """
    Return the thread-local requests.Session.

    Creates one session per thread on first call; reuses it on all subsequent
    calls from the same thread. Sessions are never closed — they live for the
    lifetime of the thread (which for uvicorn worker threads is the lifetime
    of the process).

    Usage:
        from live_monitoring.enrichment.apis._http import get_session
        r = get_session().get(url, params=params, timeout=10)
    """
    session = getattr(_thread_local, "session", None)
    if session is None:
        session = requests.Session()
        adapter = HTTPAdapter(
            pool_connections=_POOL_CONNECTIONS,
            pool_maxsize=_POOL_MAXSIZE,
            pool_block=_POOL_BLOCK,
            max_retries=0,  # callers handle their own retry logic
        )
        session.mount("https://", adapter)
        session.mount("http://", adapter)
        _thread_local.session = session
    return session
