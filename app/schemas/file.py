from __future__ import annotations

from enum import Enum
from typing import Dict, List, Optional
from pydantic import BaseModel, Field


class FileProcessingStatus(str, Enum):
    PENDING = "PENDING"
    PROCESSING = "PROCESSING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


class FileInfoResponse(BaseModel):
    """Response model for GET /api/files/{id}/ matching user specification."""
    id: str = Field(..., description="Unique file identifier")
    filename: str = Field(..., description="Uploaded file name")
    feature_count: int = Field(..., description="Total extracted feature count")
    crs: str = Field(..., description="Detected Coordinate Reference System")
    status: FileProcessingStatus = Field(..., description="Processing status")
    file_size_bytes: Optional[int] = Field(None, description="Size of uploaded file in bytes")
    geometry_breakdown: Dict[str, int] = Field(
        default_factory=dict, description="Counts of each geometry type found"
    )
    created_at: str = Field(..., description="ISO 8601 creation timestamp")
    error_message: Optional[str] = Field(None, description="Error detail if processing failed")


class FileUploadResponse(BaseModel):
    """Response returned upon successful file upload and processing."""
    id: str = Field(..., description="Unique file identifier")
    filename: str = Field(..., description="Uploaded file name")
    feature_count: int = Field(..., description="Total features extracted")
    crs: str = Field(..., description="Coordinate Reference System")
    status: FileProcessingStatus = Field(..., description="File status")
    message: str = Field("File uploaded and processed successfully", description="Status message")


class FileListResponse(BaseModel):
    """Response model for listing files."""
    total: int
    files: List[FileInfoResponse]
