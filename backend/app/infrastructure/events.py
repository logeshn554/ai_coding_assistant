import asyncio
import json
import logging

from sqlalchemy import func, select

from backend.app.infrastructure.database.connection import async_session_factory
from backend.app.infrastructure.database.models import AgentEvent
from backend.app.state import redis_client

logger = logging.getLogger("devpilot.infrastructure.events")

class EventPublisher:
    _local_subscribers = []

    @classmethod
    def subscribe_local(cls, callback) -> None:
        cls._local_subscribers.append(callback)

    @classmethod
    def unsubscribe_local(cls, callback) -> None:
        if callback in cls._local_subscribers:
            cls._local_subscribers.remove(callback)

    @classmethod
    async def publish(cls, run_id: str, event_type: str, payload: dict) -> None:
        """Durable event persistence in PostgreSQL with sequence numbers and Redis Pub/Sub publish."""
        payload_str = json.dumps(payload)
        next_seq = 1
        
        try:
            async with async_session_factory() as db:
                stmt = select(func.max(AgentEvent.sequence)).where(AgentEvent.run_id == run_id)
                res = await db.execute(stmt)
                max_seq = res.scalar()
                next_seq = (max_seq or 0) + 1
                
                event = AgentEvent(
                    run_id=run_id,
                    sequence=next_seq,
                    event_type=event_type,
                    payload_json=payload_str
                )
                db.add(event)
                await db.commit()
        except Exception as db_err:
            logger.error(f"Failed to persist event to PostgreSQL: {db_err}")
            
        # Live transport fan-out via Redis Pub/Sub
        channel = f"channel:run-events:{run_id}"
        message = {
            "run_id": run_id,
            "sequence": next_seq,
            "type": event_type,
            **payload
        }
        
        # Trigger local subscribers (in-memory/development fallback)
        for cb in list(cls._local_subscribers):
            try:
                if asyncio.iscoroutinefunction(cb):
                    asyncio.create_task(cb(run_id, message))
                else:
                    cb(run_id, message)
            except Exception as e:
                logger.error(f"Local subscriber callback failed: {e}")

        if not redis_client.use_fallback:
            try:
                client = await redis_client._ensure_client()
                await client.publish(channel, json.dumps(message))
            except Exception as redis_err:
                logger.debug(f"Redis publish unavailable, switching to local in-memory fallback: {redis_err}")
                redis_client.use_fallback = True
