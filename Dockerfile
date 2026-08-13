# --- Build Frontend ---
FROM node:20-alpine AS frontend-builder
WORKDIR /app/frontend

COPY frontend/package*.json ./
RUN npm ci

COPY frontend/ ./
RUN npm run build

# --- Build Runtime Image ---
FROM python:3.12-slim
WORKDIR /app

# Create non-root group and user (Section 2 & 3 requirement)
RUN groupadd -g 10001 devpilot && \
    useradd -u 10001 -g devpilot -m -s /bin/bash devpilot

# Install system dependencies (including bash/git/curl for terminal operations)
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    bash \
    git \
    curl \
    ripgrep \
    && rm -rf /var/lib/apt/lists/*

# Copy backend requirements and install them
COPY backend/requirements.txt ./backend/
RUN pip install --no-cache-dir -r backend/requirements.txt

ARG INSTALL_PLAYWRIGHT=false
RUN if [ "$INSTALL_PLAYWRIGHT" = "true" ] ; then \
        playwright install --with-deps chromium ; \
    fi

# Copy built frontend dist folder so FastAPI can serve it statically
COPY --from=frontend-builder /app/frontend/dist ./frontend/dist

# Copy backend application code
COPY backend/ ./backend/

# Assign ownership of directory to devpilot user
RUN chown -R devpilot:devpilot /app

# Switch to non-root user
USER devpilot

# Expose backend port
EXPOSE 8000

# Set environment variables for production/docker deployment
ENV PORT=8000 \
    HOST=0.0.0.0 \
    PYTHONPATH=/app \
    DOCKER_MODE=true \
    ALLOW_REMOTE=true

HEALTHCHECK --interval=30s --timeout=5s --start-period=5s --retries=3 \
  CMD curl -f http://localhost:8000/health/live || exit 1

# Start DevPilot backend
CMD ["python", "backend/run.py"]
