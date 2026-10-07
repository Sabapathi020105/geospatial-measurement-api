import pytest
from shapely.geometry import MultiPolygon, MultiLineString, GeometryCollection, Polygon, LineString, Point
from app.services.measurement_service import (
    process_feature_measurement,
    calculate_measurements_for_features,
)
from app.schemas.measurement import MeasurementStatus


def test_multipolygon_area_calculation():
    p1 = Polygon([(0.0, 0.0), (0.001, 0.0), (0.001, 0.001), (0.0, 0.001), (0.0, 0.0)])
    p2 = Polygon([(0.002, 0.0), (0.003, 0.0), (0.003, 0.001), (0.002, 0.001), (0.002, 0.0)])
    mp = MultiPolygon([p1, p2])

    detail = process_feature_measurement(
        feature_id="mp_1",
        geom=mp,
        geom_type="MultiPolygon",
        source_crs="EPSG:4326",
        properties={"category": "islands"},
    )

    assert detail.is_supported is True
    assert detail.measurement_status == MeasurementStatus.CALCULATED
    assert detail.area_sq_m is not None
    assert detail.area_sq_m > 0
    assert detail.area_hectares is not None
    assert detail.area_sq_km is not None


def test_multilinestring_length_calculation():
    l1 = LineString([(0.0, 0.0), (0.001, 0.0)])
    l2 = LineString([(0.002, 0.0), (0.003, 0.0)])
    mls = MultiLineString([l1, l2])

    detail = process_feature_measurement(
        feature_id="mls_1",
        geom=mls,
        geom_type="MultiLineString",
        source_crs="EPSG:4326",
        properties={"type": "segmented_tracks"},
    )

    assert detail.is_supported is True
    assert detail.measurement_status == MeasurementStatus.CALCULATED
    assert detail.length_m is not None
    assert detail.length_m > 0
    assert detail.length_km is not None


def test_geometry_collection_unsupported_graceful():
    p = Point(10.0, 20.0)
    poly = Polygon([(10.0, 20.0), (10.01, 20.0), (10.01, 20.01), (10.0, 20.01), (10.0, 20.0)])
    gc = GeometryCollection([p, poly])

    detail = process_feature_measurement(
        feature_id="gc_1",
        geom=gc,
        geom_type="GeometryCollection",
        source_crs="EPSG:4326",
        properties={"note": "mixed collection"},
    )

    assert detail.is_supported is False
    assert detail.measurement_status == MeasurementStatus.UNSUPPORTED_GEOMETRY
    assert detail.area_sq_m is None
    assert detail.length_m is None
    assert "not supported" in detail.message


def test_empty_geometry_graceful():
    detail = process_feature_measurement(
        feature_id="empty_1",
        geom=None,
        geom_type="None",
        source_crs="EPSG:4326",
        properties={},
    )

    assert detail.is_supported is False
    assert detail.measurement_status == MeasurementStatus.UNSUPPORTED_GEOMETRY
    assert "empty" in detail.message.lower()


def test_southern_hemisphere_projection():
    # Buenos Aires, Argentina (~ -58.38 deg lon, -34.60 deg lat)
    # UTM zone 21S -> EPSG:32721
    poly = Polygon([
        (-58.38, -34.60),
        (-58.37, -34.60),
        (-58.37, -34.59),
        (-58.38, -34.59),
        (-58.38, -34.60),
    ])

    detail = process_feature_measurement(
        feature_id="ba_poly",
        geom=poly,
        geom_type="Polygon",
        source_crs="EPSG:4326",
        properties={"city": "Buenos Aires"},
    )

    assert detail.is_supported is True
    assert detail.projected_crs == "EPSG:32721"
    assert detail.area_sq_m > 0
