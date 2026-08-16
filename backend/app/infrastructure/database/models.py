import datetime
import uuid
from typing import Optional

from sqlalchemy import (
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass

def generate_uuid() -> str:
    return str(uuid.uuid4())

class Organization(Base):
    __tablename__ = "organizations"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    created_at: Mapped[datetime.datetime] = mapped_column(DateTime, default=datetime.datetime.utcnow)
    updated_at: Mapped[datetime.datetime] = mapped_column(
        DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow
    )

    # Relationships
    memberships: Mapped[list["Membership"]] = relationship("Membership", back_populates="organization", cascade="all, delete-orphan")
    projects: Mapped[list["Project"]] = relationship("Project", back_populates="organization", cascade="all, delete-orphan")
    workspaces: Mapped[list["Workspace"]] = relationship("Workspace", back_populates="organization", cascade="all, delete-orphan")
    conversations: Mapped[list["Conversation"]] = relationship("Conversation", back_populates="organization", cascade="all, delete-orphan")
    agent_runs: Mapped[list["AgentRun"]] = relationship("AgentRun", back_populates="organization", cascade="all, delete-orphan")
    approvals: Mapped[list["Approval"]] = relationship("Approval", back_populates="organization", cascade="all, delete-orphan")
    audit_events: Mapped[list["AuditEvent"]] = relationship("AuditEvent", back_populates="organization", cascade="all, delete-orphan")
    usage_records: Mapped[list["UsageRecord"]] = relationship("UsageRecord", back_populates="organization", cascade="all, delete-orphan")
    artifacts: Mapped[list["Artifact"]] = relationship("Artifact", back_populates="organization", cascade="all, delete-orphan")


class User(Base):
    __tablename__ = "users"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid)
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    full_name: Mapped[str] = mapped_column(String(255), nullable=False)
    hashed_password: Mapped[str] = mapped_column(String(255), nullable=False)
    created_at: Mapped[datetime.datetime] = mapped_column(DateTime, default=datetime.datetime.utcnow)
    updated_at: Mapped[datetime.datetime] = mapped_column(
        DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow
    )

    # Relationships
    memberships: Mapped[list["Membership"]] = relationship("Membership", back_populates="user", cascade="all, delete-orphan")
    conversations: Mapped[list["Conversation"]] = relationship("Conversation", back_populates="user", cascade="all, delete-orphan")
    agent_runs: Mapped[list["AgentRun"]] = relationship("AgentRun", back_populates="user", cascade="all, delete-orphan")
    approvals: Mapped[list["Approval"]] = relationship("Approval", back_populates="user", cascade="all, delete-orphan")
    audit_events: Mapped[list["AuditEvent"]] = relationship("AuditEvent", back_populates="user", cascade="all, delete-orphan")
    usage_records: Mapped[list["UsageRecord"]] = relationship("UsageRecord", back_populates="user", cascade="all, delete-orphan")


