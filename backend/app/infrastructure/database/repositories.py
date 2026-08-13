import datetime
from typing import List, Optional, Any
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update, delete
from backend.app.infrastructure.database.models import (
    Organization, User, Membership, Project, Workspace,
    Conversation, Message, AgentRun, AgentTask, AgentStep,
    AgentCheckpoint, ToolCall, Approval, AuditEvent, UsageRecord, Artifact
)

class BaseRepository:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

class OrganizationRepository(BaseRepository):
    async def create(self, name: str) -> Organization:
        org = Organization(name=name)
        self.db.add(org)
        await self.db.flush()
        return org

    async def get_by_id(self, org_id: str) -> Optional[Organization]:
        res = await self.db.execute(select(Organization).where(Organization.id == org_id))
        return res.scalars().first()

class UserRepository(BaseRepository):
    async def create(self, email: str, full_name: str, hashed_password: str) -> User:
        user = User(email=email, full_name=full_name, hashed_password=hashed_password)
        self.db.add(user)
        await self.db.flush()
        return user

    async def get_by_email(self, email: str) -> Optional[User]:
        res = await self.db.execute(select(User).where(User.email == email))
        return res.scalars().first()

    async def get_by_id(self, user_id: str) -> Optional[User]:
        res = await self.db.execute(select(User).where(User.id == user_id))
        return res.scalars().first()

class MembershipRepository(BaseRepository):
    async def add_member(self, org_id: str, user_id: str, role: str = "DEVELOPER") -> Membership:
        membership = Membership(organization_id=org_id, user_id=user_id, role=role)
        self.db.add(membership)
        await self.db.flush()
        return membership

    async def get_membership(self, org_id: str, user_id: str) -> Optional[Membership]:
        res = await self.db.execute(
            select(Membership).where(
                Membership.organization_id == org_id,
                Membership.user_id == user_id
            )
        )
        return res.scalars().first()

class ProjectRepository(BaseRepository):
    async def create(self, org_id: str, name: str, description: Optional[str] = None) -> Project:
        proj = Project(organization_id=org_id, name=name, description=description)
        self.db.add(proj)
        await self.db.flush()
        return proj

    async def get_project(self, org_id: str, project_id: str) -> Optional[Project]:
        res = await self.db.execute(
            select(Project).where(
                Project.organization_id == org_id,
                Project.id == project_id
            )
        )
        return res.scalars().first()

    async def list_by_org(self, org_id: str) -> List[Project]:
        res = await self.db.execute(select(Project).where(Project.organization_id == org_id))
        return list(res.scalars().all())

class WorkspaceRepository(BaseRepository):
    async def create(self, org_id: str, project_id: str, name: str, root_identifier: str) -> Workspace:
        ws = Workspace(organization_id=org_id, project_id=project_id, name=name, root_identifier=root_identifier)
        self.db.add(ws)
        await self.db.flush()
        return ws

    async def get_workspace(self, org_id: str, workspace_id: str) -> Optional[Workspace]:
        res = await self.db.execute(
            select(Workspace).where(
                Workspace.organization_id == org_id,
                Workspace.id == workspace_id
            )
        )
        return res.scalars().first()

    async def get_by_root(self, org_id: str, root_identifier: str) -> Optional[Workspace]:
        res = await self.db.execute(
            select(Workspace).where(
                Workspace.organization_id == org_id,
                Workspace.root_identifier == root_identifier
            )
        )
        return res.scalars().first()

    async def list_by_project(self, org_id: str, project_id: str) -> List[Workspace]:
        res = await self.db.execute(
            select(Workspace).where(
                Workspace.organization_id == org_id,
                Workspace.project_id == project_id
            )
        )
        return list(res.scalars().all())

