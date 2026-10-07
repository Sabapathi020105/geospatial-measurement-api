"""Health check endpoint."""

from __future__ import annotations

import sys
from fastapi import APIRouter
from pyproj import __version__ as pyproj_version
from shapely import __version__ as shapely_version

from app.config import settings

router = APIRouter(tags=["Health"])


@router.get("/health", summary="Health check")
def health_check():
    """Returns application health and geospatial library versions."""
    return {
        "status": "healthy",
        "app": settings.PROJECT_NAME,
        "version": settings.VERSION,
        "python": sys.version,
        "geospatial_engine": {
            "shapely": shapely_version,
            "pyproj": pyproj_version,
        },
    }
