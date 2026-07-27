from pydantic import BaseModel, Field
from typing import Optional

class FileItemResponse(BaseModel):
    """Schema for a single file or directory item."""
    name: str = Field(..., description="File or directory name")
    path: str = Field(..., description="Relative path within workspace")
    is_dir: bool = Field(..., description="True if item is a directory")
    size: Optional[int] = Field(None, description="Size in bytes if file")


class FileCreateRequest(BaseModel):
    """Schema for creating a new file or directory."""
    path: str = Field(..., min_length=1, description="Relative path of file or folder to create")
    is_dir: bool = Field(False, description="Set to true if creating a folder")
    content: Optional[str] = Field("", description="Initial text content for file")


class FileContentResponse(BaseModel):
    """Schema for reading file contents."""
    path: str
    content: str
    size: int
