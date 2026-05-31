FROM python:3.11-slim

# System deps
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    g++ \
    libffi-dev \
    libssl-dev \
    curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install production deps inline — no separate requirements file to copy.
# Stripped of: streamlit, redis, alpaca-py, statsmodels, discord.py, matplotlib,
# seaborn, pytest, black, flake6 — saves ~140MB vs full requirements.txt
RUN pip install --no-cache-dir --upgrade pip && pip install --no-cache-dir \
    requests>=2.31.0 \
    numpy>=1.24.0 \
    "yfinance>=0.2.18" \
    pandas>=2.0.0 \
    python-dateutil>=2.8.0 \
    pytz>=2023.3 \
    python-dotenv>=1.0.0 \
    beautifulsoup4>=4.12.0 \
    feedparser>=6.0.10 \
    pyfedwatch>=1.2.0 \
    psutil>=5.9.0 \
    "fastapi>=0.104.0" \
    "uvicorn[standard]>=0.24.0" \
    "httpx>=0.27.0" \
    "google-generativeai>=0.3.0" \
    "cohere>=5.0.0" \
    "groq>=0.9.0" \
    "finnhub-python>=2.4.0" \
    "cot_reports>=0.1.0" \
    "supabase>=2.0.0" \
    "ta>=0.11.0" \
    "scikit-learn>=1.3.0" \
    "langgraph>=0.3.0" \
    "langchain-groq>=0.3.0"

# Copy application code
COPY . .

# Railway injects PORT at runtime
ENV PORT=8000
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1

# API_LIGHT_MODE=1 skips UnifiedAlphaMonitor (~300-400MB startup bomb).
# All API endpoints remain functional via compute_kill_chain() in the API layer.
ENV API_LIGHT_MODE=1

EXPOSE $PORT

CMD ["uvicorn", "backend.app.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1"]
