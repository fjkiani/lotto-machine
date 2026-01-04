"""
💾 Persistent Storage Utility for Render Deployment
==================================================
Handles persistent storage for SQLite databases on Render.

On Render:
- Free tier: Ephemeral filesystem (data lost on spin-down)
- Paid tier: Can use persistent disk (/opt/render/project/src/data)

This utility provides a fallback mechanism:
1. Try Render persistent disk if available
2. Fall back to project root /data directory
3. Log warnings if using ephemeral storage
"""

import os
import logging
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

# Render persistent disk path (if available on paid tier)
RENDER_PERSISTENT_DISK = Path("/opt/render/project/src/data")

# Standard data directory in project root
PROJECT_DATA_DIR = Path(__file__).parent.parent.parent.parent / "data"


def get_persistent_data_dir() -> Path:
    """
    Get the persistent data directory path.
    
    Priority:
    1. Render persistent disk (if available)
    2. Environment variable DATA_DIR (if set)
    3. Project root /data directory
    
    Returns:
        Path to persistent data directory
    """
    # Check for environment variable override
    env_data_dir = os.getenv('DATA_DIR')
    if env_data_dir:
        data_dir = Path(env_data_dir)
        data_dir.mkdir(parents=True, exist_ok=True)
        logger.info(f"📁 Using DATA_DIR from environment: {data_dir}")
        return data_dir
    
    # Check for Render persistent disk (paid tier)
    if RENDER_PERSISTENT_DISK.exists() and os.access(RENDER_PERSISTENT_DISK, os.W_OK):
        RENDER_PERSISTENT_DISK.mkdir(parents=True, exist_ok=True)
        logger.info(f"💾 Using Render persistent disk: {RENDER_PERSISTENT_DISK}")
        return RENDER_PERSISTENT_DISK
    
    # Fallback to project root
    PROJECT_DATA_DIR.mkdir(parents=True, exist_ok=True)
    
    # Warn if on Render free tier (ephemeral storage)
    if os.getenv('RENDER'):
        logger.warning("⚠️  WARNING: Using ephemeral storage on Render free tier!")
        logger.warning("⚠️  Data will be LOST when service spins down.")
        logger.warning("⚠️  Solutions:")
        logger.warning("   1. Upgrade to Render paid tier (persistent disk)")
        logger.warning("   2. Use external database (PostgreSQL, etc.)")
        logger.warning("   3. Set DATA_DIR environment variable to external storage")
    else:
        logger.info(f"📁 Using project data directory: {PROJECT_DATA_DIR}")
    
    return PROJECT_DATA_DIR


def get_database_path(db_filename: str) -> Path:
    """
    Get full path to a database file in persistent storage.
    
    Args:
        db_filename: Name of database file (e.g., "dp_learning.db")
    
    Returns:
        Full path to database file
    """
    data_dir = get_persistent_data_dir()
    db_path = data_dir / db_filename
    return db_path


def is_persistent() -> bool:
    """
    Check if current storage is persistent (won't be lost on restart).
    
    Returns:
        True if using persistent storage, False if ephemeral
    """
    data_dir = get_persistent_data_dir()
    
    # Render persistent disk is persistent
    if data_dir == RENDER_PERSISTENT_DISK:
        return True
    
    # Environment variable might point to persistent storage
    if os.getenv('DATA_DIR'):
        return True
    
    # Project root on Render free tier is ephemeral
    if os.getenv('RENDER'):
        return False
    
    # Local development is "persistent" (doesn't get wiped)
    return True

