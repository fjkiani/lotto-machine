#!/usr/bin/env python3
"""
ALERT ROUTER - Route signals to multiple channels
- Console, CSV, Slack, Email
- Modular - easy to add new channels
"""

import logging
from typing import List, Any
from pathlib import Path
import sys

sys.path.append(str(Path(__file__).parent.parent / 'core'))
from signal_generator import LiveSignal

logger = logging.getLogger(__name__)

class AlertRouter:
    """Route signals to configured alert channels"""
    
    def __init__(self, alerters: List[Any] = None):
        self.alerters = alerters or []
        logger.info(f"📢 Alert Router initialized with {len(self.alerters)} channels")
    
    def add_alerter(self, alerter):
        """Add an alert channel"""
        self.alerters.append(alerter)
        logger.info(f"Added alerter: {alerter.__class__.__name__}")
    
    def send_signal_alert(self, signal: LiveSignal):
        """Send signal to all configured channels"""
        for alerter in self.alerters:
            try:
                alerter.alert_signal(signal)
            except Exception as e:
                logger.error(f"Error in {alerter.__class__.__name__}: {e}")
    
    def send_info(self, message: str):
        """Send info message to all channels"""
        for alerter in self.alerters:
            try:
                if hasattr(alerter, 'alert_info'):
                    alerter.alert_info(message)
            except Exception as e:
                logger.error(f"Error in {alerter.__class__.__name__}: {e}")
    
    def send_warning(self, message: str):
        """Send warning to all channels"""
        for alerter in self.alerters:
            try:
                if hasattr(alerter, 'alert_warning'):
                    alerter.alert_warning(message)
            except Exception as e:
                logger.error(f"Error in {alerter.__class__.__name__}: {e}")
    
    def send_error(self, message: str):
        """Send error to all channels"""
        for alerter in self.alerters:
            try:
                if hasattr(alerter, 'alert_error'):
                    alerter.alert_error(message)
            except Exception as e:
                logger.error(f"Error in {alerter.__class__.__name__}: {e}")



