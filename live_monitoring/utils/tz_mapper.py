"""
🕐 Timezone Mapper — Single Source of Truth for Time Conversion

Trading Economics calendar returns times in GMT/UTC.
Our system operates in US/Eastern (ET).
This module provides ONE PLACE for all timezone conversions.

Usage:
    from live_monitoring.utils.tz_mapper import te_time_to_et, now_et, hours_until_release
"""

from datetime import datetime, timedelta
from typing import Optional
import pytz

# ── Constants ──
ET = pytz.timezone('US/Eastern')
UTC = pytz.UTC


def now_et() -> datetime:
    """Get current time in Eastern, timezone-aware."""
    return datetime.now(ET)


def now_utc() -> datetime:
    """Get current UTC time, timezone-aware."""
    return datetime.now(UTC)


def te_time_to_et(te_date: str, te_time: str) -> Optional[datetime]:
    """
    Convert a TE calendar date+time (GMT) to Eastern Time.
    
    Args:
        te_date: TE date string, e.g. "Tuesday March 10 2026"
        te_time: TE time string, e.g. "02:00 PM" (GMT)
    
    Returns:
        Timezone-aware datetime in US/Eastern, or None if parsing fails.
    
    Example:
        te_time_to_et("Tuesday March 10 2026", "02:00 PM")
        → 2026-03-10 10:00:00-04:00  (EDT)
    """
    if not te_date:
        return None
    
    try:
        # Strip day name: "Tuesday March 10 2026" → "March 10 2026"
        parts = te_date.strip().split(' ', 1)
        if len(parts) < 2:
            return None
        date_str = parts[1]
        
        time_str = (te_time or "08:30 AM").strip()
        dt_str = f"{date_str} {time_str}"
        
        # Parse as naive datetime
        parsed = None
        for fmt in ["%B %d %Y %I:%M %p", "%B %d %Y %H:%M"]:
            try:
                parsed = datetime.strptime(dt_str, fmt)
                break
            except ValueError:
                continue
        
        if parsed is None:
            return None
        
        # TE times are GMT → localize to UTC, then convert to ET
        utc_dt = UTC.localize(parsed)
        et_dt = utc_dt.astimezone(ET)
        
        return et_dt
    except (ValueError, AttributeError):
        return None


def hours_until_release(te_date: str, te_time: str, from_time: datetime = None) -> Optional[float]:
    """
    Compute hours from now (or from_time) until a TE event release.
    
    Both sides are timezone-aware (ET).
    
    Args:
        te_date: TE date string (GMT)
        te_time: TE time string (GMT)
        from_time: Optional reference time (must be tz-aware). Defaults to now_et().
    
    Returns:
        Hours until release (negative = already passed), or None.
    """
    release_et = te_time_to_et(te_date, te_time)
    if release_et is None:
        return None
    
    ref = from_time or now_et()
    
    # Ensure ref is timezone-aware
    if ref.tzinfo is None:
        ref = ET.localize(ref)
    
    delta = release_et - ref
    return delta.total_seconds() / 3600.0


def format_et(dt: datetime) -> str:
    """Format a datetime for display: '10:00 AM ET'."""
    return dt.strftime("%I:%M %p ET")


def te_display_time(te_date: str, te_time: str) -> str:
    """
    Convert a TE GMT time to a human-readable ET string.
    
    Example:
        te_display_time("Tuesday March 10 2026", "02:00 PM")
        → "10:00 AM ET"
    """
    et_dt = te_time_to_et(te_date, te_time)
    if et_dt is None:
        return te_time or "??:??"
    return format_et(et_dt)
