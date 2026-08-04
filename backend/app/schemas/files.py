from pydantic import BaseModel, Field
from typing import Optional, List

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


class FileCreateResponse(BaseModel):
    success: bool = Field(..., description="Indicates if directory or file creation succeeded")


class FileContentResponse(BaseModel):
    """Schema for reading file contents."""
    path: str = Field(..., description="Relative path to file")
    content: str = Field(..., description="Contents of the file")
    size: int = Field(..., description="Size of file in bytes")


class FileSaveRequest(BaseModel):
    """Schema for saving file contents."""
    path: str = Field(..., min_length=1, description="Relative path to file to save")
    content: str = Field(..., description="File contents to write")


class FileSaveResponse(BaseModel):
    success: bool = Field(..., description="Indicates if saving content succeeded")


class FileDeleteRequest(BaseModel):
    """Schema for deleting a file or directory."""
    path: str = Field(..., min_length=1, description="Relative path to delete")


class FileDeleteResponse(BaseModel):
    success: bool = Field(..., description="Indicates if deletion succeeded")


class FileRenameRequest(BaseModel):
    """Schema for renaming/moving a file or directory."""
    old_path: str = Field(..., min_length=1, description="Source relative path")
    new_path: str = Field(..., min_length=1, description="Target relative path")


class FileRenameResponse(BaseModel):
    success: bool = Field(..., description="Indicates if renaming succeeded")


class RollbackRequest(BaseModel):
    """Schema for rolling back a file to a previous version."""
    path: str = Field(..., min_length=1, description="Relative path of file to roll back")
    timestamp: Optional[int] = Field(None, description="Optional Unix timestamp target version")


class RollbackResponse(BaseModel):
    success: bool = Field(..., description="Indicates if rollback succeeded")
