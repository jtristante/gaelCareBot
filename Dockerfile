FROM python:3.11-slim

# Create non-root user
RUN useradd --create-home appuser

WORKDIR /app

# Install dependencies
COPY pyproject.toml .
COPY gaelcarebot/ gaelcarebot/
RUN pip install --no-cache-dir .

# Create data directory for SQLite DB (must be writable by appuser)
RUN mkdir -p /data && chown appuser:appuser /data

USER appuser

VOLUME ["/data"]

CMD ["python", "-m", "gaelcarebot.bot"]
