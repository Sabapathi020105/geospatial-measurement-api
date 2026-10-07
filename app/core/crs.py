"""CRS (Coordinate Reference System) detection, management, and reprojection service.

Geospatial geometries in geographic CRS (such as EPSG:4326 / WGS84) have angular units
(degrees). Calculating Euclidean area or length in degrees leads to severe geographic
distortion. This module automatically selects an appropriate metric projected CRS
(Universal Transverse Mercator - UTM, Universal Polar Stereographic - UPS, or Equal Area)
and reprojects geometries before measurement calculations.
"""

from __future__ import annotations

import logging
import math
from functools import lru_cache
from typing import Tuple

from pyproj import CRS, Transformer
from pyproj.exceptions import CRSError
from shapely.geometry.base import BaseGeometry
from shapely.ops import transform

from app.core.exceptions import CRSProjectionError

logger = logging.getLogger(__name__)

DEFAULT_GEOGRAPHIC_CRS = "EPSG:4326"


@lru_cache(maxsize=128)
def get_transformer(source_crs_str: str, target_crs_str: str) -> Transformer:
    """Return a cached PyProj Transformer with always_xy=True (lon, lat ordering)."""
    try:
        src = CRS.from_user_input(source_crs_str)
        tgt = CRS.from_user_input(target_crs_str)
        return Transformer.from_crs(src, tgt, always_xy=True)
    except CRSError as e:
        raise CRSProjectionError(
            f"Failed to initialize transformer from '{source_crs_str}' to '{target_crs_str}': {e}"
        ) from e


def normalize_crs_string(crs_input: str | None) -> str:
    """Normalize input CRS representation to a clean EPSG or WKT string.
    
    Defaults to EPSG:4326 if not specified (standard for KML / GPS).
    """
    if not crs_input or str(crs_input).strip() == "" or str(crs_input).lower() == "none":
        return DEFAULT_GEOGRAPHIC_CRS

    crs_str = str(crs_input).strip()
    try:
        parsed = CRS.from_user_input(crs_str)
        epsg = parsed.to_epsg()
        if epsg:
            return f"EPSG:{epsg}"
        return parsed.to_string()
    except Exception:
        # Fallback to provided string if pyproj cannot parse
        return crs_str


def get_utm_epsg_for_lon_lat(lon: float, lat: float) -> str:
    """Calculate the EPSG code for the Universal Transverse Mercator (UTM) or Universal
    Polar Stereographic (UPS) zone containing the given geographic coordinates.
    
    Args:
        lon: Longitude in degrees (-180 to 180)
        lat: Latitude in degrees (-90 to 90)
        
    Returns:
        EPSG string, e.g., 'EPSG:32632' (North) or 'EPSG:32732' (South)
    """
    # Polar regions
    if lat > 84.0:
        return "EPSG:32661"  # UPS North
    if lat < -80.0:
        return "EPSG:32761"  # UPS South

    # Normal UTM zones (1 to 60)
    # Zone formula: floor((lon + 180) / 6) + 1
    normalized_lon = (lon + 180.0) % 360.0 - 180.0
    zone = int(math.floor((normalized_lon + 180.0) / 6.0)) + 1
    zone = max(1, min(60, zone))

    # Northern Hemisphere is 326xx, Southern Hemisphere is 327xx
    epsg_code = 32600 + zone if lat >= 0 else 32700 + zone
    return f"EPSG:{epsg_code}"


def project_geometry_to_metric(
    geometry: BaseGeometry,
    source_crs_str: str | None = None,
) -> Tuple[BaseGeometry, str]:
    """Reproject a Shapely geometry to an appropriate metric projected coordinate system.
    
    Strategy:
    1. Determine source CRS (defaults to EPSG:4326 if unspecified).
    2. If source CRS is already a projected metric CRS with valid units (e.g. UTM, State Plane,
       National Grid) and not EPSG:3857 (Web Mercator has high distortion), we can use it directly.
    3. If source CRS is geographic (degrees) or distorted (Web Mercator), convert centroid to
       EPSG:4326 to determine the optimal local UTM zone.
    4. Reproject geometry to the target projected CRS and return the projected geometry and CRS code.
    
    Args:
        geometry: Shapely geometry object
        source_crs_str: Input coordinate reference system representation
        
    Returns:
        Tuple of (projected_geometry, target_crs_code)
    """
    norm_source_crs = normalize_crs_string(source_crs_str)

    try:
        src_crs_obj = CRS.from_user_input(norm_source_crs)
    except Exception:
        norm_source_crs = DEFAULT_GEOGRAPHIC_CRS
        src_crs_obj = CRS.from_user_input(norm_source_crs)

    # Check if already projected in a suitable non-distorted metric CRS
    if src_crs_obj.is_projected:
        epsg = src_crs_obj.to_epsg()
        # EPSG:3857 (Web Mercator) preserves shapes locally but distorts area/distance significantly away from equator.
        # Reproject EPSG:3857 to local UTM for accurate measurements.
        if epsg != 3857:
            # Check linear units
            try:
                units = src_crs_obj.axis_info[0].unit_name.lower()
                if "metre" in units or "meter" in units:
                    return geometry, norm_source_crs
            except Exception:
                pass

    # Source is geographic or distorted: determine centroid in WGS84 (EPSG:4326)
    if norm_source_crs != DEFAULT_GEOGRAPHIC_CRS:
        # Reproject to EPSG:4326 first to inspect centroid coordinates in lon/lat
        to_wgs84 = get_transformer(norm_source_crs, DEFAULT_GEOGRAPHIC_CRS)
        wgs84_geom = transform(to_wgs84.transform, geometry)
    else:
        wgs84_geom = geometry

    centroid = wgs84_geom.centroid
    target_crs = get_utm_epsg_for_lon_lat(centroid.x, centroid.y)

    # Transform geometry from source CRS to target projected CRS
    to_metric = get_transformer(norm_source_crs, target_crs)
    projected_geom = transform(to_metric.transform, geometry)

    return projected_geom, target_crs
