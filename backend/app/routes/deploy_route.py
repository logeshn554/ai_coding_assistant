"""Deploy command suggestion route.

GET /api/deploy/command -- returns the recommended deploy CLI command for
the current workspace project type. This is purely advisory: Loopix
detects the project type from config files and tells the user which command
to run, rather than attempting to deploy itself.
"""
from __future__ import annotations

import logging

from fastapi import APIRouter, HTTPException

from ..deployment import generate_deploy_command
from ..state import workspace_state

logger = logging.getLogger("loopix.routes.deploy")
router = APIRouter()


@router.get("/api/deploy/command")
async def get_deploy_command():
    """Return the recommended deploy CLI command for the current workspace.

    Inspects the workspace root for known config files (vercel.json,
    Dockerfile, fly.toml, pyproject.toml, package.json) to determine the
    target platform, then returns:
      - platform: detected platform name
      - command: the CLI command to run (or null if unknown)
      - install: how to install the CLI tool (or null)
      - docs: link to the platform deployment docs
    """
    root = workspace_state.root
    if not root:
        raise HTTPException(status_code=400, detail="No workspace open. Open a folder first.")

    result = await generate_deploy_command(root)
    return {"success": True, **result}
