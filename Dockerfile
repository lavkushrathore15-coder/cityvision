# CITYVISION AI - Production Containerfile for Hugging Face Spaces & Cloud Docker
# Runs on Hugging Face Spaces Free Tier (2 vCPU, 16 GB RAM) at $0 cost
FROM python:3.11-slim

# Install system dependencies required for OpenCV, video processing, and network tools
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libgl1 \
    libglib2.0-0 \
    libgomp1 \
    ffmpeg \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Set up standard Hugging Face Spaces non-root user (UID 1000)
RUN useradd -m -u 1000 user
ENV HOME=/home/user \
    PATH=/home/user/.local/bin:$PATH \
    PYTHONUNBUFFERED=1 \
    PORT=8000 \
    INFERENCE_DEVICE=cpu

WORKDIR $HOME/app

# Install Python ML and backend dependencies
COPY --chown=user:user requirements.txt .
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Copy application directories with user ownership
COPY --chown=user:user backend/ ./backend/
COPY --chown=user:user ai/ ./ai/
COPY --chown=user:user config/ ./config/
COPY --chown=user:user data/ ./data/
COPY --chown=user:user models/ ./models/
COPY --chown=user:user alembic.ini ./

# Ensure data directory and cache folders are fully writable by user 1000
RUN mkdir -p $HOME/app/data && chmod -R 777 $HOME/app/data && \
    mkdir -p $HOME/.cache && chmod -R 777 $HOME/.cache

USER user

EXPOSE 8000

# Launch FastAPI backend with uvicorn listening on 0.0.0.0 and port $PORT (default 8000)
CMD ["sh", "-c", "uvicorn backend.app.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
