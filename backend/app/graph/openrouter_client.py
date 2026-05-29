"""
OpenRouter Multi-LLM Client
============================
Single entry point for all LLM calls in the graph pipeline.
Routes to the right free model based on role.
Primary: OpenRouter (OPENROUTER_API_KEY).
Fallback: OpenRouter Nemotron (same key, different model) — no Groq dependency.

Model assignments (verified available 2026-05-23):
  MACRO node      → nvidia/nemotron-3-super-120b-a12b:free  (120B MoE, strong reasoning)
  FLOW node       → nvidia/nemotron-3-super-120b-a12b:free  (120B — structured data)
  REGIME node     → nvidia/nemotron-3-super-120b-a12b:free  (fast classification)
  SYNTHESIS node  → nvidia/nemotron-3-super-120b-a12b:free  (MoE synthesis)
  QUICK / EXPLAIN → nvidia/nemotron-3-super-120b-a12b:free  (fast, free)
"""
import os
import json
import logging
import hashlib
import time
import re
from typing import Optional, Dict, Any
import httpx

logger = logging.getLogger(__name__)

OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY", "")
OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1/chat/completions"

# Primary model — NVIDIA Nemotron 3 Super 120B (free tier, OpenRouter)
NEMOTRON_MODEL = "nvidia/nemotron-3-super-120b-a12b:free"

# Model role registry — all roles route to Nemotron (free, 120B, strong reasoning)
MODEL_REGISTRY = {
    "macro":     NEMOTRON_MODEL,
    "flow":      NEMOTRON_MODEL,
    "regime":    NEMOTRON_MODEL,
    "synthesis": NEMOTRON_MODEL,
    "quick":     NEMOTRON_MODEL,
    "explain":   NEMOTRON_MODEL,
}

# In-memory response cache (prompt_hash → {content, expires})
_cache: Dict[str, Any] = {}
_CACHE_TTL = 600  # 10 minutes


def _cache_key(model: str, prompt: str) -> str:
    return hashlib.md5(f"{model}:{prompt}".encode()).hexdigest()


def _openrouter_post(
    messages: list,
    model: str,
    max_tokens: int,
    timeout: int,
    response_format: Optional[Dict] = None,
) -> Optional[str]:
    """
    Raw OpenRouter POST. Returns content string or None on failure.
    Shared by call_openrouter() and all direct callers in oracle/agents/explainer.
    """
    if not OPENROUTER_API_KEY:
        logger.warning("OPENROUTER_API_KEY not set — LLM call skipped")
        return None
    body: Dict[str, Any] = {
        "model": model,
        "messages": messages,
        "max_tokens": max_tokens,
        "temperature": 0.3,
    }
    if response_format:
        body["response_format"] = response_format
    try:
        resp = httpx.post(
            OPENROUTER_BASE_URL,
            headers={
                "Authorization": f"Bearer {OPENROUTER_API_KEY}",
                "HTTP-Referer": "https://lotto-machine.onrender.com",
                "X-Title": "Alpha Terminal",
                "Content-Type": "application/json",
            },
            json=body,
            timeout=timeout,
        )
        resp.raise_for_status()
        content = resp.json()["choices"][0]["message"]["content"]
        logger.info(f"✅ OpenRouter {model} OK ({len(content)} chars)")
        return content
    except Exception as e:
        logger.error(f"💀 OpenRouter {model} failed: {e}")
        return None


async def _openrouter_post_async(
    messages: list,
    model: str,
    max_tokens: int,
    timeout: float,
    response_format: Optional[Dict] = None,
) -> Optional[str]:
    """Async variant of _openrouter_post for FastAPI endpoints."""
    if not OPENROUTER_API_KEY:
        logger.warning("OPENROUTER_API_KEY not set — LLM call skipped")
        return None
    body: Dict[str, Any] = {
        "model": model,
        "messages": messages,
        "max_tokens": max_tokens,
        "temperature": 0.3,
    }
    if response_format:
        body["response_format"] = response_format
    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            resp = await client.post(
                OPENROUTER_BASE_URL,
                headers={
                    "Authorization": f"Bearer {OPENROUTER_API_KEY}",
                    "HTTP-Referer": "https://lotto-machine.onrender.com",
                    "X-Title": "Alpha Terminal",
                    "Content-Type": "application/json",
                },
                json=body,
            )
        resp.raise_for_status()
        content = resp.json()["choices"][0]["message"]["content"]
        logger.info(f"✅ OpenRouter async {model} OK ({len(content)} chars)")
        return content
    except Exception as e:
        logger.error(f"💀 OpenRouter async {model} failed: {e}")
        return None


def call_openrouter(
    prompt: str,
    role: str = "quick",
    model: Optional[str] = None,
    system: Optional[str] = None,
    max_tokens: int = 600,
    timeout: int = 15,
    use_cache: bool = True,
) -> Dict[str, Any]:
    """
    Call OpenRouter with automatic model selection by role.
    All roles route to nvidia/nemotron-3-super-120b-a12b:free.
    Returns: {"content": str, "model": str, "source": "openrouter"|"cache"|"error"}
    """
    resolved_model = model or MODEL_REGISTRY.get(role, NEMOTRON_MODEL)

    # Cache check
    if use_cache:
        key = _cache_key(resolved_model, prompt)
        cached = _cache.get(key)
        if cached and cached["expires"] > time.time():
            logger.debug(f"Cache hit for {resolved_model}")
            return {**cached["data"], "source": "cache"}

    messages = []
    if system:
        messages.append({"role": "system", "content": system})
    messages.append({"role": "user", "content": prompt})

    content = _openrouter_post(messages, resolved_model, max_tokens, timeout)
    if content:
        result = {"content": content, "model": resolved_model, "source": "openrouter"}
        if use_cache:
            _cache[_cache_key(resolved_model, prompt)] = {
                "data": result,
                "expires": time.time() + _CACHE_TTL,
            }
        return result

    return {
        "content": "",
        "model": "none",
        "source": "error",
        "error": "OpenRouter LLM call failed",
    }


def extract_json(content: str) -> Optional[Dict]:
    """Extract JSON from LLM response, handling markdown code blocks."""
    content = re.sub(r"```(?:json)?\n?", "", content).strip()
    content = content.rstrip("`").strip()
    try:
        return json.loads(content)
    except Exception:
        match = re.search(r'\{.*\}', content, re.DOTALL)
        if match:
            try:
                return json.loads(match.group())
            except Exception:
                pass
    logger.warning("extract_json: could not parse JSON from LLM response")
    return None
