"""High-performance, secure, and namespace-agnostic KML parser using defusedxml and Shapely."""

from __future__ import annotations

import logging
import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import defusedxml.ElementTree as ET
from shapely.geometry import (
    GeometryCollection,
    LineString,
    MultiLineString,
    MultiPoint,
    MultiPolygon,
    Point,
    Polygon,
)
from shapely.geometry.base import BaseGeometry

from app.core.exceptions import CorruptedFileError

logger = logging.getLogger(__name__)

KML_DEFAULT_CRS = "EPSG:4326"


def _clean_tag(tag: str) -> str:
    """Strip XML namespace prefix from tag name."""
    if "}" in tag:
        return tag.split("}", 1)[1]
    return tag


def _find_child_by_tag(elem: ET.Element, target_tag: str) -> Optional[ET.Element]:
    """Find immediate child element matching tag name case-insensitively without namespace."""
    target_lower = target_tag.lower()
    for child in elem:
        if _clean_tag(child.tag).lower() == target_lower:
            return child
    return None


def _find_descendants_by_tag(elem: ET.Element, target_tag: str) -> List[ET.Element]:
    """Find all descendant elements matching tag name case-insensitively without namespace."""
    target_lower = target_tag.lower()
    results = []
    for item in elem.iter():
        if _clean_tag(item.tag).lower() == target_lower:
            results.append(item)
    return results


def _parse_coordinates_text(coord_text: str) -> List[Tuple[float, float]]:
    """Parse coordinate string from KML coordinates element.
    
    Format: 'lon,lat[,alt] lon,lat[,alt] ...' or separated by whitespace/newlines.
    """
    coords = []
    if not coord_text:
        return coords

    tokens = re.split(r"[\s\r\n\t]+", coord_text.strip())
    for token in tokens:
        if not token:
            continue
        parts = token.split(",")
        if len(parts) >= 2:
            try:
                lon = float(parts[0].strip())
                lat = float(parts[1].strip())
                coords.append((lon, lat))
            except ValueError:
                continue
    return coords


def _parse_geometry_element(elem: ET.Element) -> Optional[BaseGeometry]:
    """Parse a single KML geometry XML element into a Shapely geometry."""
    tag = _clean_tag(elem.tag).lower()

    if tag == "point":
        coord_elems = _find_descendants_by_tag(elem, "coordinates")
        if coord_elems and coord_elems[0].text:
            coords = _parse_coordinates_text(coord_elems[0].text)
            if coords:
                return Point(coords[0])

    elif tag == "linestring":
        coord_elems = _find_descendants_by_tag(elem, "coordinates")
        if coord_elems and coord_elems[0].text:
            coords = _parse_coordinates_text(coord_elems[0].text)
            if len(coords) >= 2:
                return LineString(coords)

    elif tag == "linearring":
        coord_elems = _find_descendants_by_tag(elem, "coordinates")
        if coord_elems and coord_elems[0].text:
            coords = _parse_coordinates_text(coord_elems[0].text)
            if len(coords) >= 3:
                return Polygon(coords)

    elif tag == "polygon":
        outer_ring = None
        inner_rings = []

        # Find outerBoundaryIs
        for child in elem:
            c_tag = _clean_tag(child.tag).lower()
            if c_tag == "outerboundaryis":
                coord_elems = _find_descendants_by_tag(child, "coordinates")
                if coord_elems and coord_elems[0].text:
                    coords = _parse_coordinates_text(coord_elems[0].text)
                    if len(coords) >= 3:
                        outer_ring = coords
            elif c_tag == "innerboundaryis":
                coord_elems = _find_descendants_by_tag(child, "coordinates")
                if coord_elems and coord_elems[0].text:
                    coords = _parse_coordinates_text(coord_elems[0].text)
                    if len(coords) >= 3:
                        inner_rings.append(coords)

        if outer_ring:
            return Polygon(outer_ring, inner_rings)

    elif tag == "multigeometry":
        sub_geoms = []
        for child in elem:
            g = _parse_geometry_element(child)
            if g is not None:
                sub_geoms.append(g)
        if sub_geoms:
            if all(isinstance(g, Polygon) for g in sub_geoms):
                return MultiPolygon(sub_geoms)
            elif all(isinstance(g, LineString) for g in sub_geoms):
                return MultiLineString(sub_geoms)
            elif all(isinstance(g, Point) for g in sub_geoms):
                return MultiPoint(sub_geoms)
            else:
                return GeometryCollection(sub_geoms)

    return None


def _extract_placemark_properties(placemark_elem: ET.Element) -> Dict[str, Any]:
    """Extract attributes, name, description, and ExtendedData from a Placemark."""
    props: Dict[str, Any] = {}
    for child in placemark_elem:
        tag = _clean_tag(child.tag).lower()
        if tag == "name" and child.text:
            props["name"] = child.text.strip()
        elif tag == "description" and child.text:
            props["description"] = child.text.strip()
        elif tag == "extendeddata":
            # Extract Data/value and SchemaData/SimpleData
            for ed_child in child:
                ed_tag = _clean_tag(ed_child.tag).lower()
                if ed_tag == "data":
                    name_attr = ed_child.attrib.get("name")
                    val_elems = _find_descendants_by_tag(ed_child, "value")
                    if name_attr and val_elems and val_elems[0].text:
                        props[name_attr] = val_elems[0].text.strip()
                elif ed_tag == "schemadata":
                    for sd_child in ed_child:
                        if _clean_tag(sd_child.tag).lower() == "simpledata":
                            name_attr = sd_child.attrib.get("name")
                            if name_attr and sd_child.text:
                                props[name_attr] = sd_child.text.strip()
    return props


def parse_kml_file(file_path: Path | str) -> List[Dict[str, Any]]:
    """Parse a KML file and extract all features.
    
    Returns a list of dicts with keys:
    - feature_id (int or str)
    - geometry_type (str)
    - geometry (BaseGeometry)
    - crs (str)
    - properties (dict)
    """
    path = Path(file_path)
    if not path.is_file():
        raise CorruptedFileError(f"KML file not found at {path}")

    try:
        tree = ET.parse(str(path))
        root = tree.getroot()
    except Exception as e:
        raise CorruptedFileError(f"Failed to parse XML in KML file: {e}") from e

    # Find all Placemark elements across all namespaces
    placemarks = [el for el in root.iter() if _clean_tag(el.tag).lower() == "placemark"]

    features = []
    for idx, pm in enumerate(placemarks):
        feature_id = pm.attrib.get("id") or f"feature_{idx + 1}"
        props = _extract_placemark_properties(pm)

        geometry = None
        for child in pm:
            geom = _parse_geometry_element(child)
            if geom is not None:
                geometry = geom
                break

        geom_type = geometry.geom_type if geometry is not None else "None"

        features.append(
            {
                "feature_id": feature_id,
                "geometry_type": geom_type,
                "geometry": geometry,
                "crs": KML_DEFAULT_CRS,
                "properties": props,
            }
        )

    return features
