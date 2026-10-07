from __future__ import annotations

from enum import Enum
from typing import Any, Dict, List, Optional, Union
from pydantic import BaseModel, Field


class MeasurementStatus(str, Enum):
    CALCULATED = "CALCULATED"
    NOT_APPLICABLE = "NOT_APPLICABLE"
    UNSUPPORTED_GEOMETRY = "UNSUPPORTED_GEOMETRY"
    ERROR = "ERROR"


class MeasurementDetail(BaseModel):
    """Measurement outcome for a single feature."""
    feature_id: Union[int, str] = Field(..., description="ID or index of the feature")
    geometry_type: str = Field(..., description="Geometry type of the feature")
    properties: Dict[str, Any] = Field(default_factory=dict, description="Feature attributes")
    is_supported: bool = Field(..., description="Whether geometry supports measurement calculation")
    measurement_status: MeasurementStatus = Field(..., description="Status of the measurement")
    
    # Area measurements (for Polygon / MultiPolygon)
    area_sq_m: Optional[float] = Field(None, description="Area in square meters (m²)")
    area_hectares: Optional[float] = Field(None, description="Area in hectares (ha)")
    area_sq_km: Optional[float] = Field(None, description="Area in square kilometers (km²)")
    
    # Length measurements (for LineString / MultiLineString)
    length_m: Optional[float] = Field(None, description="Length in meters (m)")
    length_km: Optional[float] = Field(None, description="Length in kilometers (km)")
    
    # CRS used for calculation
    projected_crs: Optional[str] = Field(
        None, description="Metric projected CRS used to calculate measurements without angular distortion"
    )
    message: Optional[str] = Field(None, description="Informational message or reason if not applicable/unsupported")


class MeasurementSummary(BaseModel):
    """Aggregated measurements across all features in a file."""
    total_features: int = Field(0, description="Total number of features in the file")
    polygon_count: int = Field(0, description="Number of polygon features")
    linestring_count: int = Field(0, description="Number of linestring features")
    point_count: int = Field(0, description="Number of point features (no measurement applicable)")
    unsupported_count: int = Field(0, description="Number of unsupported geometries")
    
    total_area_sq_m: float = Field(0.0, description="Sum of area across all polygons in square meters")
    total_area_hectares: float = Field(0.0, description="Sum of area in hectares")
    total_area_sq_km: float = Field(0.0, description="Sum of area in square kilometers")
    
    total_length_m: float = Field(0.0, description="Sum of length across all linestrings in meters")
    total_length_km: float = Field(0.0, description="Sum of length in kilometers")


class FileMeasurementResponse(BaseModel):
    """Response model for GET /api/files/{id}/measurements/."""
    file_id: str = Field(..., description="Unique file ID")
    filename: str = Field(..., description="Original filename")
    crs: str = Field(..., description="Source coordinate reference system")
    summary: MeasurementSummary = Field(..., description="Aggregated metric summary")
    features: List[MeasurementDetail] = Field(default_factory=list, description="Measurements per feature")
