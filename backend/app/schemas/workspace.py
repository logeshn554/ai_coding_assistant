from pydantic import BaseModel, Field
from typing import Dict, Optional

class WorkspaceStatsResponse(BaseModel):
    """Schema for workspace analytics and language breakdown."""
    total_files: int = Field(..., description="Total file count in workspace")
    total_lines: int = Field(..., description="Total lines of code")
    languages: Dict[str, int] = Field(..., description="Breakdown of file count per language")
    git_commits: int = Field(0, description="Total git commits in repository")


class HealthCheckResponse(BaseModel):
    """Schema for backend health check response."""
    status: str = Field("healthy", description="Status of the application")
    version: str = Field(..., description="API Version")
    timestamp: str = Field(..., description="ISO 8601 UTC timestamp")