class ConversationRepository(BaseRepository):
    async def create(self, org_id: str, user_id: str, workspace_id: str, title: str, id: Optional[str] = None) -> Conversation:
        conv = Conversation(organization_id=org_id, user_id=user_id, workspace_id=workspace_id, title=title)
        if id:
            conv.id = id
        self.db.add(conv)
        await self.db.flush()
        return conv

    async def get_conversation(self, org_id: str, conversation_id: str) -> Optional[Conversation]:
        res = await self.db.execute(
            select(Conversation).where(
                Conversation.organization_id == org_id,
                Conversation.id == conversation_id
            )
        )
        return res.scalars().first()

    async def get_last_for_workspace(self, org_id: str, workspace_id: str) -> Optional[Conversation]:
        res = await self.db.execute(
            select(Conversation)
            .where(
                Conversation.organization_id == org_id,
                Conversation.workspace_id == workspace_id
            )
            .order_by(Conversation.updated_at.desc())
        )
        return res.scalars().first()

    async def list_by_workspace(self, org_id: str, workspace_id: str) -> List[Conversation]:
        res = await self.db.execute(
            select(Conversation)
            .where(
                Conversation.organization_id == org_id,
                Conversation.workspace_id == workspace_id
            )
            .order_by(Conversation.updated_at.desc())
        )
        return list(res.scalars().all())

    async def list_all(self, org_id: str) -> List[Conversation]:
        res = await self.db.execute(
            select(Conversation)
            .where(Conversation.organization_id == org_id)
            .order_by(Conversation.updated_at.desc())
        )
        return list(res.scalars().all())

    async def delete_by_workspace(self, org_id: str, workspace_id: str) -> None:
        await self.db.execute(
            delete(Conversation).where(
                Conversation.organization_id == org_id,
                Conversation.workspace_id == workspace_id
            )
        )

    async def delete_by_id(self, org_id: str, conversation_id: str) -> None:
        await self.db.execute(
            delete(Conversation).where(
                Conversation.organization_id == org_id,
                Conversation.id == conversation_id
            )
        )

class MessageRepository(BaseRepository):
    async def create(self, conversation_id: str, role: str, content: str, sequence: int, metadata_json: Optional[str] = "{}") -> Message:
        msg = Message(
            conversation_id=conversation_id,
            role=role,
            content=content,
            sequence=sequence,
            metadata_json=metadata_json
        )
        self.db.add(msg)
        await self.db.flush()
        return msg

    async def get_by_conversation(self, conversation_id: str) -> List[Message]:
        res = await self.db.execute(
            select(Message)
            .where(Message.conversation_id == conversation_id)
            .order_by(Message.sequence.asc())
        )
        return list(res.scalars().all())

class AgentRunRepository(BaseRepository):
    async def create(
        self,
        org_id: str,
        user_id: str,
        project_id: str,
        workspace_id: str,
        conversation_id: str,
        task_description: str,
        mode: str,
        id: Optional[str] = None
    ) -> AgentRun:
        run = AgentRun(
            organization_id=org_id,
            user_id=user_id,
            project_id=project_id,
            workspace_id=workspace_id,
            conversation_id=conversation_id,
            task_description=task_description,
            mode=mode,
            state="RUNNING"
        )
        if id:
            run.id = id
        self.db.add(run)
        await self.db.flush()
        return run

    async def get_run(self, org_id: str, run_id: str) -> Optional[AgentRun]:
        res = await self.db.execute(
            select(AgentRun).where(
                AgentRun.organization_id == org_id,
                AgentRun.id == run_id
            )
        )
        return res.scalars().first()

    async def update_status(self, org_id: str, run_id: str, status: str, state: Optional[str] = None) -> None:
        stmt = update(AgentRun).where(
            AgentRun.organization_id == org_id,
            AgentRun.id == run_id
        ).values(status=status)
        if state:
            stmt = stmt.values(state=state)
        await self.db.execute(stmt)

class ApprovalRepository(BaseRepository):
    async def create(
        self,
        org_id: str,
        user_id: str,
        workspace_id: str,
        run_id: str,
        tool_call_id: Optional[str],
        capability: str
    ) -> Approval:
        appr = Approval(
            organization_id=org_id,
            user_id=user_id,
            workspace_id=workspace_id,
            run_id=run_id,
            tool_call_id=tool_call_id,
            capability=capability,
            status="PENDING"
        )
        self.db.add(appr)
        await self.db.flush()
        return appr

    async def resolve(
        self,
        org_id: str,
        approval_id: str,
        status: str,
        resolved_by: str,
        reason: Optional[str] = None
    ) -> None:
        await self.db.execute(
            update(Approval)
            .where(
                Approval.organization_id == org_id,
                Approval.id == approval_id
            )
            .values(
                status=status,
                resolved_by=resolved_by,
                resolved_at=datetime.datetime.utcnow(),
                reason=reason
            )
        )

    async def get_approval(self, org_id: str, approval_id: str) -> Optional[Approval]:
        res = await self.db.execute(
            select(Approval).where(
                Approval.organization_id == org_id,
                Approval.id == approval_id
            )
        )
        return res.scalars().first()
