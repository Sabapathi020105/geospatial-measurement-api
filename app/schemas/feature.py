from __future__ import annotations

from typing import Any, Dict, Optional, Union
from pydantic import BaseModel, Field


class FeatureGeoJSONGeometry(BaseModel):
    """GeoJSON geometry representation."""
    type: str = Field(..., description="Geometry type, e.g. Point, LineString, Polygon")
    coordinates: Any = Field(..., description="Coordinates array according to GeoJSON specification")


class FeatureSchema(BaseModel):
    """Normalized feature representation extracted from geospatial files."""
    feature_id: Union[int, str] = Field(..., description="Feature ID or index in dataset")
    geometry_type: str = Field(..., description="Type of geometry (Polygon, LineString, Point, etc.)")
    geometry: Optional[FeatureGeoJSONGeometry] = Field(None, description="GeoJSON geometry object")
    crs: str = Field(..., description="Coordinate Reference System of the source geometry")
    properties: Dict[str, Any] = Field(default_factory=dict, description="Attributes / property metadata")


class FeatureListResponse(BaseModel):
    """Paginated or listed features for a file."""
    file_id: str
    total_features: int
    features: list[FeatureSchema]
