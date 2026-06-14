FROM python:3.11-slim

# Create non-root user
RUN useradd --create-home appuser

WORKDIR /app

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY src/ src/

# Create data directory for SQLite DB (must be writable by appuser)
RUN mkdir -p /data && chown appuser:appuser /data

USER appuser

VOLUME ["/data"]

CMD ["python", "-m", "src.bot"]
