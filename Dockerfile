FROM python:3.12-slim

WORKDIR /app

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PORT=8000

# Install system dependencies if required
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy backend application and client script
COPY server/ ./server/
COPY standalone_client.py ./standalone_client.py

# Create persistent data directory for SQLite if PostgreSQL is not attached
RUN mkdir -p /app/data

EXPOSE 8000

# Start server honoring Railway dynamic PORT
CMD ["sh", "-c", "uvicorn server.app:app --host 0.0.0.0 --port ${PORT:-8000}"]
