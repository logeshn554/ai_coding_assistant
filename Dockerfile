# --- Build Frontend ---
FROM node:20-alpine AS frontend-builder
WORKDIR /app/frontend

COPY frontend/package*.json ./
RUN npm ci

COPY frontend/ ./
RUN npm run build

# --- Build Runtime Image ---
FROM python:3.11-slim
WORKDIR /app

# Install system dependencies (including bash/git/curl for terminal operations)
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    bash \
    git \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy backend requirements and install them
COPY backend/requirements.txt ./backend/
RUN pip install --no-cache-dir -r backend/requirements.txt

# Copy and install parallel_agent_system
COPY parallel_agent_system/ ./parallel_agent_system/
RUN pip install --no-cache-dir ./parallel_agent_system

# Copy built frontend dist folder so FastAPI can serve it statically
COPY --from=frontend-builder /app/frontend/dist ./frontend/dist

# Copy backend application code
COPY backend/ ./backend/

# Expose backend port
EXPOSE 8000

# Set environment variables for production/docker deployment
ENV PORT=8000 \
    HOST=0.0.0.0 \
    PYTHONPATH=/app \
    DOCKER_MODE=true \
    ALLOW_REMOTE=true

# Start DevPilot backend
CMD ["python", "backend/run.py"]
