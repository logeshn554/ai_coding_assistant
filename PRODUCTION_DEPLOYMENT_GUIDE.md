# Production Deployment Guide - AI Coding Agent Orchestrator

## Overview

This guide covers deploying the AI coding agent orchestrator to production, including setup, monitoring, troubleshooting, and incident response.

---

## Prerequisites

### System Requirements
- Python 3.9+
- Git 2.35+
- Docker (optional, for containerization)
- PostgreSQL 12+ (for persistent storage)
- Redis 6+ (for distributed caching)

### Dependencies
```bash
pip install -r requirements.txt
```

### Environment Variables
```bash
# LLM Configuration
export OPENAI_API_KEY=sk-...
export ANTHROPIC_API_KEY=sk-ant-...
export LLM_MODEL_PRIMARY=gpt-4  # or claude-3-opus
export LLM_MODEL_FALLBACK=gpt-3.5-turbo

# Infrastructure
export POSTGRES_URL=postgresql://user:pass@localhost/agent_orchestrator
export REDIS_URL=redis://localhost:6379
export CHECKPOINT_DIR=/var/lib/agent_orchestrator/checkpoints
export LOG_DIR=/var/log/agent_orchestrator

# Agent Configuration
export MAX_CONCURRENT_AGENTS=10
export TOKEN_BUDGET_DEFAULT=50000
export COST_BUDGET_DEFAULT_USD=10.0
export WORKSPACE_ROOT=/tmp/agent_workspaces
export GIT_WORKTREE_ROOT=/tmp/agent_worktrees
```

---

## Deployment Steps

### 1. Database Setup

```bash
# Initialize PostgreSQL
psql -U postgres -d agent_orchestrator < schema.sql

# Create tables for runs, tasks, events, checkpoints
CREATE TABLE runs (
    run_id VARCHAR PRIMARY KEY,
    status VARCHAR,
    created_at TIMESTAMP,
    completed_at TIMESTAMP,
    cost_usd DECIMAL(10,4)
);

CREATE TABLE tasks (
    task_id VARCHAR PRIMARY KEY,
    run_id VARCHAR REFERENCES runs(run_id),
    status VARCHAR,
    agent_id VARCHAR,
    result JSONB
);

CREATE TABLE events (
    event_id VARCHAR PRIMARY KEY,
    run_id VARCHAR REFERENCES runs(run_id),
    event_type VARCHAR,
    timestamp TIMESTAMP,
    payload JSONB
);

CREATE TABLE checkpoints (
    checkpoint_id VARCHAR PRIMARY KEY,
    run_id VARCHAR REFERENCES runs(run_id),
    created_at TIMESTAMP,
    metadata JSONB
);
```

### 2. Setup Checkpoint Storage

```bash
# Create checkpoint directories
mkdir -p /var/lib/agent_orchestrator/checkpoints
mkdir -p /tmp/agent_workspaces
mkdir -p /tmp/agent_worktrees

# Set permissions
chmod 755 /var/lib/agent_orchestrator
chmod 755 /tmp/agent_workspaces
chmod 755 /tmp/agent_worktrees
```

### 3. Initialize Redis Cache

```bash
# Start Redis
redis-server --bind 127.0.0.1 --port 6379

# Or use Docker
docker run -d -p 6379:6379 redis:latest
```

### 4. Configure Application

```python
# config/production.py
import os

class ProductionConfig:
    DEBUG = False
    LOG_LEVEL = "INFO"
    
    # LLM
    LLM_MODEL = os.getenv("LLM_MODEL_PRIMARY", "gpt-4")
    LLM_FALLBACK = os.getenv("LLM_MODEL_FALLBACK", "gpt-3.5-turbo")
    
    # Database
    DATABASE_URL = os.getenv("POSTGRES_URL")
    CACHE_URL = os.getenv("REDIS_URL")
    
    # Limits
    MAX_CONCURRENT_AGENTS = int(os.getenv("MAX_CONCURRENT_AGENTS", "10"))
    TOKEN_BUDGET = int(os.getenv("TOKEN_BUDGET_DEFAULT", "50000"))
    COST_BUDGET_USD = float(os.getenv("COST_BUDGET_DEFAULT_USD", "10.0"))
    
    # Paths
    CHECKPOINT_DIR = os.getenv("CHECKPOINT_DIR")
    WORKSPACE_ROOT = os.getenv("WORKSPACE_ROOT")
```

