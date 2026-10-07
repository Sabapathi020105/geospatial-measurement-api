import pytest
from app.services.kml_parser import parse_kml_file
from app.core.exceptions import CorruptedFileError


def test_parse_kml_polygons(sample_kml_polygon_path):
    features = parse_kml_file(sample_kml_polygon_path)
    assert len(features) == 2

    feat1 = features[0]
    assert feat1["feature_id"] == "parcel_01"
    assert feat1["geometry_type"] == "Polygon"
    assert feat1["crs"] == "EPSG:4326"
    assert feat1["properties"]["name"] == "North Quad"
    assert feat1["properties"]["zone"] == "Commercial-A"
    assert feat1["geometry"].is_valid


def test_parse_kml_linestrings(sample_kml_linestring_path):
    features = parse_kml_file(sample_kml_linestring_path)
    assert len(features) == 2

    feat1 = features[0]
    assert feat1["geometry_type"] == "LineString"
    assert feat1["properties"]["name"] == "Market Street Main Corridor"
    assert feat1["properties"]["route_type"] == "Bus"


def test_parse_kml_points(sample_kml_points_path):
    features = parse_kml_file(sample_kml_points_path)
    assert len(features) == 2

    assert features[0]["geometry_type"] == "Point"
    assert features[0]["properties"]["name"] == "Station Alpha"


def test_parse_kml_mixed(sample_kml_mixed_path):
    features = parse_kml_file(sample_kml_mixed_path)
    assert len(features) == 3

    geom_types = {f["geometry_type"] for f in features}
    assert "Polygon" in geom_types
    assert "LineString" in geom_types
    assert "Point" in geom_types


def test_parse_invalid_xml(tmp_path):
    bad_file = tmp_path / "broken.kml"
    bad_file.write_text("This is not valid XML <broken")

    with pytest.raises(CorruptedFileError):
        parse_kml_file(bad_file)


def test_parse_kml_polygon_with_hole(tmp_path):
    hole_kml = tmp_path / "hole.kml"
    hole_kml.write_text("""<?xml version="1.0" encoding="UTF-8"?>
<kml xmlns="http://www.opengis.net/kml/2.2">
  <Document>
    <Placemark id="donut_poly">
      <Polygon>
        <outerBoundaryIs>
          <LinearRing>
            <coordinates>
              0,0,0 10,0,0 10,10,0 0,10,0 0,0,0
            </coordinates>
          </LinearRing>
        </outerBoundaryIs>
        <innerBoundaryIs>
          <LinearRing>
            <coordinates>
              2,2,0 8,2,0 8,8,0 2,8,0 2,2,0
            </coordinates>
          </LinearRing>
        </innerBoundaryIs>
      </Polygon>
    </Placemark>
  </Document>
</kml>
""")
    features = parse_kml_file(hole_kml)
    assert len(features) == 1
    assert features[0]["geometry_type"] == "Polygon"
    geom = features[0]["geometry"]
    assert len(geom.interiors) == 1
