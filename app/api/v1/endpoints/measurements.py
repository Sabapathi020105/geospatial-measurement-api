"""Measurement retrieval endpoint."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, status

from app.core.exceptions import FileNotFoundCustomError
from app.schemas.measurement import FileMeasurementResponse
from app.services.file_service import FileService

router = APIRouter(prefix="/files", tags=["Measurements"])


@router.get(
    "/{file_id}/measurements/",
    response_model=FileMeasurementResponse,
    summary="Get measurements for features in the file",
    description=(
        "Retrieve computed measurements for all features in the file. "
        "Polygons include Area (m², ha, km²). "
        "LineStrings include Length (m, km). "
        "Points and unsupported geometries are gracefully reported without errors."
    ),
)
@router.get(
    "/{file_id}/measurements",
    response_model=FileMeasurementResponse,
    include_in_schema=False,
)
def get_measurements(file_id: str) -> FileMeasurementResponse:
    try:
        return FileService.get_file_measurements(file_id)
    except FileNotFoundCustomError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=e.message)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"An error occurred while fetching measurements: {e}",
        )