### 5. Start Application

```bash
# Development (local testing)
python -m agent_os.cli --goal "Create test script" --workspace /tmp/test_ws

# Production (with gunicorn)
gunicorn --workers 4 --threads 2 --worker-class=gthread \
    --bind 0.0.0.0:8000 \
    agent_os.api:app

# Or with Docker
docker run -d \
    -e OPENAI_API_KEY=$OPENAI_API_KEY \
    -e POSTGRES_URL=$POSTGRES_URL \
    -e REDIS_URL=$REDIS_URL \
    -p 8000:8000 \
    agent-orchestrator:latest
```

---

## Monitoring & Observability

### Log Configuration

```bash
# Log to file with rotation
import logging.handlers

handler = logging.handlers.RotatingFileHandler(
    "/var/log/agent_orchestrator/app.log",
    maxBytes=100_000_000,  # 100MB
    backupCount=10
)

formatter = logging.Formatter(
    '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
handler.setFormatter(formatter)
```

### Key Metrics to Monitor

```
1. Agent Execution
   - agents_running (gauge)
   - agents_completed_total (counter)
   - agents_failed_total (counter)
   - agent_duration_seconds (histogram)

2. LLM Usage
   - llm_calls_total (counter)
   - llm_tokens_used_total (counter)
   - llm_cost_usd_total (counter)
   - llm_latency_seconds (histogram)

3. Tool Execution
   - tool_calls_total (counter)
   - tool_errors_total (counter)
   - tool_duration_seconds (histogram)

4. Budget
   - budget_exceeded_total (counter)
   - cost_usd_current (gauge)
   - tokens_used_current (gauge)

5. System
   - checkpoint_save_duration_seconds (histogram)
   - workspace_health_check_failures (counter)
   - database_connection_errors (counter)
```

### Prometheus Metrics Endpoint

```python
from prometheus_client import Counter, Histogram, Gauge

agents_running = Gauge('agents_running', 'Number of running agents')
agents_completed = Counter('agents_completed_total', 'Total completed agents')
llm_cost = Counter('llm_cost_usd_total', 'Total LLM cost in USD')
llm_latency = Histogram('llm_latency_seconds', 'LLM call latency')
```

### Alerting Rules

```yaml
# prometheus/rules.yml
groups:
  - name: agent_orchestrator
    rules:
      - alert: HighAgentFailureRate
        expr: rate(agents_failed_total[5m]) > 0.2
        for: 5m
        annotations:
          summary: "High agent failure rate ({{ $value | humanizePercentage }})"

      - alert: BudgetExceeded
        expr: budget_exceeded_total > 0
        annotations:
          summary: "Agent budget exceeded"

      - alert: LLMLatencyHigh
        expr: histogram_quantile(0.95, llm_latency_seconds) > 10
        for: 5m
        annotations:
          summary: "LLM latency p95 > 10s"

      - alert: WorkspaceHealthCheck
        expr: workspace_health_check_failures > 5
        annotations:
          summary: "Workspace health checks failing"
```

---

## Troubleshooting

### Agent Stuck in Running State

**Symptom:** Agent remains in RUNNING state for >timeout

**Investigation:**
```bash
# Check execution log
SELECT * FROM events 
WHERE run_id = 'run-xyz' 
ORDER BY timestamp DESC 
LIMIT 20;

# Check LLM latency
grep "LLM_LATENCY" /var/log/agent_orchestrator/app.log | tail -20

# Inspect workspace
ls -la /tmp/agent_workspaces/run-xyz/
```

**Resolution:**
1. Check if LLM provider is responsive: `curl https://api.openai.com/v1/models`
2. Check network connectivity
3. Manual cancellation: `POST /api/runs/run-xyz/cancel`
4. Cleanup workspace: `rm -rf /tmp/agent_workspaces/run-xyz/`

### High Memory Usage

