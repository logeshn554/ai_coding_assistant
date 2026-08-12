import json
import logging
import functools
from typing import Any, Optional

from backend.app.shared_memory import sm_set, sm_get, sm_get_all
from agent_runtime.tools import ToolDefinition, ToolResult, RiskLevel

logger = logging.getLogger("agent_runtime.tools.shared_memory")


async def _shared_memory_set(key: str, value: str, run_id: str) -> ToolResult:
    """Set a key-value pair in the shared memory."""
    try:
        try:
            parsed_val = json.loads(value)
        except (json.JSONDecodeError, TypeError):
            parsed_val = value

        await sm_set(run_id, key, parsed_val)
        return ToolResult(
            success=True,
            output=f"Successfully set shared memory key '{key}'."
        )
    except Exception as e:
        logger.error("Failed to set shared memory key '%s': %s", key, e)
        return ToolResult(
            success=False,
            output="",
            error=str(e)
        )


async def _shared_memory_get(key: str, run_id: str) -> ToolResult:
    """Get a value by key from the shared memory."""
    try:
        val = await sm_get(run_id, key)
        if val is None:
            return ToolResult(
                success=True,
                output=f"Key '{key}' not found in shared memory."
            )
        val_str = json.dumps(val, indent=2) if not isinstance(val, str) else val
        return ToolResult(
            success=True,
            output=val_str
        )
    except Exception as e:
        logger.error("Failed to get shared memory key '%s': %s", key, e)
        return ToolResult(
            success=False,
            output="",
            error=str(e)
        )


async def _shared_memory_get_all(run_id: str) -> ToolResult:
    """Retrieve all stored key-value pairs from the shared memory."""
    try:
        all_mem = await sm_get_all(run_id)
        if not all_mem:
            return ToolResult(
                success=True,
                output="Shared memory is empty."
            )
        return ToolResult(
            success=True,
            output=json.dumps(all_mem, indent=2)
        )
    except Exception as e:
        logger.error("Failed to get all shared memory keys: %s", e)
        return ToolResult(
            success=False,
            output="",
            error=str(e)
        )


def create_shared_memory_tools(run_id: str) -> list[ToolDefinition]:
    """Create shared memory tools bound to the current execution run_id.

    Args:
        run_id: The run or session identifier.

    Returns:
        List of ToolDefinition objects ready for registration.
    """
    run_id_val = run_id or "default"
    set_fn = functools.partial(_shared_memory_set, run_id=run_id_val)
    get_fn = functools.partial(_shared_memory_get, run_id=run_id_val)
    get_all_fn = functools.partial(_shared_memory_get_all, run_id=run_id_val)

    return [
        ToolDefinition(
            name="shared_memory_set",
            description=(
                "Store a key-value pair in the shared memory accessible by all specialist agents. "
                "Use this to pass context, results, requirements, specs, or logs to subsequent agents."
            ),
            parameters={
                "type": "object",
                "properties": {
                    "key": {
                        "type": "string",
                        "description": "The key under which the information will be stored.",
                    },
                    "value": {
                        "type": "string",
                        "description": "The string or JSON-serialized value to store.",
                    },
                },
                "required": ["key", "value"],
            },
            executor=set_fn,
            risk_level=RiskLevel.LOW,
        ),
        ToolDefinition(
            name="shared_memory_get",
            description=(
                "Retrieve the value of a key from the shared memory. "
                "Use this to read information, plans, specifications, or data left by other agents."
            ),
            parameters={
                "type": "object",
                "properties": {
                    "key": {
                        "type": "string",
                        "description": "The key to retrieve from shared memory.",
                    },
                },
                "required": ["key"],
            },
            executor=get_fn,
            risk_level=RiskLevel.LOW,
        ),
        ToolDefinition(
            name="shared_memory_get_all",
            description="Retrieve all stored keys and values currently held in the shared memory.",
            parameters={
                "type": "object",
                "properties": {},
            },
            executor=get_all_fn,
            risk_level=RiskLevel.LOW,
        ),
    ]
