from fastapi import APIRouter

from app.api.v1.endpoints import files, health, measurements

api_router = APIRouter()

api_router.include_router(health.router)
api_router.include_router(files.router)
api_router.include_router(measurements.router)
