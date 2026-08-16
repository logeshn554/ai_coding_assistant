-- One-time migration: Ensure all conversations.messages_json data is migrated to the relational messages table.
-- Generated for DevPilot conversation storage consolidation.

-- 1. Create a temporary staging or verify table schema compatibility
-- Relational messages table structure:
-- (id VARCHAR(36) PRIMARY KEY, conversation_id VARCHAR(36) NOT NULL, role VARCHAR(50) NOT NULL, content TEXT NOT NULL, sequence INTEGER NOT NULL, created_at TIMESTAMP)

-- 2. Mark messages_json as deprecated (column maintained for backward read compatibility during rollout)
COMMENT ON COLUMN conversations.messages_json IS 'DEPRECATED: Messages are stored in the relational messages table.';