**Investigation:**
```bash
# Check checkpoint size
du -sh /var/lib/agent_orchestrator/checkpoints/

# Check agent memory
ps aux | grep agent

# Monitor memory
watch -n 1 'free -h'
```

**Resolution:**
```bash
# Cleanup old checkpoints
python -c "
from agent_os.agent import CheckpointManager
cm = CheckpointManager('/var/lib/agent_orchestrator/checkpoints')
for run_id in cm.checkpoint_dir.iterdir():
    cm.cleanup_old_checkpoints(run_id.name, keep_last_n=3)
"

# Clear old workspaces
find /tmp/agent_workspaces -type d -mtime +7 -exec rm -rf {} \;
```

### Verification Failures

**Symptom:** Verification always fails

**Investigation:**
```bash
# Check test infrastructure
which pytest
pytest --version

# Check Python environment
python -m py_compile test_file.py

# Verify in workspace
cd /tmp/agent_workspaces/run-xyz
python -m pytest -v
```

**Resolution:**
1. Install missing test framework: `pip install pytest`
2. Check Python version compatibility
3. Install project dependencies in workspace
4. Run verification manually to identify issue

### Tool Execution Timeout

**Symptom:** Tools timeout frequently

**Investigation:**
```bash
# Check system load
uptime
top -b -n 1 | head -20

# Check disk space
df -h /tmp

# Check tool logs
grep "TOOL_TIMEOUT" /var/log/agent_orchestrator/app.log
```

**Resolution:**
```python
# Increase timeout in config
TOOL_TIMEOUT_SECONDS = 60  # Increase from 30

# Or specific tool
tool_def.timeout_seconds = 120
```

---

## Incident Response

### Critical Alert: Multiple Agents Failed

1. **Immediate Actions**
   - Check LLM provider status: https://status.openai.com
   - Check database connectivity: `psql -U postgres -c "SELECT 1"`
   - Check API rate limits: Review recent LLM cost logs
   - Stop new agent submissions (if needed)

2. **Diagnosis**
   ```bash
   # Get failure details
   SELECT run_id, status, error 
   FROM runs 
   WHERE status = 'failed' 
   AND created_at > NOW() - INTERVAL '1 hour'
   ORDER BY created_at DESC;

   # Get error patterns
   SELECT error, COUNT(*) 
   FROM runs 
   GROUP BY error 
   ORDER BY count DESC;
   ```

3. **Recovery**
   - Resume from checkpoint: `POST /api/runs/{run_id}/resume`
   - Retry with different model: Update LLM_MODEL_FALLBACK
   - Clear cache: `redis-cli FLUSHALL`
   - Restart agents: `systemctl restart agent-orchestrator`

### High Cost Alert

1. **Investigation**
   ```sql
   SELECT agent_id, SUM(cost_usd) as total_cost, COUNT(*) as runs
   FROM runs
   GROUP BY agent_id
   ORDER BY total_cost DESC;
   ```

2. **Actions**
   - Review recent tasks for inefficiencies
   - Check model selection (use cheaper model if possible)
   - Reduce token budget for new runs
   - Enable cost limit enforcement

---

## Performance Tuning

### Optimize Concurrent Agents
```python
# In production.py
MAX_CONCURRENT_AGENTS = 20  # Increase based on load

# Adjust semaphore in DAGExecutor
executor = DAGExecutor(max_concurrent=20)
```

### Improve LLM Latency
```python
# Enable caching
from functools import lru_cache
llm_cache = lru_cache(maxsize=1000)

# Use batch requests
# Instead of 10 sequential calls, use batch API
```

### Database Optimization
```sql
-- Create indexes for common queries
CREATE INDEX idx_runs_created_at ON runs(created_at);
CREATE INDEX idx_runs_status ON runs(status);
CREATE INDEX idx_events_run_id ON events(run_id);
CREATE INDEX idx_events_timestamp ON events(timestamp);

-- Vacuum and analyze
VACUUM ANALYZE;
```

---

## Backup & Recovery

### Backup Strategy

