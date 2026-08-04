from pydantic import BaseModel, Field
from typing import Dict, Optional, List

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


class WorkspaceChangeRequest(BaseModel):
    path: str = Field(..., description="Path to transition the active workspace to")


class WorkspaceChangeResponse(BaseModel):
    success: bool = Field(..., description="Indicates if change was successful")
    workspace: str = Field(..., description="The new active workspace path")


class WorkspaceInfoResponse(BaseModel):
    workspace: Optional[str] = Field(None, description="The current active workspace root path")


class DetectCommandRequest(BaseModel):
    file_path: str = Field(..., description="Path to the file to run")


class DetectCommandResponse(BaseModel):
    command: str = Field(..., description="AI detected or fallback CLI command line")


class ShellNameResponse(BaseModel):
    name: str = Field(..., description="Name of the shell platform executable")


class SSHHostRequest(BaseModel):
    name: str = Field(..., description="Remote host identifier name")
    host: str = Field(..., description="IP address or hostname")
    username: str = Field(..., description="SSH login username")
    port: int = Field(22, description="SSH connection port")


class SSHHostResponse(BaseModel):
    success: bool = Field(..., description="Indicates if host addition succeeded")
    host: dict = Field(..., description="Added remote SSH host profile details")


class RootsResponse(BaseModel):
    roots: List[str] = Field(..., description="List of secondary multi-root paths")
    active_root: str = Field(..., description="The currently active workspace root path")


class RootsAddResponse(BaseModel):
    success: bool = Field(..., description="Indicates if secondary root addition succeeded")
    roots: List[str] = Field(..., description="Updated secondary multi-root paths")


class SSHHostsResponse(BaseModel):
    hosts: List[dict] = Field(..., description="List of configured remote SSH profiles")
