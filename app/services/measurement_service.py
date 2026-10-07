"""Service responsible for extracting features and computing accurate metric measurements."""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Tuple

from shapely.geometry import mapping
from shapely.geometry.base import BaseGeometry

from app.core.crs import project_geometry_to_metric
from app.schemas.measurement import MeasurementDetail, MeasurementStatus, MeasurementSummary

logger = logging.getLogger(__name__)

# Geometries supported for area calculation
POLYGON_TYPES = {"Polygon", "MultiPolygon"}

# Geometries supported for length calculation
LINE_TYPES = {"LineString", "MultiLineString", "LinearRing"}

# Geometries with no applicable measurement
POINT_TYPES = {"Point", "MultiPoint"}


def process_feature_measurement(
    feature_id: Any,
    geom: BaseGeometry | None,
    geom_type: str,
    source_crs: str,
    properties: Dict[str, Any],
) -> MeasurementDetail:
    """Calculate measurements for a single feature with appropriate CRS projection."""
    if geom is None or geom.is_empty:
        return MeasurementDetail(
            feature_id=str(feature_id),
            geometry_type=geom_type or "Empty",
            properties=properties,
            is_supported=False,
            measurement_status=MeasurementStatus.UNSUPPORTED_GEOMETRY,
            message="Geometry is empty or missing; measurement cannot be computed.",
        )

    # Point geometries require no measurement
    if geom_type in POINT_TYPES:
        return MeasurementDetail(
            feature_id=str(feature_id),
            geometry_type=geom_type,
            properties=properties,
            is_supported=False,
            measurement_status=MeasurementStatus.NOT_APPLICABLE,
            projected_crs=None,
            message="Measurement not applicable for Point geometry.",
        )

    # Polygon geometries: calculate area
    if geom_type in POLYGON_TYPES:
        try:
            proj_geom, proj_crs = project_geometry_to_metric(geom, source_crs)
            area_m2 = round(float(proj_geom.area), 4)
            area_ha = round(area_m2 / 10000.0, 6)
            area_km2 = round(area_m2 / 1_000_000.0, 6)

            return MeasurementDetail(
                feature_id=str(feature_id),
                geometry_type=geom_type,
                properties=properties,
                is_supported=True,
                measurement_status=MeasurementStatus.CALCULATED,
                area_sq_m=area_m2,
                area_hectares=area_ha,
                area_sq_km=area_km2,
                projected_crs=proj_crs,
                message="Area successfully calculated in metric projected CRS.",
            )
        except Exception as e:
            logger.error(f"Failed to calculate area for feature {feature_id}: {e}")
            return MeasurementDetail(
                feature_id=str(feature_id),
                geometry_type=geom_type,
                properties=properties,
                is_supported=True,
                measurement_status=MeasurementStatus.ERROR,
                message=f"Failed to calculate area: {e}",
            )

    # LineString geometries: calculate length
    if geom_type in LINE_TYPES:
        try:
            proj_geom, proj_crs = project_geometry_to_metric(geom, source_crs)
            length_m = round(float(proj_geom.length), 4)
            length_km = round(length_m / 1000.0, 6)

            return MeasurementDetail(
                feature_id=str(feature_id),
                geometry_type=geom_type,
                properties=properties,
                is_supported=True,
                measurement_status=MeasurementStatus.CALCULATED,
                length_m=length_m,
                length_km=length_km,
                projected_crs=proj_crs,
                message="Length successfully calculated in metric projected CRS.",
            )
        except Exception as e:
            logger.error(f"Failed to calculate length for feature {feature_id}: {e}")
            return MeasurementDetail(
                feature_id=str(feature_id),
                geometry_type=geom_type,
                properties=properties,
                is_supported=True,
                measurement_status=MeasurementStatus.ERROR,
                message=f"Failed to calculate length: {e}",
            )

    # Any other unsupported geometry type (e.g. GeometryCollection, Tin, PolyhedralSurface)
    return MeasurementDetail(
        feature_id=str(feature_id),
        geometry_type=geom_type,
        properties=properties,
        is_supported=False,
        measurement_status=MeasurementStatus.UNSUPPORTED_GEOMETRY,
        message=f"Geometry type '{geom_type}' is not supported for measurement calculation.",
    )


def calculate_measurements_for_features(
    raw_features: List[Dict[str, Any]],
) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]], MeasurementSummary]:
    """Process a list of parsed features:
    
    1. Prepares normalized feature records (with GeoJSON geometry).
    2. Computes measurements for each feature.
    3. Builds aggregated summary statistics.
    """
    normalized_features = []
    measurements_data = []

    summary = MeasurementSummary(total_features=len(raw_features))

    for feat in raw_features:
        f_id = feat["feature_id"]
        geom = feat.get("geometry")
        geom_type = feat.get("geometry_type", "Unknown")
        crs = feat.get("crs", "EPSG:4326")
        props = feat.get("properties", {})

        # GeoJSON representation for feature inspection
        geojson_geom = mapping(geom) if geom is not None and not geom.is_empty else None

        normalized_features.append(
            {
                "feature_id": str(f_id),
                "geometry_type": geom_type,
                "geometry": geojson_geom,
                "crs": crs,
                "properties": props,
            }
        )

        detail = process_feature_measurement(f_id, geom, geom_type, crs, props)
        detail_dict = detail.model_dump()
        measurements_data.append(detail_dict)

        # Update summary counters
        if geom_type in POLYGON_TYPES:
            summary.polygon_count += 1
            if detail.area_sq_m is not None:
                summary.total_area_sq_m += detail.area_sq_m
        elif geom_type in LINE_TYPES:
            summary.linestring_count += 1
            if detail.length_m is not None:
                summary.total_length_m += detail.length_m
        elif geom_type in POINT_TYPES:
            summary.point_count += 1
        else:
            summary.unsupported_count += 1

    summary.total_area_sq_m = round(summary.total_area_sq_m, 4)
    summary.total_area_hectares = round(summary.total_area_sq_m / 10000.0, 6)
    summary.total_area_sq_km = round(summary.total_area_sq_m / 1_000_000.0, 6)
    summary.total_length_m = round(summary.total_length_m, 4)
    summary.total_length_km = round(summary.total_length_m / 1000.0, 6)

    return normalized_features, measurements_data, summary
