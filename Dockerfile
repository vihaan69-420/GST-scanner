FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies first (for caching)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Create temp directories
RUN mkdir -p /app/temp /app/exports /app/logs /app/data /app/orders

# Expose the single HTTP port (Cloud Run routes all traffic here via PORT)
EXPOSE 8080

# Environment defaults (can be overridden via Cloud Run env vars)
ENV PYTHONUNBUFFERED=1
ENV HEALTH_SERVER_PORT=8080
ENV HEALTH_SERVER_ENABLED=true
ENV FEATURE_API_ENABLED=false
ENV API_HOST=0.0.0.0

# Run the bot (FastAPI starts alongside it when FEATURE_API_ENABLED=true)
CMD ["python", "start_bot.py"]
