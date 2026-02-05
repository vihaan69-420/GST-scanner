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
RUN mkdir -p /app/temp /app/exports /app/logs

# Expose health check port
EXPOSE 8080

# Environment defaults (can be overridden)
ENV PYTHONUNBUFFERED=1
ENV HEALTH_SERVER_PORT=8080
ENV HEALTH_SERVER_ENABLED=true

# Run the bot
CMD ["python", "start_bot.py"]
