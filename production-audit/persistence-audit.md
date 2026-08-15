# Persistence Audit — DevPilot IDE Platform

This document details the current data persistence mechanisms, identifies hardcoded paths and database migration bottlenecks, and provides a target database schema for hosted production.

---

## 1. Current Persistence Architecture

- **Database Support:** Multi-database support with SQLite (local development/desktop) and PostgreSQL (production server), using `SQLAlchemy 2.x`, `asyncpg`, and `aiosqlite`.
- **Relational Schema:** Fully normalized multi-tenant models (`Organization`, `User`, `Workspace`, `Conversation`, `Message`, `AgentRun`, `AgentStep`, `ToolCall`, `Approval`, `AgentEvent`, `UsageRecord`, `Artifact`).
- **Migrations:** Managed via Alembic (`alembic.ini` and `alembic/` migration scripts).
- **Session Identity:** Single canonical session lifecycle with tenant/user authorization boundaries. Message sequence uniqueness is enforced via `UNIQUE(conversation_id, sequence)`.
- **Durability:** Messages are persisted idempotently per sequence. Eager loading with `selectinload` avoids greenlet issues in async sessions.

---

## 2. Production Scalability & Multi-Tenancy Status

1. **Schema Migration:**
   - Production uses Alembic migrations for continuous schema evolution on PostgreSQL.
2. **Multi-Tenancy & Authorization:**
   - Multi-tenant tenant boundaries (`organization_id`, `user_id`, `workspace_id`) are enforced across all chat routes, sessions, history, and WebSocket connections.
3. **Dual History Deprecation:**
   - The normalized `messages` table serves as the primary source of truth for conversation history.

---

## 3. Production PostgreSQL Schema Definition

For a scalable hosted production deployment, we propose the following normalized relational schema:

```sql
-- Multi-tenancy Boundaries
CREATE TABLE organizations (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name VARCHAR(255) NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE users (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    email VARCHAR(255) UNIQUE NOT NULL,
    hashed_password VARCHAR(255) NOT NULL,
    role VARCHAR(50) NOT NULL DEFAULT 'DEVELOPER', -- OWNER, ADMIN, DEVELOPER, VIEWER
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE memberships (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    org_id UUID REFERENCES organizations(id) ON DELETE CASCADE,
    user_id UUID REFERENCES users(id) ON DELETE CASCADE,
    role VARCHAR(50) NOT NULL DEFAULT 'DEVELOPER',
    UNIQUE (org_id, user_id)
);

CREATE TABLE workspaces (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    org_id UUID REFERENCES organizations(id) ON DELETE CASCADE,
    root_path VARCHAR(1024) NOT NULL,
    name VARCHAR(255) NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Agent Job & Task State
CREATE TABLE agent_runs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    org_id UUID REFERENCES organizations(id) ON DELETE CASCADE,
    user_id UUID REFERENCES users(id) ON DELETE CASCADE,
    workspace_id UUID REFERENCES workspaces(id) ON DELETE CASCADE,
    state VARCHAR(50) NOT NULL, -- IDLE, PLANNING, EXECUTING, etc.
    task_description TEXT NOT NULL,
    budget_usd NUMERIC(10, 4) DEFAULT 10.0,
    cost_usd NUMERIC(10, 4) DEFAULT 0.0,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE agent_steps (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    run_id UUID REFERENCES agent_runs(id) ON DELETE CASCADE,
    step_number INTEGER NOT NULL,
    thinking TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE tool_calls (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    run_id UUID REFERENCES agent_runs(id) ON DELETE CASCADE,
    tool_name VARCHAR(100) NOT NULL,
    arguments JSONB NOT NULL,
    output TEXT,
    success BOOLEAN NOT NULL,
    duration_seconds NUMERIC(8, 3),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE agent_events (
    id BIGSERIAL PRIMARY KEY,
    run_id UUID REFERENCES agent_runs(id) ON DELETE CASCADE,
    sequence_number INTEGER NOT NULL,
    event_type VARCHAR(100) NOT NULL,
    payload JSONB NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (run_id, sequence_number)
);

CREATE TABLE audit_records (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    org_id UUID REFERENCES organizations(id) ON DELETE CASCADE,
    user_id UUID REFERENCES users(id) ON DELETE CASCADE,
    action VARCHAR(100) NOT NULL,
    resource TEXT,
    risk VARCHAR(50) NOT NULL,
    decision VARCHAR(50) NOT NULL,
    timestamp TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);
```