class Membership(Base):
    __tablename__ = "memberships"
    __table_args__ = (
        UniqueConstraint("organization_id", "user_id", name="uq_organization_user"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid)
    organization_id: Mapped[str] = mapped_column(String(36), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False)
    user_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    role: Mapped[str] = mapped_column(String(50), default="DEVELOPER")  # OWNER, ADMIN, DEVELOPER, VIEWER
    status: Mapped[str] = mapped_column(String(50), default="ACTIVE")
    created_at: Mapped[datetime.datetime] = mapped_column(DateTime, default=datetime.datetime.utcnow)
    updated_at: Mapped[datetime.datetime] = mapped_column(
        DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow
    )

    # Relationships
    organization: Mapped["Organization"] = relationship("Organization", back_populates="memberships")
    user: Mapped["User"] = relationship("User", back_populates="memberships")


class Project(Base):
    __tablename__ = "projects"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid)
    organization_id: Mapped[str] = mapped_column(String(36), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    repository_url: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    default_branch: Mapped[str | None] = mapped_column(String(255), nullable=True, default="main")
    created_at: Mapped[datetime.datetime] = mapped_column(DateTime, default=datetime.datetime.utcnow)
    updated_at: Mapped[datetime.datetime] = mapped_column(
        DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow
    )

    # Relationships
    organization: Mapped["Organization"] = relationship("Organization", back_populates="projects")
    workspaces: Mapped[list["Workspace"]] = relationship("Workspace", back_populates="project", cascade="all, delete-orphan")
    agent_runs: Mapped[list["AgentRun"]] = relationship("AgentRun", back_populates="project", cascade="all, delete-orphan")


class Workspace(Base):
    __tablename__ = "workspaces"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid)
    project_id: Mapped[str] = mapped_column(String(36), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True)
    organization_id: Mapped[str] = mapped_column(String(36), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    root_identifier: Mapped[str] = mapped_column(String(1024), nullable=False)
    branch: Mapped[str | None] = mapped_column(String(255), nullable=True)
    status: Mapped[str] = mapped_column(String(50), default="ACTIVE")
    created_at: Mapped[datetime.datetime] = mapped_column(DateTime, default=datetime.datetime.utcnow)
    updated_at: Mapped[datetime.datetime] = mapped_column(
        DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow
    )

    # Relationships
    project: Mapped["Project"] = relationship("Project", back_populates="workspaces")
    organization: Mapped["Organization"] = relationship("Organization", back_populates="workspaces")
    conversations: Mapped[list["Conversation"]] = relationship("Conversation", back_populates="workspace", cascade="all, delete-orphan")
    agent_runs: Mapped[list["AgentRun"]] = relationship("AgentRun", back_populates="workspace", cascade="all, delete-orphan")
    approvals: Mapped[list["Approval"]] = relationship("Approval", back_populates="workspace", cascade="all, delete-orphan")
    audit_events: Mapped[list["AuditEvent"]] = relationship("AuditEvent", back_populates="workspace", cascade="all, delete-orphan")
    usage_records: Mapped[list["UsageRecord"]] = relationship("UsageRecord", back_populates="workspace", cascade="all, delete-orphan")
    artifacts: Mapped[list["Artifact"]] = relationship("Artifact", back_populates="workspace", cascade="all, delete-orphan")


class Conversation(Base):
    __tablename__ = "conversations"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid)
    organization_id: Mapped[str] = mapped_column(String(36), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    workspace_id: Mapped[str] = mapped_column(String(36), ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False, index=True)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    workspace_root: Mapped[str | None] = mapped_column(String(1024), nullable=True, default="")
    mode: Mapped[str | None] = mapped_column(String(32), nullable=True, default="Ask")
    provider: Mapped[str | None] = mapped_column(String(64), nullable=True, default="")
    model: Mapped[str | None] = mapped_column(String(128), nullable=True, default="")
    token_input: Mapped[int | None] = mapped_column(Integer, nullable=True, default=0)
    token_output: Mapped[int | None] = mapped_column(Integer, nullable=True, default=0)
    token_total: Mapped[int | None] = mapped_column(Integer, nullable=True, default=0)
    messages_json: Mapped[str | None] = mapped_column(Text, nullable=True, default="[]")
    created_at: Mapped[datetime.datetime] = mapped_column(DateTime, default=datetime.datetime.utcnow)
    updated_at: Mapped[datetime.datetime] = mapped_column(
        DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow
    )

    # Relationships
    organization: Mapped["Organization"] = relationship("Organization", back_populates="conversations")
    user: Mapped["User"] = relationship("User", back_populates="conversations")
    workspace: Mapped["Workspace"] = relationship("Workspace", back_populates="conversations")
    messages: Mapped[list["Message"]] = relationship("Message", back_populates="conversation", cascade="all, delete-orphan")
    agent_runs: Mapped[list["AgentRun"]] = relationship("AgentRun", back_populates="conversation")


class Message(Base):
    __tablename__ = "messages"
    __table_args__ = (
        UniqueConstraint("conversation_id", "sequence", name="uq_conversation_sequence"),
        Index("idx_messages_conv_seq", "conversation_id", "sequence"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid)
    conversation_id: Mapped[str] = mapped_column(String(36), ForeignKey("conversations.id", ondelete="CASCADE"), nullable=False, index=True)
    role: Mapped[str] = mapped_column(String(50), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    sequence: Mapped[int] = mapped_column(Integer, nullable=False)
    metadata_json: Mapped[str | None] = mapped_column(Text, nullable=True, default="{}")
    created_at: Mapped[datetime.datetime] = mapped_column(DateTime, default=datetime.datetime.utcnow)

    # Relationships
    conversation: Mapped["Conversation"] = relationship("Conversation", back_populates="messages")


class AgentRun(Base):
    __tablename__ = "agent_runs"
    __table_args__ = (
        Index("idx_agent_runs_org_state", "organization_id", "state"),
        Index("idx_agent_runs_ws_state", "workspace_id", "state"),
        Index("idx_agent_runs_user_created", "user_id", "created_at"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid)
    organization_id: Mapped[str] = mapped_column(String(36), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    project_id: Mapped[str] = mapped_column(String(36), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True)
    workspace_id: Mapped[str] = mapped_column(String(36), ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False, index=True)
    conversation_id: Mapped[str] = mapped_column(String(36), ForeignKey("conversations.id", ondelete="CASCADE"), nullable=False, index=True)
    task_description: Mapped[str] = mapped_column(Text, nullable=False)
    mode: Mapped[str] = mapped_column(String(50), nullable=False)
    workspace_root: Mapped[str | None] = mapped_column(String(1024), nullable=True)  # denormalized for worker
    profile_name: Mapped[str | None] = mapped_column(String(255), nullable=True)   # model profile at run time
    state: Mapped[str] = mapped_column(String(50), default="RUNNING")
    status: Mapped[str] = mapped_column(String(255), nullable=True)
    worker_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    heartbeat_at: Mapped[datetime.datetime | None] = mapped_column(DateTime, nullable=True, index=True)
    error_code: Mapped[str | None] = mapped_column(String(100), nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime.datetime] = mapped_column(DateTime, default=datetime.datetime.utcnow, index=True)
    started_at: Mapped[datetime.datetime | None] = mapped_column(DateTime, nullable=True)
    completed_at: Mapped[datetime.datetime | None] = mapped_column(DateTime, nullable=True)

    # Relationships
    organization: Mapped["Organization"] = relationship("Organization", back_populates="agent_runs")
    user: Mapped["User"] = relationship("User", back_populates="agent_runs")
    project: Mapped["Project"] = relationship("Project", back_populates="agent_runs")
    workspace: Mapped["Workspace"] = relationship("Workspace", back_populates="agent_runs")
    conversation: Mapped["Conversation"] = relationship("Conversation", back_populates="agent_runs")
    tasks: Mapped[list["AgentTask"]] = relationship("AgentTask", back_populates="run", cascade="all, delete-orphan")
    steps: Mapped[list["AgentStep"]] = relationship("AgentStep", back_populates="run", cascade="all, delete-orphan")
    checkpoints: Mapped[list["AgentCheckpoint"]] = relationship("AgentCheckpoint", back_populates="run", cascade="all, delete-orphan")
    tool_calls: Mapped[list["ToolCall"]] = relationship("ToolCall", back_populates="run", cascade="all, delete-orphan")
    approvals: Mapped[list["Approval"]] = relationship("Approval", back_populates="run", cascade="all, delete-orphan")
    audit_events: Mapped[list["AuditEvent"]] = relationship("AuditEvent", back_populates="run", cascade="all, delete-orphan")
    usage_records: Mapped[list["UsageRecord"]] = relationship("UsageRecord", back_populates="run", cascade="all, delete-orphan")
    artifacts: Mapped[list["Artifact"]] = relationship("Artifact", back_populates="run", cascade="all, delete-orphan")
    events: Mapped[list["AgentEvent"]] = relationship("AgentEvent", back_populates="run", cascade="all, delete-orphan")


class AgentTask(Base):
    __tablename__ = "agent_tasks"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid)
    run_id: Mapped[str] = mapped_column(String(36), ForeignKey("agent_runs.id", ondelete="CASCADE"), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    status: Mapped[str] = mapped_column(String(50), default="PENDING")
    created_at: Mapped[datetime.datetime] = mapped_column(DateTime, default=datetime.datetime.utcnow)

    # Relationships
    run: Mapped["AgentRun"] = relationship("AgentRun", back_populates="tasks")


class AgentStep(Base):
    __tablename__ = "agent_steps"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid)
    run_id: Mapped[str] = mapped_column(String(36), ForeignKey("agent_runs.id", ondelete="CASCADE"), nullable=False, index=True)
    step_number: Mapped[int] = mapped_column(Integer, nullable=False)
    action_type: Mapped[str] = mapped_column(String(100), nullable=False)
    status: Mapped[str] = mapped_column(String(50), default="COMPLETED")
    created_at: Mapped[datetime.datetime] = mapped_column(DateTime, default=datetime.datetime.utcnow)

    # Relationships
    run: Mapped["AgentRun"] = relationship("AgentRun", back_populates="steps")


class AgentCheckpoint(Base):
    __tablename__ = "agent_checkpoints"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid)
    run_id: Mapped[str] = mapped_column(String(36), ForeignKey("agent_runs.id", ondelete="CASCADE"), nullable=False, index=True)
    checkpoint_name: Mapped[str] = mapped_column(String(255), nullable=False)
    state_json: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime.datetime] = mapped_column(DateTime, default=datetime.datetime.utcnow)

    # Relationships
    run: Mapped["AgentRun"] = relationship("AgentRun", back_populates="checkpoints")


class ToolCall(Base):
    __tablename__ = "tool_calls"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid)
    run_id: Mapped[str] = mapped_column(String(36), ForeignKey("agent_runs.id", ondelete="CASCADE"), nullable=False, index=True)
    workspace_id: Mapped[str] = mapped_column(String(36), ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False, index=True)
    tool_name: Mapped[str] = mapped_column(String(255), nullable=False)
    tool_version: Mapped[str | None] = mapped_column(String(50), nullable=True)
    status: Mapped[str] = mapped_column(String(50), default="REQUESTED")
    arguments_metadata: Mapped[str | None] = mapped_column(Text, nullable=True)
    exit_code: Mapped[int | None] = mapped_column(Integer, nullable=True)
    error_code: Mapped[str | None] = mapped_column(String(100), nullable=True)
    started_at: Mapped[datetime.datetime] = mapped_column(DateTime, default=datetime.datetime.utcnow)
    completed_at: Mapped[datetime.datetime | None] = mapped_column(DateTime, nullable=True)
    duration_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)

    # Relationships
    run: Mapped["AgentRun"] = relationship("AgentRun", back_populates="tool_calls")
    approvals: Mapped[list["Approval"]] = relationship("Approval", back_populates="tool_call", cascade="all, delete-orphan")
    audit_events: Mapped[list["AuditEvent"]] = relationship("AuditEvent", back_populates="tool_call", cascade="all, delete-orphan")


