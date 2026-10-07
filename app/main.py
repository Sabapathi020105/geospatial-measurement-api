"""FastAPI Application Entry Point."""

from __future__ import annotations

import logging
from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api.v1.router import api_router
from app.config import settings
from app.core.exceptions import (
    CorruptedFileError,
    FileNotFoundCustomError,
    GeospatialError,
    InvalidFileFormatError,
    MissingShapefileComponentsError,
)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("geospatial_api")

app = FastAPI(
    title=settings.PROJECT_NAME,
    version=settings.VERSION,
    description=(
        "Production-ready Geospatial File Measurement API built with FastAPI. "
        "Accepts zipped ESRI Shapefiles (.zip) and Keyhole Markup Language (.kml) files, "
        "extracts geographic features, properly projects coordinates to metric coordinate systems (UTM/UPS) "
        "to prevent degree-distortion, and calculates precise geometric measurements (Area for Polygons, Length for LineStrings)."
    ),
    docs_url="/docs",
    redoc_url="/redoc",
)

# CORS middleware for cross-origin access
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Exception handlers
@app.exception_handler(FileNotFoundCustomError)
async def handle_not_found_error(request: Request, exc: FileNotFoundCustomError):
    return JSONResponse(
        status_code=status.HTTP_404_NOT_FOUND,
        content={"detail": exc.message, "type": "FileNotFoundError"},
    )


@app.exception_handler(InvalidFileFormatError)
async def handle_invalid_format_error(request: Request, exc: InvalidFileFormatError):
    return JSONResponse(
        status_code=status.HTTP_400_BAD_REQUEST,
        content={"detail": exc.message, "type": "InvalidFileFormatError"},
    )


@app.exception_handler(CorruptedFileError)
async def handle_corrupted_file_error(request: Request, exc: CorruptedFileError):
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={"detail": exc.message, "type": "CorruptedFileError"},
    )


@app.exception_handler(MissingShapefileComponentsError)
async def handle_missing_shp_error(request: Request, exc: MissingShapefileComponentsError):
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={"detail": exc.message, "type": "MissingShapefileComponentsError"},
    )


@app.exception_handler(GeospatialError)
async def handle_geospatial_error(request: Request, exc: GeospatialError):
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={"detail": exc.message, "type": "GeospatialProcessingError"},
    )


# Include API routers
app.include_router(api_router, prefix=settings.API_V1_PREFIX)


@app.get("/", summary="Root API Index", tags=["Health"])
def root():
    return {
        "service": settings.PROJECT_NAME,
        "version": settings.VERSION,
        "status": "online",
        "docs_url": "/docs",
        "redoc_url": "/redoc",
        "endpoints": {
            "upload_file": "POST /api/files/",
            "list_files": "GET /api/files/",
            "file_info": "GET /api/files/{id}/",
            "file_measurements": "GET /api/files/{id}/measurements/",
            "file_features": "GET /api/files/{id}/features/",
            "health": "GET /api/health",
        },
    }
