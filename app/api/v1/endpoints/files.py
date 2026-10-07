"""File upload, retrieval, and metadata endpoints."""

from __future__ import annotations

from typing import List
from fastapi import APIRouter, File, HTTPException, Query, UploadFile, status

from app.core.exceptions import (
    CorruptedFileError,
    FileNotFoundCustomError,
    InvalidFileFormatError,
    MissingShapefileComponentsError,
)
from app.schemas.feature import FeatureListResponse
from app.schemas.file import FileInfoResponse, FileListResponse
from app.services.file_service import FileService

router = APIRouter(prefix="/files", tags=["Files"])


@router.post(
    "/",
    response_model=FileInfoResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Upload and process a geospatial file",
    description="Upload a Shapefile (.zip) or KML (.kml) file for feature extraction and measurement calculation.",
)
async def upload_file(
    file: UploadFile = File(..., description="Geospatial file (.zip Shapefile or .kml)"),
) -> FileInfoResponse:
    try:
        return await FileService.save_and_process_file(file)
    except InvalidFileFormatError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=e.message)
    except (CorruptedFileError, MissingShapefileComponentsError) as e:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=e.message)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"An unexpected error occurred during processing: {e}",
        )


@router.get(
    "/",
    response_model=FileListResponse,
    summary="List all uploaded geospatial files",
    description="Retrieve paginated list of uploaded geospatial files and their processing statuses.",
)
def list_files(
    limit: int = Query(50, ge=1, le=100, description="Items per page"),
    offset: int = Query(0, ge=0, description="Pagination offset"),
) -> FileListResponse:
    total, items = FileService.list_files(limit=limit, offset=offset)
    return FileListResponse(total=total, files=items)


@router.get(
    "/{file_id}/",
    response_model=FileInfoResponse,
    summary="Get file information",
    description="Retrieve processing status, feature count, detected CRS, and metadata for a specific file.",
)
@router.get(
    "/{file_id}",
    response_model=FileInfoResponse,
    include_in_schema=False,
)
def get_file_info(file_id: str) -> FileInfoResponse:
    try:
        return FileService.get_file_info(file_id)
    except FileNotFoundCustomError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=e.message)


@router.get(
    "/{file_id}/features/",
    summary="Get extracted features",
    description="Retrieve raw features with geometries, CRS, and attributes extracted from the file.",
)
@router.get(
    "/{file_id}/features",
    include_in_schema=False,
)
def get_file_features(file_id: str):
    try:
        return FileService.get_file_features(file_id)
    except FileNotFoundCustomError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=e.message)


@router.delete(
    "/{file_id}/",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a file",
    description="Delete an uploaded geospatial file, its extracted features, and measurements.",
)
@router.delete(
    "/{file_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    include_in_schema=False,
)
def delete_file(file_id: str):
    try:
        FileService.delete_file(file_id)
    except FileNotFoundCustomError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=e.message)
