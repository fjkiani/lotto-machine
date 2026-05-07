"""
OpenRouter Multi-LLM Client
============================
Single entry point for all LLM calls in the graph pipeline.
Routes to the right free model based on role.
Falls back to Groq llama-3.3-70b if OpenRouter fails.

Model assignments (verified available 2026-05-07):
  MACRO node      → qwen/qwen3-next-80b-a3b-instruct:free  (80B, strong reasoning)
  FLOW node       → qwen/qwen3-coder:free                  (coder, structured data)
  REGIME node     → meta-llama/llama-3.3-70b-instruct:free (66K ctx, fast)
  SYNTHESIS node  → openai/gpt-oss-120b:free               (131K ctx, MoE reasoning)
  QUICK / EXPLAIN → meta-llama/llama-3.3-70b-instruct:free (fast, free)
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
GROQ_FALLBACK_URL = "https://api.groq.com/openai/v1/chat/completions"
GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")

# Model role registry — free models verified available on OpenRouter 2026-05-07
MODEL_REGISTRY = {
    "macro":     "openai/gpt-oss-120b:free",                 # 120B MoE — strong reasoning
    "flow":      "nvidia/nemotron-3-super-120b-a12b:free",   # 120B — structured data
    "regime":    "openai/gpt-oss-20b:free",                  # fast classification
    "synthesis": "openai/gpt-oss-120b:free",                 # MoE synthesis
    "quick":     "openai/gpt-oss-20b:free",                  # fast, free
    "explain":   "openai/gpt-oss-120b:free",                 # best available for narrative
}

# In-memory response cache (prompt_hash → {content, expires})
_cache: Dict[str, Any] = {}
_CACHE_TTL = 600  # 10 minutes


def _cache_key(model: str, prompt: str) -> str:
    return hashlib.md5(f"{model}:{prompt}".encode()).hexdigest()


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
    Falls back to Groq llama-3.3-70b on any OpenRouter failure.
    Returns: {"content": str, "model": str, "source": "openrouter"|"groq_fallback"|"error"}
    """
    resolved_model = model or MODEL_REGISTRY.get(role, MODEL_REGISTRY["quick"])

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

    # ── Try OpenRouter first ──────────────────────────────────────────────────
    if OPENROUTER_API_KEY:
        try:
            resp = httpx.post(
                OPENROUTER_BASE_URL,
                headers={
                    "Authorization": f"Bearer {OPENROUTER_API_KEY}",
                    "HTTP-Referer": "https://lotto-machine.onrender.com",
                    "X-Title": "Alpha Terminal",
                    "Content-Type": "application/json",
                },
                json={
                    "model": resolved_model,
                    "messages": messages,
                    "max_tokens": max_tokens,
                    "temperature": 0.3,
                },
                timeout=timeout,
            )
            resp.raise_for_status()
            data = resp.json()
            content = data["choices"][0]["message"]["content"]
            result = {"content": content, "model": resolved_model, "source": "openrouter"}
            if use_cache:
                _cache[_cache_key(resolved_model, prompt)] = {
                    "data": result,
                    "expires": time.time() + _CACHE_TTL,
                }
            logger.info(f"✅ OpenRouter {resolved_model} OK ({len(content)} chars)")
            return result
        except Exception as e:
            logger.warning(f"⚠️ OpenRouter failed ({resolved_model}): {e} — falling back to Groq")

    # ── Groq fallback ─────────────────────────────────────────────────────────
    if GROQ_API_KEY:
        try:
            resp = httpx.post(
                GROQ_FALLBACK_URL,
                headers={
                    "Authorization": f"Bearer {GROQ_API_KEY}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": "llama-3.3-70b-versatile",
                    "messages": messages,
                    "max_tokens": max_tokens,
                    "temperature": 0.3,
                },
                timeout=timeout,
            )
            resp.raise_for_status()
            content = resp.json()["choices"][0]["message"]["content"]
            logger.info(f"✅ Groq fallback OK ({len(content)} chars)")
            return {"content": content, "model": "llama-3.3-70b-versatile", "source": "groq_fallback"}
        except Exception as e:
            logger.error(f"💀 Groq fallback also failed: {e}")

    return {
        "content": "",
        "model": "none",
        "source": "error",
        "error": "All LLM backends failed",
    }


def extract_json(content: str) -> Optional[Dict]:
    """Extract JSON from LLM response, handling markdown code blocks."""
    # Strip markdown code fences
    content = re.sub(r"```(?:json)?\n?", "", content).strip()
    content = content.rstrip("`").strip()
    try:
        return json.loads(content)
    except Exception:
        # Try to find first JSON object in the response
        match = re.search(r'\{.*\}', content, re.DOTALL)
        if match:
            try:
                return json.loads(match.group())
            except Exception:
                pass
    logger.warning("extract_json: could not parse JSON from LLM response")
    return None
