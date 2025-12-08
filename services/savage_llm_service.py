#!/usr/bin/env python3
"""
SAVAGE LLM SERVICE - Discord Bot Integration Layer

Provides a clean interface for Discord bot to interact with savage LLM.
Handles errors, formatting, and response processing.
"""

import os
import logging
from typing import Dict, Any
from src.data.llm_api import query_llm_savage

logger = logging.getLogger(__name__)

class SavageLLMService:
    """
    Service layer for savage LLM integration with Discord bot

    Features:
    - Async response handling
    - Error management
    - Response formatting
    - Rate limiting awareness
    """

    def __init__(self):
        """Initialize savage LLM service"""
        self.api_key = os.getenv("GEMINI_API_KEY")
        self.default_level = os.getenv("SAVAGE_LEVEL", "chained_pro")

        if not self.api_key:
            logger.error("❌ GEMINI_API_KEY not found in environment!")
            self.ready = False
        else:
            self.ready = True
            logger.info("✅ Savage LLM service initialized")

    async def get_savage_response(self, query: str, level: str = None) -> Dict[str, Any]:
        """
        Get savage LLM response with comprehensive error handling

        Args:
            query: User's question
            level: Savagery level (basic, alpha_warrior, full_savage, chained_pro)

        Returns:
            Dict with response data or error info
        """
        if not self.ready:
            return {
                "error": "Savage LLM not configured. Check GEMINI_API_KEY environment variable.",
                "status": "error"
            }

        if not level:
            level = self.default_level

        try:
            logger.info(f"🤖 Processing savage query: '{query[:50]}...' at level: {level}")

            # Call savage LLM
            response = query_llm_savage(query, level)

            if isinstance(response, dict) and "error" in response:
                return {
                    "error": f"Savage LLM error: {response['error']}",
                    "status": "error"
                }

            # Success response
            return {
                "response": response['response'] if isinstance(response, dict) else str(response),
                "level": level,
                "status": "success",
                "timestamp": response.get('timestamp', None)
            }

        except Exception as e:
            logger.error(f"❌ Savage LLM service error: {e}")
            return {
                "error": f"Savage system malfunction: {str(e)}",
                "status": "error"
            }

    def get_available_levels(self) -> Dict[str, str]:
        """Get available savagery levels with descriptions"""
        return {
            "basic": "Basic Savage (4K chars) - Solid analysis with edge",
            "alpha_warrior": "Alpha Warrior (3K chars) - Combat mode intensity",
            "full_savage": "Maximum Savage (5K chars) - Ruthless aggression",
            "chained_pro": "GODLIKE Savage (8K chars) - Ultimate brutality"
        }

    def is_ready(self) -> bool:
        """Check if service is ready"""
        return self.ready

    def get_stats(self) -> Dict[str, Any]:
        """Get service statistics"""
        return {
            "ready": self.ready,
            "default_level": self.default_level,
            "api_key_configured": bool(self.api_key),
            "available_levels": list(self.get_available_levels().keys())
        }


