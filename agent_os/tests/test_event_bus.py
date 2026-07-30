import pytest
import asyncio
from agent_os.core.event_bus import EventBus

@pytest.mark.asyncio
async def test_event_bus_pub_sub_sync():
    bus = EventBus()
    received = []

    def handler(data):
        received.append(data)

    bus.subscribe("test_event", handler)
    await bus.publish("test_event", "hello")
    assert received == ["hello"]

    bus.unsubscribe("test_event", handler)
    await bus.publish("test_event", "world")
    assert received == ["hello"]

@pytest.mark.asyncio
async def test_event_bus_pub_sub_async():
    bus = EventBus()
    received = []

    async def async_handler(data):
        await asyncio.sleep(0.01)
        received.append(data)

    bus.subscribe("test_async", async_handler)
    await bus.publish("test_async", "hello_async")
    assert received == ["hello_async"]
