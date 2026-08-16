import json

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select

from backend.app.infrastructure.database.connection import async_session_factory
from backend.app.infrastructure.database.models import AgentEvent, AgentRun
from backend.app.state import verify_token

router = APIRouter(prefix="/api/runs", tags=["runs"])

@router.get("/{run_id}/events")
async def get_events(
    run_id: str,
    after_sequence: int = Query(0, description="Monotonic sequence number to query after"),
    limit: int = Query(100, description="Maximum number of events to return"),
    token_user_id: str = Depends(verify_token)
):
    """Retrieve ordered, paginated events for a specific run ID."""
    async with async_session_factory() as db:
        # Check run exists
        stmt = select(AgentRun).where(AgentRun.id == run_id)
        run_res = await db.execute(stmt)
        run = run_res.scalar()
        if not run:
            raise HTTPException(status_code=404, detail="Agent run not found.")
            
        # Verify tenant boundary
        if run.organization_id != "default-org":
            raise HTTPException(status_code=403, detail="Access denied to requested run events.")
            
        # Fetch events after sequence, ordered monotonically
        stmt = (
            select(AgentEvent)
            .where(AgentEvent.run_id == run_id)
            .where(AgentEvent.sequence > after_sequence)
            .order_by(AgentEvent.sequence.asc())
            .limit(limit)
        )
        evt_res = await db.execute(stmt)
        events = evt_res.scalars().all()
        
        return [
            {
                "id": evt.id,
                "run_id": evt.run_id,
                "sequence": evt.sequence,
                "event_type": evt.event_type,
                "payload": json.loads(evt.payload_json),
                "created_at": evt.created_at.isoformat()
            }
            for evt in events
        ]
