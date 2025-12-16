"""
Webhook Handlers Package
========================

Handles webhooks from various sources (YAGPDB, Discord, etc.)
"""

from .yagpdb_youtube_handler import YAGPDBYouTubeHandler, app

__all__ = ['YAGPDBYouTubeHandler', 'app']