class Approval(Base):
    __tablename__ = "approvals"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid)
    run_id: Mapped[str] = mapped_column(String(36), ForeignKey("agent_runs.id", ondelete="CASCADE"), nullable=False, index=True)
    organization_id: Mapped[str] = mapped_column(String(36), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    workspace_id: Mapped[str] = mapped_column(String(36), ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False, index=True)
    tool_call_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("tool_calls.id", ondelete="SET NULL"), nullable=True)
    capability: Mapped[str] = mapped_column(String(255), nullable=False)
    status: Mapped[str] = mapped_column(String(50), default="PENDING")
    reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    requested_at: Mapped[datetime.datetime] = mapped_column(DateTime, default=datetime.datetime.utcnow)
    resolved_at: Mapped[datetime.datetime | None] = mapped_column(DateTime, nullable=True)
    resolved_by: Mapped[str | None] = mapped_column(String(255), nullable=True)

    # Relationships
    organization: Mapped["Organization"] = relationship("Organization", back_populates="approvals")
    user: Mapped["User"] = relationship("User", back_populates="approvals")
    workspace: Mapped["Workspace"] = relationship("Workspace", back_populates="approvals")
    run: Mapped["AgentRun"] = relationship("AgentRun", back_populates="approvals")
    tool_call: Mapped[Optional["ToolCall"]] = relationship("ToolCall", back_populates="approvals")


