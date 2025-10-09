# Multi-stage build for ARM and AMD64 architectures
FROM python:3.12-alpine AS builder

# Install build dependencies and Python packages in a single layer
COPY requirements.txt .
RUN apk add --no-cache \
        gcc \
        musl-dev \
        libffi-dev \
        openssl-dev \
        postgresql-dev \
        jpeg-dev \
        zlib-dev \
        libjpeg \
        build-base && \
    pip install --no-cache-dir --upgrade pip setuptools wheel && \
    pip install --no-cache-dir --user -r requirements.txt && \
    apk del gcc musl-dev libffi-dev openssl-dev build-base

# Final stage
FROM python:3.12-alpine

# Set environment variables early for layer caching
ENV PYTHONPATH=/app \
    PYTHONUNBUFFERED=1 \
    PATH=/root/.local/bin:$PATH

# Install runtime dependencies and setup in a single layer
RUN apk add --no-cache \
        ffmpeg \
        wget \
        postgresql-libs \
        jpeg \
        zlib && \
    mkdir -p /app/downloads /app/config

# Copy Python packages from builder stage
COPY --from=builder /root/.local /root/.local

# Set working directory
WORKDIR /app

# Copy entrypoint script first (less likely to change)
COPY docker-entrypoint.sh /usr/local/bin/
RUN chmod +x /usr/local/bin/docker-entrypoint.sh

# Copy application code last (most likely to change)
COPY . .

# Expose port
EXPOSE 9833

# Set entrypoint and default command
ENTRYPOINT ["/usr/local/bin/docker-entrypoint.sh"]
CMD ["python", "main.py"]
