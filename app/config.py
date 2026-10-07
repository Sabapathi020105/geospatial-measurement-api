import os
from pathlib import Path
from pydantic import BaseModel

BASE_DIR = Path(__file__).resolve().parent.parent

class Settings(BaseModel):
    PROJECT_NAME: str = "Geospatial File Measurement API"
    VERSION: str = "1.0.0"
    API_V1_PREFIX: str = "/api"
    
    # Upload configurations
    UPLOAD_DIR: Path = BASE_DIR / "uploads"
    MAX_FILE_SIZE_MB: int = 50
    ALLOWED_EXTENSIONS: set[str] = {".zip", ".kml"}
    
    # SQLite storage path
    SQLITE_DB_PATH: Path = BASE_DIR / "storage" / "metadata.db"

settings = Settings()

# Ensure directories exist
settings.UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
settings.SQLITE_DB_PATH.parent.mkdir(parents=True, exist_ok=True)