class AuditEvent(Base):
    __tablename__ = "audit_events"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid)
    organization_id: Mapped[str] = mapped_column(String(36), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    workspace_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("workspaces.id", ondelete="SET NULL"), nullable=True, index=True)
    run_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("agent_runs.id", ondelete="SET NULL"), nullable=True, index=True)
    tool_call_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("tool_calls.id", ondelete="SET NULL"), nullable=True, index=True)
    action: Mapped[str] = mapped_column(String(100), nullable=False)
    resource: Mapped[str] = mapped_column(String(255), nullable=False)
    risk: Mapped[str] = mapped_column(String(50), nullable=False)
    decision: Mapped[str] = mapped_column(String(50), nullable=False)
    correlation_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    timestamp: Mapped[datetime.datetime] = mapped_column(DateTime, default=datetime.datetime.utcnow)
    metadata_json: Mapped[str | None] = mapped_column(Text, nullable=True, default="{}")

    # Relationships
    organization: Mapped["Organization"] = relationship("Organization", back_populates="audit_events")
    user: Mapped[Optional["User"]] = relationship("User", back_populates="audit_events")
    workspace: Mapped[Optional["Workspace"]] = relationship("Workspace", back_populates="audit_events")
    run: Mapped[Optional["AgentRun"]] = relationship("AgentRun", back_populates="audit_events")
    tool_call: Mapped[Optional["ToolCall"]] = relationship("ToolCall", back_populates="audit_events")


