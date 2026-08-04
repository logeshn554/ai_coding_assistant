"""HTTP route for automated dev-server visual and runtime QA inspection."""

from __future__ import annotations

import base64
import json
import logging
import os
from typing import Any, Dict, Optional
from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field

from ..state import workspace_state
from ..tools.browser_capture import CaptureResult, capture_page, is_localhost_url

logger = logging.getLogger("devpilot.routes.inspect")
router = APIRouter()


class InspectRequest(BaseModel):
    """Request model for /api/inspect endpoint."""

    url: str = Field(..., description="Dev server localhost URL (e.g. http://localhost:5173)")
    workspace_root: Optional[str] = ""
    mode: Optional[str] = "Agent"
    auto_trigger: Optional[bool] = False


@router.post("/api/inspect")
async def run_inspect(req: InspectRequest, request: Request = None):
    """Perform visual screenshot + console/network log capture for a dev server URL.

    1. Validates that the URL targets localhost / 127.0.0.1.
    2. Runs headless Chromium browser capture.
    3. Builds a structured QA prompt with base64 screenshot + logs.
    4. Enqueues a synthetic turn to the active session for automated bug fixing.

    Returns:
        JSON object with capture summary and status.
    """
    # 1. Validate localhost URL guardrail
    try:
        is_localhost_url(req.url)
    except ValueError as val_err:
        logger.warning("Rejecting non-localhost inspect URL: %s", val_err)
        raise HTTPException(status_code=400, detail=str(val_err))

    effective_workspace = req.workspace_root or workspace_state.root or os.getcwd()

    # 2. Run browser capture
    try:
        capture: CaptureResult = await capture_page(
            url=req.url,
            workspace_root=effective_workspace,
        )
    except RuntimeError as r_err:
        logger.error("Browser capture failed: %s", r_err)
        raise HTTPException(status_code=500, detail=f"Browser QA capture failed: {r_err}")
    except Exception as exc:
        logger.error("Unexpected error during browser capture: %s", exc)
        raise HTTPException(status_code=500, detail=f"QA capture error: {exc}")

    # 3. Encode screenshot as base64 Data URI if captured
    screenshot_b64 = ""
    if capture.screenshot_path and os.path.isfile(capture.screenshot_path):
        try:
            with open(capture.screenshot_path, "rb") as sf:
                b64_str = base64.b64encode(sf.read()).decode("utf-8")
                screenshot_b64 = f"data:image/png;base64,{b64_str}"
        except Exception as img_err:
            logger.warning("Failed to encode screenshot to base64: %s", img_err)

    # 4. Format prompt
    console_summary = json.dumps(capture.console_messages, indent=2) if capture.console_messages else "No console messages recorded."
    failed_net_summary = json.dumps(capture.failed_requests, indent=2) if capture.failed_requests else "No failed network requests recorded."

    prompt_parts = [
        "🔍 **[Auto-Detected QA Inspection Report]**",
        f"**Target URL**: {capture.final_url}",
        f"**Page Title**: {capture.page_title or 'Dev Server App'}",
        f"**Screenshot**: {capture.screenshot_path or 'Captured'}",
        "",
        "### 📜 Console Messages (Errors & Warnings):",
        "```json",
        console_summary,
        "```",
        "",
        "### 🌐 Failed Network Requests:",
        "```json",
        failed_net_summary,
        "```",
        "",
        "**INSTRUCTION FOR AGENT**:",
        "Analyze this visual screenshot and the console/network logs for layout bugs, console exceptions, or failing endpoints.",
        "Identify root causes tied to specific source files in this workspace where possible, and propose/apply necessary fixes directly.",
    ]

    if screenshot_b64:
        prompt_parts.append(f"\n[ATTACHMENT_IMAGE: {screenshot_b64[:120]}...]")

    synthetic_prompt = "\n".join(prompt_parts)

    # 5. Enqueue to session if available
    enqueued = False
    try:
        from ..session.agent_session import AgentSession
        from ..permissions import PermissionManager
        from ..state import config_manager

        active_profile = config_manager.get_active_profile()
        perm_mgr = PermissionManager(config_manager, effective_workspace)

        session = AgentSession(
            workspace_root=effective_workspace,
            profile=active_profile,
            send_ws_message_func=None,
            permission_manager=perm_mgr,
        )
        await session.enqueue_message(
            text=synthetic_prompt,
            mode=req.mode or "Agent",
            auto_apply=True,
        )
        enqueued = True
    except Exception as seq_err:
        logger.warning("Could not enqueue synthetic turn to AgentSession: %s", seq_err)

    return {
        "success": True,
        "final_url": capture.final_url,
        "page_title": capture.page_title,
        "screenshot_path": capture.screenshot_path,
        "console_errors_count": len([m for m in capture.console_messages if str(m.get("type", "")).lower() in ("error", "err")]),
        "failed_requests_count": len(capture.failed_requests),
        "enqueued": enqueued,
    }