```bash
#!/bin/bash
# daily-backup.sh

BACKUP_DIR="/backup/agent_orchestrator"
DATE=$(date +%Y%m%d_%H%M%S)

# Backup database
pg_dump agent_orchestrator | gzip > "$BACKUP_DIR/db_$DATE.sql.gz"

# Backup checkpoints
tar -czf "$BACKUP_DIR/checkpoints_$DATE.tar.gz" \
    /var/lib/agent_orchestrator/checkpoints

# Backup config
cp -r /etc/agent_orchestrator "$BACKUP_DIR/config_$DATE"

# Retention: Keep last 30 days
find "$BACKUP_DIR" -mtime +30 -delete
```

### Recovery Procedure

```bash
# 1. Restore database
gunzip -c db_20240101_000000.sql.gz | psql agent_orchestrator

# 2. Restore checkpoints
tar -xzf checkpoints_20240101_000000.tar.gz -C /var/lib/agent_orchestrator

# 3. Verify integrity
psql agent_orchestrator -c "SELECT COUNT(*) FROM runs;"
ls -la /var/lib/agent_orchestrator/checkpoints | head -10

# 4. Resume interrupted runs
python -c "
from agent_os.agent import CheckpointManager
cm = CheckpointManager()
for run_id in cm.checkpoint_dir.iterdir():
    latest = cm.get_latest_checkpoint(run_id.name)
    if latest and latest['state'] != 'completed':
        print(f'Resume: {run_id.name}')
"
```

---

## Scaling Considerations

### Horizontal Scaling

```python
# Use message queue for distributed execution
import celery

# In production:
# - Run multiple agent orchestrator instances
# - Use shared database for coordination
# - Use Redis for distributed caching
# - Use message queue (RabbitMQ/Kafka) for task distribution

app = celery.Celery()

@app.task
def execute_agent_task(task_id, agent_type):
    # Execute in distributed worker
    pass
```

### Load Balancing

```yaml
# nginx.conf
upstream agent_orchestrator {
    server localhost:8000;
    server localhost:8001;
    server localhost:8002;
}

server {
    listen 80;
    server_name agent-orchestrator.example.com;

    location / {
        proxy_pass http://agent_orchestrator;
        proxy_buffering off;
    }
}
```

---

## Security Checklist

- [ ] LLM API keys stored in secure vault (not in code/config)
- [ ] Database credentials encrypted in transit (TLS/SSL)
- [ ] Workspace directories have restricted permissions (700)
- [ ] Checkpoint storage encrypted at rest
- [ ] Rate limiting enabled on API endpoints
- [ ] Input validation on all user inputs
- [ ] Audit logging enabled for all agent actions
- [ ] Regular security updates applied
- [ ] File ownership enforcement active
- [ ] Forbidden paths protection enabled

---

## Runbook Commands

### Quick Status Check
```bash
# Are services running?
systemctl status agent-orchestrator
systemctl status postgresql
systemctl status redis-server

# Any recent errors?
tail -50 /var/log/agent_orchestrator/app.log | grep ERROR

# Current metrics
curl http://localhost:8000/metrics | grep agent

# Database connectivity
psql -U agent_orchestrator -h localhost -c "SELECT 1"
```

### Restart Services
```bash
# Full restart
systemctl restart agent-orchestrator postgresql redis-server

# Graceful reload (no new agents, finish existing)
curl -X POST http://localhost:8000/admin/graceful-shutdown

# Force restart (kill all agents)
systemctl restart agent-orchestrator
```

### View Recent Runs
```bash
# Last 10 runs
psql -U agent_orchestrator -c "
  SELECT run_id, status, created_at, cost_usd 
  FROM runs 
  ORDER BY created_at DESC 
  LIMIT 10;"

# Failed runs in last hour
psql -U agent_orchestrator -c "
  SELECT run_id, error
  FROM runs
  WHERE status = 'failed'
  AND created_at > NOW() - INTERVAL '1 hour';"
```

---

## Conclusion

The AI coding agent orchestrator is now production-ready. Key takeaways:

1. **Monitor closely** - Set up comprehensive metrics and alerts
2. **Backup regularly** - Implement automated backup strategy
3. **Scale gradually** - Start with single instance, then distribute
4. **Secure properly** - Protect API keys and sensitive data
5. **Document changes** - Keep runbooks updated as system evolves

For support, check logs, metrics, and run diagnostic commands from the runbook above.
