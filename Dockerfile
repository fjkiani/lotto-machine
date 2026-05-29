FROM python:3.11-slim

# System deps needed by some packages (ta-lib, psutil, etc.)
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    g++ \
    libffi-dev \
    libssl-dev \
    curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copy requirements first (layer cache — only reinstalls when requirements change)
COPY requirements-deploy.txt ./requirements-deploy.txt

# Install production deps only — no streamlit, no redis, no alpaca, no discord
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements-deploy.txt

# Copy application code
COPY . .

# Railway injects PORT at runtime
ENV PORT=8000
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1

# API_LIGHT_MODE=1 skips UnifiedAlphaMonitor (~300-400MB startup bomb)
# All API endpoints remain functional via compute_kill_chain() in the API layer
ENV API_LIGHT_MODE=1

EXPOSE $PORT

CMD uvicorn backend.app.main:app --host 0.0.0.0 --port $PORT --workers 1
