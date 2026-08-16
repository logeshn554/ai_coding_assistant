"""
Gateway Session Manager — Session lifecycle management.

Manages:
  - Session creation, activation, pausing, termination
  - Session persistence and recovery after restarts
  - Session-to-stream channel binding
  - Session metadata and state tracking
"""
from __future__ import annotations

import logging
import time
import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

logger = logging.getLogger("agentos.gateway.session_manager")


class SessionState(str, Enum):
    CREATED = "created"
    ACTIVE = "active"
    PAUSED = "paused"
    WAITING_INPUT = "waiting_input"
    TERMINATED = "terminated"
    EXPIRED = "expired"
    ERROR = "error"


@dataclass
class SessionRecord:
    """Persistent record of a session."""
    session_id: str
    tenant_id: str
    user_id: str
    state: SessionState = SessionState.CREATED
    workspace_root: str = ""
    model_name: str = ""
    stream_channel_id: str = ""
    created_at: float = field(default_factory=time.time)
    last_active_at: float = field(default_factory=time.time)
    terminated_at: float = 0.0
    total_messages: int = 0
    total_tokens: int = 0
    total_cost_usd: float = 0.0
    error_count: int = 0
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def duration_seconds(self) -> float:
        end = self.terminated_at if self.terminated_at > 0 else time.time()
        return end - self.created_at

    @property
    def is_alive(self) -> bool:
        return self.state in (SessionState.CREATED, SessionState.ACTIVE, SessionState.PAUSED, SessionState.WAITING_INPUT)

    def touch(self) -> None:
        self.last_active_at = time.time()


class GatewaySessionManager:
    """Manages session lifecycle across the gateway."""

    def __init__(self, session_ttl: float = 7200.0, max_sessions_per_user: int = 10):
        self._sessions: dict[str, SessionRecord] = {}
        self._session_ttl = session_ttl
        self._max_sessions_per_user = max_sessions_per_user

    def create_session(
        self,
        tenant_id: str,
        user_id: str,
        workspace_root: str = "",
        model_name: str = "",
        metadata: dict[str, Any] = None,
    ) -> SessionRecord:
        """Create a new session."""
        session_id = f"sess-{uuid.uuid4().hex[:16]}"

        # Enforce per-user session limit
        user_sessions = self.get_user_sessions(user_id, alive_only=True)
        if len(user_sessions) >= self._max_sessions_per_user:
            # Terminate oldest session
            oldest = min(user_sessions, key=lambda s: s.created_at)
            self.terminate_session(oldest.session_id, reason="max_sessions_exceeded")
            logger.info(f"Auto-terminated oldest session {oldest.session_id} for user {user_id}")

        session = SessionRecord(
            session_id=session_id,
            tenant_id=tenant_id,
            user_id=user_id,
            workspace_root=workspace_root,
            model_name=model_name,
            metadata=metadata or {},
        )

        self._sessions[session_id] = session
        logger.info(f"Session created: {session_id} (user={user_id}, workspace={workspace_root})")
        return session

    def activate_session(self, session_id: str) -> SessionRecord | None:
        """Transition a session to active state."""
        session = self._sessions.get(session_id)
        if session and session.state in (SessionState.CREATED, SessionState.PAUSED):
            session.state = SessionState.ACTIVE
            session.touch()
            return session
        return None

    def pause_session(self, session_id: str) -> SessionRecord | None:
        """Pause an active session."""
        session = self._sessions.get(session_id)
        if session and session.state == SessionState.ACTIVE:
            session.state = SessionState.PAUSED
            session.touch()
            return session
        return None

    def resume_session(self, session_id: str) -> SessionRecord | None:
        """Resume a paused session."""
        return self.activate_session(session_id)

    def terminate_session(self, session_id: str, reason: str = "") -> SessionRecord | None:
        """Terminate a session."""
        session = self._sessions.get(session_id)
        if session:
            session.state = SessionState.TERMINATED
            session.terminated_at = time.time()
            if reason:
                session.metadata["termination_reason"] = reason
            logger.info(f"Session terminated: {session_id} (reason={reason})")
            return session
        return None

    def get_session(self, session_id: str) -> SessionRecord | None:
        """Get a session by ID."""
        session = self._sessions.get(session_id)
        if session:
            # Check TTL expiry
            if session.is_alive and (time.time() - session.last_active_at) > self._session_ttl:
                session.state = SessionState.EXPIRED
                session.terminated_at = time.time()
                logger.info(f"Session expired: {session_id}")
        return session

    def get_user_sessions(self, user_id: str, alive_only: bool = False) -> list[SessionRecord]:
        """Get all sessions for a user."""
        sessions = [s for s in self._sessions.values() if s.user_id == user_id]
        if alive_only:
            sessions = [s for s in sessions if s.is_alive]
        return sessions

    def get_tenant_sessions(self, tenant_id: str, alive_only: bool = False) -> list[SessionRecord]:
        """Get all sessions for a tenant."""
        sessions = [s for s in self._sessions.values() if s.tenant_id == tenant_id]
        if alive_only:
            sessions = [s for s in sessions if s.is_alive]
        return sessions

    def record_activity(
        self,
        session_id: str,
        messages: int = 0,
        tokens: int = 0,
        cost_usd: float = 0.0,
    ) -> None:
        """Record session activity metrics."""
        session = self._sessions.get(session_id)
        if session:
            session.touch()
            session.total_messages += messages
            session.total_tokens += tokens
            session.total_cost_usd += cost_usd

    def record_error(self, session_id: str) -> None:
        """Record a session error."""
        session = self._sessions.get(session_id)
        if session:
            session.error_count += 1
            session.touch()

    def cleanup_expired(self) -> int:
        """Clean up expired and old terminated sessions."""
        now = time.time()
        to_remove = []
        for sid, session in self._sessions.items():
            if session.state in (SessionState.TERMINATED, SessionState.EXPIRED, SessionState.ERROR):
                if now - (session.terminated_at or session.last_active_at) > 3600:
                    to_remove.append(sid)
            elif session.is_alive and (now - session.last_active_at) > self._session_ttl:
                session.state = SessionState.EXPIRED
                session.terminated_at = now

        for sid in to_remove:
            del self._sessions[sid]

        return len(to_remove)

    def get_stats(self) -> dict[str, Any]:
        """Get overall session statistics."""
        alive = sum(1 for s in self._sessions.values() if s.is_alive)
        return {
            "total_sessions": len(self._sessions),
            "alive_sessions": alive,
            "terminated_sessions": sum(
                1 for s in self._sessions.values()
                if s.state == SessionState.TERMINATED
            ),
            "expired_sessions": sum(
                1 for s in self._sessions.values()
                if s.state == SessionState.EXPIRED
            ),
        }


# ── Singleton ───────────────────────────────────────────────────────────────

gateway_session_manager = GatewaySessionManager()
