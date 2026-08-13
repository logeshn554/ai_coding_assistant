# Persistence Audit — DevPilot IDE Platform

This document details the current data persistence mechanisms, identifies hardcoded paths and database migration bottlenecks, and provides a target database schema for hosted production.

---

## 1. Current Persistence Review

- **Database Engine:** SQLite (using `SQLAlchemy 2.x` and `aiosqlite` driver).
- **File Location:** Hardcoded to `~/.devpilot/history.db` in [db.py](file:///e:/os%20kernel%20with%20ani/ai_coding_assistant/backend/app/db.py).
- **JSON Configuration:** Local settings and MCP server profiles are read/written to `~/.devpilot/config.json`. Keyring is used for API keys.
- **Volatile In-Memory Storage:**
  - Connection tickets (`_ws_tickets`) in `state.py`.
  - Session workspace roots (`_session_roots`) in `state.py`.
  - Agent run states, tasks, and cancellation flags in `AgentRuntime`.
  - Terminal process IDs and logs in `processes.py`.

---

## 2. Bottlenecks for Production/Multi-Instance Scale

1. **Ad-Hoc Migration Logic:**
   - [db.py](file:///e:/os%20kernel%20with%20ani/ai_coding_assistant/backend/app/db.py) defines an inline `_ensure_session_columns` migrator. This uses SQLite-specific PRAGMA queries (`PRAGMA table_info(sessions)`) and SQLite ALTER syntax. It will fail immediately if pointed to PostgreSQL.
2. **Missing Alembic Configuration:**
   - There are no Alembic configuration files or migration history files. Database updates must be applied manually.
3. **No Multi-Tenancy:**
   - The `sessions` and `chat_sessions` tables lack a `tenant_id` or `user_id` foreign key. All sessions are globally visible to anyone connecting to the SQLite database.

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
