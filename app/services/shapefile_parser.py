"""Secure and robust Shapefile (.zip) parser using Fiona and Shapely."""

from __future__ import annotations

import datetime
import logging
import os
import shutil
import tempfile
import zipfile
from pathlib import Path
from typing import Any, Dict, List, Optional

import fiona
from shapely.geometry import shape

from app.core.crs import normalize_crs_string
from app.core.exceptions import (
    CorruptedFileError,
    MissingShapefileComponentsError,
)

logger = logging.getLogger(__name__)


def _sanitize_property_value(value: Any) -> Any:
    """Convert dBase/shapefile property values to JSON-serializable types."""
    if isinstance(value, (datetime.date, datetime.datetime)):
        return value.isoformat()
    if isinstance(value, bytes):
        return value.decode("utf-8", errors="replace")
    return value


def _safe_extract_zip(zip_path: Path, extract_dir: Path) -> List[Path]:
    """Safely unpack a ZIP archive preventing Zip Slip directory traversal."""
    extracted_files = []
    try:
        with zipfile.ZipFile(zip_path, "r") as zf:
            for member in zf.infolist():
                # Prevent directory traversal vulnerability
                target_path = (extract_dir / member.filename).resolve()
                if not str(target_path).startswith(str(extract_dir.resolve())):
                    raise CorruptedFileError(
                        f"Zip Slip attempt detected in archive member: {member.filename}"
                    )
                zf.extract(member, extract_dir)
                extracted_files.append(target_path)
    except zipfile.BadZipFile as e:
        raise CorruptedFileError(f"Uploaded zip archive is invalid or corrupted: {e}") from e

    return extracted_files


def parse_shapefile_zip(zip_path: Path | str) -> List[Dict[str, Any]]:
    """Extract and parse a Shapefile from a ZIP archive.
    
    Returns a list of feature dicts:
    - feature_id (int or str)
    - geometry_type (str)
    - geometry (BaseGeometry)
    - crs (str)
    - properties (dict)
    """
    path = Path(zip_path)
    if not path.is_file():
        raise CorruptedFileError(f"Shapefile zip archive not found at {path}")

    temp_dir = Path(tempfile.mkdtemp(prefix="shp_extract_"))
    try:
        extracted = _safe_extract_zip(path, temp_dir)

        # Locate the .shp file
        shp_files = [p for p in extracted if p.suffix.lower() == ".shp"]
        if not shp_files:
            # Also search recursively in case top-level was a folder
            shp_files = list(temp_dir.rglob("*.shp"))

        if not shp_files:
            raise MissingShapefileComponentsError(
                "ZIP archive does not contain a .shp file. Ensure a valid ESRI Shapefile is included."
            )

        shp_file = shp_files[0]

        # Verify companion files (.shx, .dbf)
        companion_base = shp_file.with_suffix("")
        has_shx = companion_base.with_suffix(".shx").exists() or companion_base.with_suffix(".SHX").exists()
        has_dbf = companion_base.with_suffix(".dbf").exists() or companion_base.with_suffix(".DBF").exists()

        if not has_shx or not has_dbf:
            logger.warning(
                f"Shapefile '{shp_file.name}' is missing .shx or .dbf companion file. Reading with best effort."
            )

        features = []
        with fiona.open(str(shp_file)) as src:
            # Determine CRS
            crs_str = None
            if src.crs:
                try:
                    crs_str = normalize_crs_string(src.crs.to_string())
                except Exception:
                    crs_str = normalize_crs_string(str(src.crs))
            if not crs_str or crs_str == "None":
                crs_str = "EPSG:4326"

            for idx, feat in enumerate(src):
                feat_id = feat.get("id") or str(idx)
                raw_geom = feat.get("geometry")

                geometry = None
                geom_type = "None"
                if raw_geom:
                    try:
                        geometry = shape(raw_geom)
                        geom_type = geometry.geom_type
                    except Exception as e:
                        logger.warning(f"Failed to parse geometry for feature {feat_id}: {e}")
                        geom_type = raw_geom.get("type", "Unknown")

                # Sanitize attributes
                raw_props = feat.get("properties") or {}
                clean_props = {
                    k: _sanitize_property_value(v) for k, v in raw_props.items()
                }

                features.append(
                    {
                        "feature_id": feat_id,
                        "geometry_type": geom_type,
                        "geometry": geometry,
                        "crs": crs_str,
                        "properties": clean_props,
                    }
                )

        return features

    finally:
        # Cleanup temporary directory
        if temp_dir.exists():
            shutil.rmtree(temp_dir, ignore_errors=True)