class UsageRecord(Base):
    __tablename__ = "usage_records"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid)
    organization_id: Mapped[str] = mapped_column(String(36), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    workspace_id: Mapped[str] = mapped_column(String(36), ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False, index=True)
    run_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("agent_runs.id", ondelete="SET NULL"), nullable=True, index=True)
    provider: Mapped[str] = mapped_column(String(100), nullable=False)
    model: Mapped[str] = mapped_column(String(255), nullable=False)
    input_tokens: Mapped[int] = mapped_column(Integer, default=0)
    output_tokens: Mapped[int] = mapped_column(Integer, default=0)
    cached_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True, default=0)
    estimated_cost: Mapped[float] = mapped_column(Float, default=0.0)
    duration_ms: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime.datetime] = mapped_column(DateTime, default=datetime.datetime.utcnow, index=True)

    # Relationships
    organization: Mapped["Organization"] = relationship("Organization", back_populates="usage_records")
    user: Mapped["User"] = relationship("User", back_populates="usage_records")
    workspace: Mapped["Workspace"] = relationship("Workspace", back_populates="usage_records")
    run: Mapped[Optional["AgentRun"]] = relationship("AgentRun", back_populates="usage_records")


class Artifact(Base):
    __tablename__ = "artifacts"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid)
    organization_id: Mapped[str] = mapped_column(String(36), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True)
    workspace_id: Mapped[str] = mapped_column(String(36), ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False, index=True)
    run_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("agent_runs.id", ondelete="SET NULL"), nullable=True, index=True)
    type: Mapped[str] = mapped_column(String(100), nullable=False)
    storage_key: Mapped[str] = mapped_column(String(1024), nullable=False)
    content_type: Mapped[str] = mapped_column(String(100), nullable=False)
    size_bytes: Mapped[int] = mapped_column(Integer, default=0)
    checksum: Mapped[str | None] = mapped_column(String(255), nullable=True)
    created_at: Mapped[datetime.datetime] = mapped_column(DateTime, default=datetime.datetime.utcnow)
    expires_at: Mapped[datetime.datetime | None] = mapped_column(DateTime, nullable=True)

    # Relationships
    organization: Mapped["Organization"] = relationship("Organization", back_populates="artifacts")
    workspace: Mapped["Workspace"] = relationship("Workspace", back_populates="artifacts")
    run: Mapped[Optional["AgentRun"]] = relationship("AgentRun", back_populates="artifacts")


class AgentEvent(Base):
    __tablename__ = "agent_events"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid)
    run_id: Mapped[str] = mapped_column(String(36), ForeignKey("agent_runs.id", ondelete="CASCADE"), nullable=False, index=True)
    sequence: Mapped[int] = mapped_column(Integer, nullable=False)
    event_type: Mapped[str] = mapped_column(String(100), nullable=False)
    payload_json: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime.datetime] = mapped_column(DateTime, default=datetime.datetime.utcnow)

    # Relationships
    run: Mapped["AgentRun"] = relationship("AgentRun", back_populates="events")
