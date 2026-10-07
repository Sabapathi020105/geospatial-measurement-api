"""Custom exception definitions for Geospatial File Measurement API."""


class GeospatialError(Exception):
    """Base exception for all geospatial processing errors."""
    def __init__(self, message: str, detail: str | None = None):
        super().__init__(message)
        self.message = message
        self.detail = detail or message


class FileNotFoundCustomError(GeospatialError):
    """Raised when an uploaded file ID is not found."""
    pass


class InvalidFileFormatError(GeospatialError):
    """Raised when an uploaded file format is unsupported or invalid."""
    pass


class CorruptedFileError(GeospatialError):
    """Raised when an uploaded file cannot be parsed or unpacked."""
    pass


class MissingShapefileComponentsError(GeospatialError):
    """Raised when a zip file lacks essential shapefile components (.shp)."""
    pass


class CRSProjectionError(GeospatialError):
    """Raised when CRS transformation fails."""
    pass
