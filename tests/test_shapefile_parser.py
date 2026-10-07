import pytest
from app.services.shapefile_parser import parse_shapefile_zip
from app.core.exceptions import CorruptedFileError, MissingShapefileComponentsError


def test_parse_shapefile_polygons(sample_shp_parcels_path):
    features = parse_shapefile_zip(sample_shp_parcels_path)
    assert len(features) == 2

    feat1 = features[0]
    assert feat1["geometry_type"] == "Polygon"
    assert "name" in feat1["properties"]
    assert feat1["properties"]["zone"] == "R-1"
    assert feat1["geometry"].is_valid


def test_parse_shapefile_linestrings(sample_shp_roads_path):
    features = parse_shapefile_zip(sample_shp_roads_path)
    assert len(features) == 2

    feat1 = features[0]
    assert feat1["geometry_type"] == "LineString"
    assert feat1["properties"]["road_name"] == "Sunset Highway"


def test_missing_shp_in_zip(sample_invalid_zip_path):
    with pytest.raises(MissingShapefileComponentsError):
        parse_shapefile_zip(sample_invalid_zip_path)


def test_corrupted_zip(tmp_path):
    fake_zip = tmp_path / "corrupted.zip"
    fake_zip.write_bytes(b"not a real zip file header content")

    with pytest.raises(CorruptedFileError):
        parse_shapefile_zip(fake_zip)
