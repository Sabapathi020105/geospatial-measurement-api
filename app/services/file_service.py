"""File management, upload coordination, and processing orchestration service."""

from __future__ import annotations

import logging
import os
import shutil
import uuid
from collections import Counter
from pathlib import Path
from typing import BinaryIO, Dict, Tuple

from fastapi import UploadFile

from app.config import settings
from app.core.exceptions import (
    CorruptedFileError,
    FileNotFoundCustomError,
    InvalidFileFormatError,
)
from app.db.storage import storage
from app.schemas.file import FileInfoResponse, FileProcessingStatus
from app.schemas.measurement import FileMeasurementResponse, MeasurementDetail, MeasurementSummary
from app.services.kml_parser import parse_kml_file
from app.services.measurement_service import calculate_measurements_for_features
from app.services.shapefile_parser import parse_shapefile_zip

logger = logging.getLogger(__name__)


class FileService:
    """Orchestrates upload storage, format routing, parsing, and measurement storage."""

    @staticmethod
    def _validate_extension(filename: str) -> str:
        """Validate and return lower-cased file extension."""
        ext = Path(filename).suffix.lower()
        if ext not in settings.ALLOWED_EXTENSIONS:
            raise InvalidFileFormatError(
                f"Unsupported file format '{ext}'. Allowed formats are: {sorted(list(settings.ALLOWED_EXTENSIONS))}"
            )
        return ext

    @classmethod
    async def save_and_process_file(cls, upload_file: UploadFile) -> FileInfoResponse:
        """Handle uploaded file stream, save to disk, parse geometries, and store measurements."""
        filename = upload_file.filename or "unknown_file"
        ext = cls._validate_extension(filename)

        file_id = uuid.uuid4().hex[:12]
        safe_saved_name = f"{file_id}_{Path(filename).name}"
        saved_path = settings.UPLOAD_DIR / safe_saved_name

        # Stream upload file to disk and enforce max size
        total_size = 0
        max_bytes = settings.MAX_FILE_SIZE_MB * 1024 * 1024

        try:
            with open(saved_path, "wb") as out_file:
                while chunk := await upload_file.read(1024 * 64):  # 64 KB chunks
                    total_size += len(chunk)
                    if total_size > max_bytes:
                        raise InvalidFileFormatError(
                            f"File size exceeds limit of {settings.MAX_FILE_SIZE_MB}MB."
                        )
                    out_file.write(chunk)
        except Exception:
            if saved_path.exists():
                saved_path.unlink()
            raise

        # Initialize record in storage
        storage.save_file_record(
            file_id=file_id,
            filename=filename,
            file_path=str(saved_path),
            file_size_bytes=total_size,
            crs="UNKNOWN",
            status=FileProcessingStatus.PROCESSING.value,
        )

        try:
            # Parse based on extension
            if ext == ".zip":
                raw_features = parse_shapefile_zip(saved_path)
            elif ext == ".kml":
                raw_features = parse_kml_file(saved_path)
            else:
                raise InvalidFileFormatError(f"Unsupported extension {ext}")

            # Calculate measurements and normalized features
            normalized_features, measurements_data, summary = calculate_measurements_for_features(
                raw_features
            )

            # Determine dominant/detected CRS
            detected_crs = "EPSG:4326"
            if raw_features:
                crs_candidates = [f["crs"] for f in raw_features if f.get("crs")]
                if crs_candidates:
                    detected_crs = crs_candidates[0]

            # Geometry type counts
            type_counts = dict(Counter(f["geometry_type"] for f in raw_features))

            # Store in database
            storage.save_features_and_measurements(
                file_id=file_id,
                features=normalized_features,
                measurements=measurements_data,
            )

            storage.update_file_completed(
                file_id=file_id,
                feature_count=len(raw_features),
                crs=detected_crs,
                geometry_breakdown=type_counts,
                status=FileProcessingStatus.COMPLETED.value,
            )

            file_record = storage.get_file(file_id)
            return FileInfoResponse(
                id=file_record["id"],
                filename=file_record["filename"],
                feature_count=file_record["feature_count"],
                crs=file_record["crs"],
                status=FileProcessingStatus(file_record["status"]),
                file_size_bytes=file_record["file_size_bytes"],
                geometry_breakdown=file_record["geometry_breakdown"],
                created_at=file_record["created_at"],
            )

        except Exception as e:
            logger.exception(f"Error processing file {file_id}: {e}")
            storage.update_file_failed(file_id, str(e))
            raise

    @classmethod
    def get_file_info(cls, file_id: str) -> FileInfoResponse:
        """Fetch metadata for an uploaded file."""
        file_record = storage.get_file(file_id)
        return FileInfoResponse(
            id=file_record["id"],
            filename=file_record["filename"],
            feature_count=file_record["feature_count"],
            crs=file_record["crs"],
            status=FileProcessingStatus(file_record["status"]),
            file_size_bytes=file_record["file_size_bytes"],
            geometry_breakdown=file_record["geometry_breakdown"],
            created_at=file_record["created_at"],
            error_message=file_record.get("error_message"),
        )

    @classmethod
    def get_file_measurements(cls, file_id: str) -> FileMeasurementResponse:
        """Fetch calculated measurements for a file."""
        file_record = storage.get_file(file_id)
        raw_measurements = storage.get_measurements(file_id)

        measurements = []
        summary = MeasurementSummary(total_features=len(raw_measurements))

        for m in raw_measurements:
            detail = MeasurementDetail(
                feature_id=m["feature_id"],
                geometry_type=m["geometry_type"],
                properties=m.get("properties", {}),
                is_supported=m["is_supported"],
                measurement_status=m["measurement_status"],
                area_sq_m=m["area_sq_m"],
                area_hectares=m["area_hectares"],
                area_sq_km=m["area_sq_km"],
                length_m=m["length_m"],
                length_km=m["length_km"],
                projected_crs=m["projected_crs"],
                message=m["message"],
            )
            measurements.append(detail)

            # Accumulate summary
            if detail.area_sq_m is not None:
                summary.polygon_count += 1
                summary.total_area_sq_m += detail.area_sq_m
            elif detail.length_m is not None:
                summary.linestring_count += 1
                summary.total_length_m += detail.length_m
            elif detail.geometry_type in {"Point", "MultiPoint"}:
                summary.point_count += 1
            else:
                summary.unsupported_count += 1

        summary.total_area_sq_m = round(summary.total_area_sq_m, 4)
        summary.total_area_hectares = round(summary.total_area_sq_m / 10000.0, 6)
        summary.total_area_sq_km = round(summary.total_area_sq_m / 1_000_000.0, 6)
        summary.total_length_m = round(summary.total_length_m, 4)
        summary.total_length_km = round(summary.total_length_m / 1000.0, 6)

        return FileMeasurementResponse(
            file_id=file_record["id"],
            filename=file_record["filename"],
            crs=file_record["crs"],
            summary=summary,
            features=measurements,
        )

    @classmethod
    def get_file_features(cls, file_id: str):
        """Fetch extracted raw features for a file."""
        file_record = storage.get_file(file_id)
        features = storage.get_features(file_id)
        return {
            "file_id": file_record["id"],
            "total_features": len(features),
            "features": features,
        }

    @classmethod
    def list_files(cls, limit: int = 50, offset: int = 0) -> Tuple[int, list[FileInfoResponse]]:
        """List uploaded files with pagination."""
        total, rows = storage.list_files(limit=limit, offset=offset)
        items = [
            FileInfoResponse(
                id=r["id"],
                filename=r["filename"],
                feature_count=r["feature_count"],
                crs=r["crs"],
                status=FileProcessingStatus(r["status"]),
                file_size_bytes=r["file_size_bytes"],
                geometry_breakdown=r["geometry_breakdown"],
                created_at=r["created_at"],
                error_message=r.get("error_message"),
            )
            for r in rows
        ]
        return total, items

    @classmethod
    def delete_file(cls, file_id: str) -> None:
        """Delete file and its storage entries."""
        file_record = storage.get_file(file_id)
        file_path = Path(file_record["file_path"])
        if file_path.exists():
            file_path.unlink()
        storage.delete_file(file_id)
