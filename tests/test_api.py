import pytest
from fastapi.testclient import TestClient


def test_health_check(client: TestClient):
    response = client.get("/api/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert "geospatial_engine" in data


def test_upload_and_measure_kml_polygons(client: TestClient, sample_kml_polygon_path):
    with open(sample_kml_polygon_path, "rb") as f:
        response = client.post("/api/files/", files={"file": ("sample_polygons.kml", f, "application/vnd.google-earth.kml+xml")})

    assert response.status_code == 201
    file_info = response.json()
    file_id = file_info["id"]
    assert file_info["filename"] == "sample_polygons.kml"
    assert file_info["feature_count"] == 2
    assert file_info["crs"] == "EPSG:4326"
    assert file_info["status"] == "COMPLETED"

    # Test GET /api/files/{id}/
    info_resp = client.get(f"/api/files/{file_id}/")
    assert info_resp.status_code == 200
    info_data = info_resp.json()
    assert info_data["id"] == file_id
    assert info_data["feature_count"] == 2
    assert info_data["status"] == "COMPLETED"

    # Test GET /api/files/{id}/measurements/
    meas_resp = client.get(f"/api/files/{file_id}/measurements/")
    assert meas_resp.status_code == 200
    meas_data = meas_resp.json()

    assert meas_data["file_id"] == file_id
    assert meas_data["summary"]["polygon_count"] == 2
    assert meas_data["summary"]["total_area_sq_m"] > 0
    assert meas_data["summary"]["total_area_hectares"] > 0

    features = meas_data["features"]
    assert len(features) == 2
    f1 = features[0]
    assert f1["feature_id"] == "parcel_01"
    assert f1["geometry_type"] == "Polygon"
    assert f1["is_supported"] is True
    assert f1["measurement_status"] == "CALCULATED"
    assert f1["area_sq_m"] > 0
    assert f1["projected_crs"] == "EPSG:32610"
    assert f1["properties"]["zone"] == "Commercial-A"


def test_upload_and_measure_shapefile_parcels(client: TestClient, sample_shp_parcels_path):
    with open(sample_shp_parcels_path, "rb") as f:
        response = client.post("/api/files/", files={"file": ("sample_parcels_shp.zip", f, "application/zip")})

    assert response.status_code == 201
    file_info = response.json()
    file_id = file_info["id"]
    assert file_info["feature_count"] == 2
    assert file_info["status"] == "COMPLETED"

    meas_resp = client.get(f"/api/files/{file_id}/measurements/")
    assert meas_resp.status_code == 200
    meas_data = meas_resp.json()
    assert meas_data["summary"]["polygon_count"] == 2
    assert meas_data["summary"]["total_area_sq_m"] > 0


def test_upload_and_measure_shapefile_roads(client: TestClient, sample_shp_roads_path):
    with open(sample_shp_roads_path, "rb") as f:
        response = client.post("/api/files/", files={"file": ("sample_roads_shp.zip", f, "application/zip")})

    assert response.status_code == 201
    file_id = response.json()["id"]

    meas_resp = client.get(f"/api/files/{file_id}/measurements/")
    assert meas_resp.status_code == 200
    meas_data = meas_resp.json()
    assert meas_data["summary"]["linestring_count"] == 2
    assert meas_data["summary"]["total_length_m"] > 0
    assert meas_data["summary"]["total_length_km"] > 0

    feat1 = meas_data["features"][0]
    assert feat1["geometry_type"] == "LineString"
    assert feat1["is_supported"] is True
    assert feat1["length_m"] > 0


def test_upload_points_graceful_handling(client: TestClient, sample_kml_points_path):
    with open(sample_kml_points_path, "rb") as f:
        response = client.post("/api/files/", files={"file": ("sample_points.kml", f, "application/vnd.google-earth.kml+xml")})

    assert response.status_code == 201
    file_id = response.json()["id"]

    meas_resp = client.get(f"/api/files/{file_id}/measurements/")
    assert meas_resp.status_code == 200
    meas_data = meas_resp.json()
    assert meas_data["summary"]["point_count"] == 2

    for feat in meas_data["features"]:
        assert feat["geometry_type"] == "Point"
        assert feat["is_supported"] is False
        assert feat["measurement_status"] == "NOT_APPLICABLE"
        assert feat["area_sq_m"] is None
        assert feat["length_m"] is None


def test_upload_invalid_extension(client: TestClient, tmp_path):
    bad_txt = tmp_path / "notes.txt"
    bad_txt.write_text("just text")

    with open(bad_txt, "rb") as f:
        response = client.post("/api/files/", files={"file": ("notes.txt", f, "text/plain")})

    assert response.status_code == 400
    assert "Unsupported file format" in response.json()["detail"]


def test_upload_zip_without_shp(client: TestClient, sample_invalid_zip_path):
    with open(sample_invalid_zip_path, "rb") as f:
        response = client.post("/api/files/", files={"file": ("invalid.zip", f, "application/zip")})

    assert response.status_code == 422
    assert "does not contain a .shp file" in response.json()["detail"]


def test_get_nonexistent_file(client: TestClient):
    response = client.get("/api/files/nonexistent_id/")
    assert response.status_code == 404


def test_list_and_delete_file(client: TestClient, sample_kml_polygon_path):
    with open(sample_kml_polygon_path, "rb") as f:
        resp = client.post("/api/files/", files={"file": ("to_delete.kml", f, "application/vnd.google-earth.kml+xml")})
    file_id = resp.json()["id"]

    # List files
    list_resp = client.get("/api/files/")
    assert list_resp.status_code == 200
    list_data = list_resp.json()
    assert list_data["total"] >= 1
    assert any(item["id"] == file_id for item in list_data["files"])

    # Delete
    del_resp = client.delete(f"/api/files/{file_id}/")
    assert del_resp.status_code == 204

    # Subsequent GET should return 404
    get_resp = client.get(f"/api/files/{file_id}/")
    assert get_resp.status_code == 404


def test_root_endpoint(client: TestClient):
    response = client.get("/")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "online"
    assert "endpoints" in data


def test_get_file_features_endpoint(client: TestClient, sample_kml_polygon_path):
    with open(sample_kml_polygon_path, "rb") as f:
        resp = client.post("/api/files/", files={"file": ("features_test.kml", f, "application/vnd.google-earth.kml+xml")})
    file_id = resp.json()["id"]

    feat_resp = client.get(f"/api/files/{file_id}/features/")
    assert feat_resp.status_code == 200
    data = feat_resp.json()
    assert data["file_id"] == file_id
    assert data["total_features"] == 2
    assert len(data["features"]) == 2
    f1 = data["features"][0]
    assert "geometry" in f1
    assert f1["geometry"]["type"] == "Polygon"
    assert "coordinates" in f1["geometry"]


def test_nonexistent_features_and_measurements(client: TestClient):
    assert client.get("/api/files/missing/features/").status_code == 404
    assert client.get("/api/files/missing/measurements/").status_code == 404
    assert client.delete("/api/files/missing/").status_code == 404
