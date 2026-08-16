# Production Deployment Guide — DevPilot Platform

This guide covers deploying the DevPilot AI coding platform to production, including setup, architecture, distributed workers, security hardening, monitoring, and incident response.

---

## 1. Architecture Overview

```
[ Web UI / VS Code Extension ]
             │ (HTTP / WebSocket)
             ▼
[ FastAPI Control Plane (backend.app.main:app) ]
             │
             ├── PostgreSQL (Persisted state: AgentRun, AgentCheckpoint, Conversation, Message)
             ├── Redis (Distributed Job Queue: AgentQueue, Events: EventPublisher, Locks: RunLock)
             └── Local Session Fallback (Desktop Mode)
             │
             ▼
[ Distributed Agent Workers (backend.app.infrastructure.worker) ]
             ├── Claim Job from Redis
             ├── Acquire Distributed RunLock
             ├── Canonical AgentRuntime (State Machine, Sandboxing, Checkpoints)
             ├── ResultAdapter (Deterministic single terminal session_done)
             └── RetryPolicy (Configurable transient error retry)
```

---

## 2. Prerequisites & Requirements

### System Requirements
- **Python**: 3.10+ (Python 3.12 supported)
- **Node.js**: 18+ (for Web UI build)
- **PostgreSQL**: 13+ (Relational persistence)
- **Redis**: 6.2+ (Task queue, Pub/Sub, distributed locks)
- **Docker**: 20.10+ (For sandboxed terminal tool execution)

### Core Environment Variables

```bash
# === Database & Queue ===
export DATABASE_URL="postgresql+asyncpg://devpilot:password@postgres:5432/devpilot_prod"
export REDIS_URL="redis://redis:6379/0"

# === Security & Master Key ===
export SECRET_KEY="generate-a-secure-random-32-byte-hex-key"
export DEVPILOT_MASTER_KEY="fernet-32-byte-base64-key-from-kms-or-vault"
export USE_SANDBOX="True"
export SANDBOX_IMAGE="python:3.12-slim"

# === LLM Provider Credentials ===
export OPENAI_API_KEY="sk-..."
export ANTHROPIC_API_KEY="sk-ant-..."
export GROQ_API_KEY="gsk_..."
export OLLAMA_BASE_URL="http://localhost:11434/v1"

# === Execution Limits ===
export DEVPILOT_MAX_TURNS="25"
export DEVPILOT_LLM_TURN_TIMEOUT="600.0"
```

---

## 3. Deployment Steps

### Step 1: Database Migration
Run Alembic migrations to initialize the schema:

```bash
# From project root
alembic upgrade head
```

### Step 2: Secret Management & KMS Integration
For production, set `DEVPILOT_MASTER_KEY` via your secret manager (AWS Secrets Manager, HashiCorp Vault, Google Secret Manager, or Kubernetes Secret):

```bash
# Generate a Fernet key if initializing fresh:
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

### Step 3: Run the FastAPI Control Plane
Start the API and WebSocket server:

```bash
uvicorn backend.app.main:app --host 0.0.0.0 --port 8000 --workers 4
```

Or using Gunicorn with Uvicorn workers:

```bash
gunicorn backend.app.main:app \
    --workers 4 \
    --worker-class uvicorn.workers.UvicornWorker \
    --bind 0.0.0.0:8000
```

### Step 4: Run Distributed Agent Workers
Start one or more worker processes to process background agent tasks:

```bash
python -m backend.app.infrastructure.worker
```

Scale horizontally by launching additional worker instances or containers pointing to the same Redis and PostgreSQL instances.

---

## 4. Security Hardening Checklist

1. **Filesystem Isolation**:
   - `SecureFileSystem` strictly enforces workspace boundary checks using `os.path.realpath` before operations.
   - Symlinks escaping the workspace root are rejected with `PermissionError`.
2. **Terminal Sandboxing**:
   - `USE_SANDBOX=True` routes terminal commands into ephemeral Docker containers.
   - Host execution fallback is strictly disabled in production.
3. **Tool Approval Enforcement**:
   - High-risk operations (e.g. executing destructive commands) require explicit interactive confirmation or fail-closed.
4. **Keyring Permissions**:
   - Local fallback keyrings enforce `0600` file permissions under `~/.devpilot/`.

---

## 5. Monitoring, Health Checks & Observability

- **Health Endpoint**: `GET /health` returns control-plane, DB, and Redis connectivity status.
- **Prometheus Metrics**: `GET /metrics` exposes OpenTelemetry counters for tool executions, retries, and errors.
- **Worker Telemetry**: Worker heartbeat and stale run recovery runs automatically every 60 seconds via `AgentQueue.recover_stale_jobs()`.
