"""
brief/config.py — Veto cascade config loader + tier resolver.
"""
import logging
from pathlib import Path

logger = logging.getLogger(__name__)

try:
    import yaml
except ImportError:
    yaml = None

_veto_config = None


def _load_veto_config() -> dict:
    """Load veto_cascade.yaml once at startup. Falls back to hardcoded defaults."""
    global _veto_config
    if _veto_config is not None:
        return _veto_config

    config_path = Path(__file__).resolve().parents[4] / 'config' / 'veto_cascade.yaml'
    if yaml and config_path.exists():
        try:
            with open(config_path) as f:
                _veto_config = yaml.safe_load(f)
            logger.info(f"📋 Veto config loaded from {config_path}")
            return _veto_config
        except Exception as e:
            logger.warning(f"Failed to load veto config: {e} — using hardcoded defaults")

    _veto_config = {
        'VETO_TIERS': {
            'BLOCKED':   {'hours': 0.5,  'cap': 0},
            'HIGH_RISK': {'hours': 2.0,  'cap': 35},
            'RISK':      {'hours': 6.0,  'cap': 50},
            'AWARENESS': {'hours': 24.0, 'cap': 55},
            'NORMAL':    {'hours': None, 'cap': 65},
        },
        'EVENT_OVERRIDES': {}
    }
    return _veto_config


def resolve_tiers(event_name: str) -> list:
    """Build tier ladder for a specific event, merging overrides with defaults."""
    cfg      = _load_veto_config()
    defaults  = cfg.get('VETO_TIERS', {})
    overrides = cfg.get('EVENT_OVERRIDES', {})

    event_upper       = (event_name or '').upper()
    matched_overrides = {}
    for key, ovr in overrides.items():
        if key.upper() in event_upper:
            matched_overrides = ovr or {}
            break

    tiers = []
    for tier_name, tier_def in defaults.items():
        hours = tier_def.get('hours')
        cap   = tier_def.get('cap', 65)
        if tier_name in matched_overrides:
            hours = matched_overrides[tier_name].get('hours', hours)
            cap   = matched_overrides[tier_name].get('cap', cap)
        tiers.append((tier_name, hours, cap))

    tiers.sort(key=lambda t: (t[1] is None, t[1] or 999))
    return tiers
