import pytest
from shapely.geometry import Polygon, LineString, Point
from app.core.crs import (
    get_utm_epsg_for_lon_lat,
    normalize_crs_string,
    project_geometry_to_metric,
)


def test_utm_zone_determination():
    # San Francisco: ~ -122.4, 37.7 -> UTM Zone 10N -> EPSG:32610
    assert get_utm_epsg_for_lon_lat(-122.4, 37.7) == "EPSG:32610"

    # London: ~ 0.1, 51.5 -> UTM Zone 31N -> EPSG:32631
    assert get_utm_epsg_for_lon_lat(0.1, 51.5) == "EPSG:32631"

    # Tokyo: ~ 139.7, 35.6 -> UTM Zone 54N -> EPSG:32654
    assert get_utm_epsg_for_lon_lat(139.7, 35.6) == "EPSG:32654"

    # Sydney (Southern Hemisphere): ~ 151.2, -33.8 -> UTM Zone 56S -> EPSG:32756
    assert get_utm_epsg_for_lon_lat(151.2, -33.8) == "EPSG:32756"

    # Polar Regions
    assert get_utm_epsg_for_lon_lat(10.0, 85.0) == "EPSG:32661"
    assert get_utm_epsg_for_lon_lat(10.0, -85.0) == "EPSG:32761"


def test_normalize_crs_string():
    assert normalize_crs_string("EPSG:4326") == "EPSG:4326"
    assert normalize_crs_string(None) == "EPSG:4326"
    assert normalize_crs_string("4326") == "EPSG:4326"
    assert normalize_crs_string("urn:ogc:def:crs:EPSG::4326") == "EPSG:4326"


def test_project_polygon_metric_accuracy():
    # 0.001 degree square near San Francisco (~ 37.77 deg N, -122.41 deg W)
    # 1 deg latitude is approx 111,000 meters. 0.001 deg is approx 111 meters.
    # 1 deg longitude at 37.77 N is 111,000 * cos(37.77 deg) ~= 87,700 m. 0.001 deg is approx 87.7 meters.
    # Expected area: 111m * 87.7m ~= 9734 m²
    poly_deg = Polygon([
        (-122.419, 37.774),
        (-122.418, 37.774),
        (-122.418, 37.775),
        (-122.419, 37.775),
        (-122.419, 37.774),
    ])

    proj_geom, proj_crs = project_geometry_to_metric(poly_deg, "EPSG:4326")

    assert proj_crs == "EPSG:32610"
    area_m2 = proj_geom.area
    # Area must be measured in meters squared (~9734 m²), not square degrees (0.000001 deg²)
    assert 9000 < area_m2 < 11000


def test_project_linestring_metric_accuracy():
    # 0.01 deg line along latitude (~37.77 N)
    # Expected length: ~877 meters
    line_deg = LineString([(-122.420, 37.775), (-122.410, 37.775)])

    proj_geom, proj_crs = project_geometry_to_metric(line_deg, "EPSG:4326")

    assert proj_crs == "EPSG:32610"
    length_m = proj_geom.length
    assert 800 < length_m < 950
