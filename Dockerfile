FROM python:3.11-slim

# Create non-root user
RUN useradd --create-home appuser

WORKDIR /app

# Install procps for pgrep (required by Docker HEALTHCHECK)
RUN apt-get update && apt-get install -y --no-install-recommends procps \
    && rm -rf /var/lib/apt/lists/*

# Install dependencies (cached layer - only rebuilds when pyproject.toml changes)
COPY pyproject.toml .
# Copy __init__.py so setuptools can resolve version attr before full code copy
COPY gaelcarebot/__init__.py gaelcarebot/__init__.py
RUN pip install --no-cache-dir .

# Copy application code (rebuilds on every code change)
COPY gaelcarebot/ gaelcarebot/

# Create data directory for SQLite DB (must be writable by appuser)
RUN mkdir -p /data && chown appuser:appuser /data

USER appuser

VOLUME ["/data"]

HEALTHCHECK --interval=30s --timeout=10s --start-period=15s --retries=3 \
  CMD pgrep -f "python -m gaelcarebot.bot" || exit 1

CMD ["python", "-m", "gaelcarebot.bot"]
