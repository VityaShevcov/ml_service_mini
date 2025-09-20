# Multi-stage Docker build for ML Chat Billing Service
FROM python:3.9-slim as base

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# Install system dependencies
RUN apt-get update && apt-get install -y \
    build-essential \
    curl \
    git \
    && rm -rf /var/lib/apt/lists/*

# Create app user
RUN useradd --create-home --shell /bin/bash app

# Set work directory
WORKDIR /app

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Create necessary directories
RUN mkdir -p logs data && \
    chown -R app:app /app

# Switch to app user
USER app

# Expose ports
EXPOSE 8000 7861

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

# Default command
CMD ["python", "startup.py"]

# =============================================================================
# Production stage
# =============================================================================
FROM base as production

# Install production dependencies only
COPY requirements-prod.txt .
RUN pip install --no-cache-dir -r requirements-prod.txt

# Set production environment
ENV DEBUG=false \
    LOG_LEVEL=WARNING \
    ENABLE_PERFORMANCE_MONITORING=true

# Use gunicorn for production
CMD ["gunicorn", "main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "4", "--worker-class", "uvicorn.workers.UvicornWorker"]

# =============================================================================
# Development stage
# =============================================================================
FROM base as development

# Install development dependencies
COPY requirements-dev.txt .
RUN pip install --no-cache-dir -r requirements-dev.txt

# Set development environment
ENV DEBUG=true \
    LOG_LEVEL=DEBUG \
    RELOAD_ON_CHANGE=true

# Mount volumes for development
VOLUME ["/app/logs", "/app/data"]

# Development command with auto-reload
CMD ["python", "startup.py"]