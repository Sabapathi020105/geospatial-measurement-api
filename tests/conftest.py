import os
import sys
from pathlib import Path
import pytest
from fastapi.testclient import TestClient

# Ensure root directory is in sys.path
BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

from app.main import app
from app.db.storage import StorageManager, storage

SAMPLE_DIR = BASE_DIR / "sample_data"


@pytest.fixture(scope="session")
def client():
    """FastAPI TestClient fixture."""
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture
def sample_kml_polygon_path():
    return SAMPLE_DIR / "sample_polygons.kml"


@pytest.fixture
def sample_kml_linestring_path():
    return SAMPLE_DIR / "sample_linestrings.kml"


@pytest.fixture
def sample_kml_points_path():
    return SAMPLE_DIR / "sample_points.kml"


@pytest.fixture
def sample_kml_mixed_path():
    return SAMPLE_DIR / "sample_mixed.kml"


@pytest.fixture
def sample_shp_parcels_path():
    return SAMPLE_DIR / "sample_parcels_shp.zip"


@pytest.fixture
def sample_shp_roads_path():
    return SAMPLE_DIR / "sample_roads_shp.zip"


@pytest.fixture
def sample_invalid_zip_path():
    return SAMPLE_DIR / "sample_invalid_no_shp.zip"
