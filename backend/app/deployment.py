"""AI Deployment Pipeline — NOT YET IMPLEMENTED.

This module previously returned hardcoded fake success responses for
every deployment request regardless of actual build state (B4 from the
audit report). This has been replaced with an honest error response.

To implement real deployment:
- Integrate with your CI/CD provider (GitHub Actions, CircleCI, etc.)
- Or implement actual build steps (build, test, containerize, push, deploy)
"""
import logging
import os
from typing import Dict, Any, Optional

logger = logging.getLogger("devpilot.deployment")


async def generate_deploy_command(workspace_root: str) -> Dict[str, Any]:
    """Return the deploy CLI command for the detected project type.

    Detects project type by inspecting the workspace root for known config
    files, then returns the appropriate command and install instructions.
    This is purely advisory — DevPilot does not execute the command.
    """
    has_vercel = os.path.exists(os.path.join(workspace_root, "vercel.json"))
    has_pkg = os.path.exists(os.path.join(workspace_root, "package.json"))
    has_pyproject = os.path.exists(os.path.join(workspace_root, "pyproject.toml"))
    has_requirements = os.path.exists(os.path.join(workspace_root, "requirements.txt"))
    has_dockerfile = os.path.exists(os.path.join(workspace_root, "Dockerfile"))
    has_fly = os.path.exists(os.path.join(workspace_root, "fly.toml"))

    if has_fly:
        return {
            "platform": "Fly.io",
            "command": "fly deploy",
            "install": "curl -L https://fly.io/install.sh | sh && fly auth login",
            "docs": "https://fly.io/docs/",
        }
    if has_vercel or (has_pkg and not has_dockerfile):
        return {
            "platform": "Vercel",
            "command": "vercel deploy --prod",
            "install": "npm i -g vercel && vercel login",
            "docs": "https://vercel.com/docs",
        }
    if has_dockerfile:
        return {
            "platform": "Docker",
            "command": "docker build -t myapp . && docker run -p 8000:8000 myapp",
            "install": None,
            "docs": "https://docs.docker.com/",
        }
    if has_pyproject or has_requirements:
        return {
            "platform": "Railway",
            "command": "railway up",
            "install": "npm i -g @railway/cli && railway login",
            "docs": "https://docs.railway.app/",
        }
    return {
        "platform": "Unknown",
        "command": None,
        "install": None,
        "message": (
            "Could not detect project type from workspace root. "
            "Add a vercel.json, Dockerfile, fly.toml, or pyproject.toml to enable deploy command suggestions."
        ),
    }


class AIDeploymentPipeline:
    def execute_deployment_pipeline(self, target_env: str = "production") -> Dict[str, Any]:
        """Deployment pipeline placeholder.

        IMPORTANT: This feature is not yet implemented.
        Returns an honest error instead of a fake success.
        """
        logger.warning(
            "execute_deployment_pipeline() called but the deployment feature "
            "is not yet implemented. Returning a clear error to the caller."
        )
        return {
            "success": False,
            "is_stub": True,
            "environment": target_env,
            "error": (
                "Deployment pipeline is not yet implemented. "
                "Configure a real CI/CD provider or implement build steps "
                "before using this feature."
            ),
            "pipeline_steps": []
        }


ai_deployment_pipeline = AIDeploymentPipeline()
