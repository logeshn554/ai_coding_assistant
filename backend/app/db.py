import os
import uuid
import time
import datetime
import json
from pathlib import Path
from sqlalchemy import Column, String, Integer, DateTime, ForeignKey, Text, select
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy.orm import declarative_base, relationship

from .tools.scan_for_bugs import generate_bug_report_async

DB_DIR = Path.home() / ".devpilot"
DB_FILE = DB_DIR / "history.db"
DATABASE_URL = f"sqlite+aiosqlite:///{DB_FILE}"

DB_DIR.mkdir(parents=True, exist_ok=True)

Base = declarative_base()

class SessionModel(Base):
    __tablename__ = "sessions"
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    title = Column(String(255), nullable=False)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow)
    
    messages = relationship("MessageModel", back_populates="session", cascade="all, delete-orphan", lazy="selectin")

class MessageModel(Base):
    __tablename__ = "messages"
    id = Column(Integer, primary_key=True, autoincrement=True)
    session_id = Column(String(36), ForeignKey("sessions.id", ondelete="CASCADE"), nullable=False)
    role = Column(String(50), nullable=False)
    content = Column(Text, nullable=False)
    timestamp = Column(DateTime, default=datetime.datetime.utcnow)
    
    session = relationship("SessionModel", back_populates="messages")

engine = create_async_engine(DATABASE_URL, echo=False)
async_session = async_sessionmaker(bind=engine, class_=AsyncSession, expire_on_commit=False)

# Track active session in memory
_active_session_id = None

async def init_db():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    await migrate_legacy_history()
    
    # Run the bug scanning tool across the workspace and store a concise report
    try:
        report = await generate_bug_report_async()
        bug_report_path = DB_DIR / "bug_report.txt"
        bug_report_path.write_text(report, encoding="utf-8")
    except Exception as e:
        print(f"Bug scanning failed: {e}")

    # Initialize active session
    global _active_session_id
    async with async_session() as db:
        res = await db.execute(select(SessionModel).order_by(SessionModel.updated_at.desc()))
        last_session = res.scalars().first()
        if last_session:
            _active_session_id = last_session.id
        else:
            # Create default session
            default_session = SessionModel(id="default-session", title="Default Conversation")
            db.add(default_session)
            await db.commit()
            _active_session_id = "default-session"

async def get_active_session_id() -> str:
    global _active_session_id
    if not _active_session_id:
        _active_session_id = "default-session"
    return _active_session_id

def set_active_session_id(s_id: str):
    global _active_session_id
    _active_session_id = s_id

async def migrate_legacy_history():
    legacy_file = DB_DIR / "chat_sessions.json"
    if legacy_file.exists():
        try:
            with open(legacy_file, "r", encoding="utf-8") as f:
                data = json.load(f)
                
            sessions_dict = data.get("sessions", {})
            async with async_session() as db:
                for s_id, s in sessions_dict.items():
                    stmt = select(SessionModel).where(SessionModel.id == s_id)
                    res = await db.execute(stmt)
                    existing = res.scalar()
                    if not existing:
                        title = s.get("title", "Conversation")
                        try:
                            c_at = datetime.datetime.utcfromtimestamp(s.get("created_at", time.time()))
                        except Exception:
                            c_at = datetime.datetime.utcnow()
                        try:
                            u_at = datetime.datetime.utcfromtimestamp(s.get("updated_at", time.time()))
                        except Exception:
                            u_at = datetime.datetime.utcnow()
                        
                        db_sess = SessionModel(id=s_id, title=title, created_at=c_at, updated_at=u_at)
                        db.add(db_sess)
                        
                        # Add messages
                        for m in s.get("messages", []):
                            m_role = m.get("role", "user")
                            m_content = m.get("content", "")
                            if isinstance(m_content, dict) or isinstance(m_content, list):
                                m_content = json.dumps(m_content)
                            try:
                                m_time = datetime.datetime.utcfromtimestamp(m.get("timestamp", time.time()))
                            except Exception:
                                m_time = datetime.datetime.utcnow()
                            db_msg = MessageModel(
                                session_id=s_id,
                                role=m_role,
                                content=m_content,
                                timestamp=m_time
                            )
                            db.add(db_msg)
                await db.commit()
            
            # Rename legacy file
            legacy_file.rename(legacy_file.with_name("chat_sessions.json.bak"))
        except Exception as e:
            print(f"Failed to migrate legacy history: {e}")