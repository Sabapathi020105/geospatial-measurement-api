"""Persistent storage layer using SQLite for file metadata, extracted features, and measurements."""

from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from app.config import settings
from app.core.exceptions import FileNotFoundCustomError


class StorageManager:
    """Manages SQLite persistence for geospatial files, features, and measurements."""

    def __init__(self, db_path: Path | str | None = None):
        self.db_path = str(db_path or settings.SQLITE_DB_PATH)
        self._init_db()

    def _get_connection(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        return conn

    def _init_db(self) -> None:
        """Create tables and indexes if they do not exist."""
        with self._get_connection() as conn:
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS files (
                    id TEXT PRIMARY KEY,
                    filename TEXT NOT NULL,
                    file_path TEXT NOT NULL,
                    file_size_bytes INTEGER,
                    feature_count INTEGER DEFAULT 0,
                    crs TEXT NOT NULL,
                    status TEXT NOT NULL,
                    geometry_breakdown TEXT DEFAULT '{}',
                    error_message TEXT,
                    created_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS features (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    file_id TEXT NOT NULL,
                    feature_id TEXT NOT NULL,
                    geometry_type TEXT NOT NULL,
                    geometry_geojson TEXT,
                    crs TEXT NOT NULL,
                    properties TEXT DEFAULT '{}',
                    FOREIGN KEY (file_id) REFERENCES files (id) ON DELETE CASCADE
                );

                CREATE TABLE IF NOT EXISTS measurements (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    file_id TEXT NOT NULL,
                    feature_id TEXT NOT NULL,
                    geometry_type TEXT NOT NULL,
                    is_supported INTEGER NOT NULL,
                    measurement_status TEXT NOT NULL,
                    area_sq_m REAL,
                    area_hectares REAL,
                    area_sq_km REAL,
                    length_m REAL,
                    length_km REAL,
                    projected_crs TEXT,
                    message TEXT,
                    FOREIGN KEY (file_id) REFERENCES files (id) ON DELETE CASCADE
                );

                CREATE INDEX IF NOT EXISTS idx_features_file_id ON features (file_id);
                CREATE INDEX IF NOT EXISTS idx_measurements_file_id ON measurements (file_id);
                """
            )

    def save_file_record(
        self,
        file_id: str,
        filename: str,
        file_path: str,
        file_size_bytes: int,
        crs: str,
        status: str = "PROCESSING",
    ) -> None:
        """Create an initial file record."""
        now = datetime.now(timezone.utc).isoformat()
        with self._get_connection() as conn:
            conn.execute(
                """
                INSERT INTO files (id, filename, file_path, file_size_bytes, crs, status, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (file_id, filename, file_path, file_size_bytes, crs, status, now),
            )

    def update_file_completed(
        self,
        file_id: str,
        feature_count: int,
        crs: str,
        geometry_breakdown: Dict[str, int],
        status: str = "COMPLETED",
    ) -> None:
        """Mark a file as completed with extracted feature statistics."""
        with self._get_connection() as conn:
            conn.execute(
                """
                UPDATE files
                SET feature_count = ?, crs = ?, status = ?, geometry_breakdown = ?
                WHERE id = ?
                """,
                (feature_count, crs, status, json.dumps(geometry_breakdown), file_id),
            )

    def update_file_failed(self, file_id: str, error_message: str) -> None:
        """Mark a file as failed with error details."""
        with self._get_connection() as conn:
            conn.execute(
                """
                UPDATE files
                SET status = 'FAILED', error_message = ?
                WHERE id = ?
                """,
                (error_message, file_id),
            )

    def get_file(self, file_id: str) -> Dict[str, Any]:
        """Fetch a single file record by ID."""
        with self._get_connection() as conn:
            cur = conn.execute("SELECT * FROM files WHERE id = ?", (file_id,))
            row = cur.fetchone()
            if not row:
                raise FileNotFoundCustomError(f"File with ID '{file_id}' not found.")
            data = dict(row)
            data["geometry_breakdown"] = json.loads(data["geometry_breakdown"] or "{}")
            return data

    def list_files(self, limit: int = 50, offset: int = 0) -> tuple[int, List[Dict[str, Any]]]:
        """Fetch list of files with total count."""
        with self._get_connection() as conn:
            total = conn.execute("SELECT COUNT(*) FROM files").fetchone()[0]
            cur = conn.execute(
                "SELECT * FROM files ORDER BY created_at DESC LIMIT ? OFFSET ?",
                (limit, offset),
            )
            rows = []
            for r in cur.fetchall():
                d = dict(r)
                d["geometry_breakdown"] = json.loads(d["geometry_breakdown"] or "{}")
                rows.append(d)
            return total, rows

    def save_features_and_measurements(
        self,
        file_id: str,
        features: List[Dict[str, Any]],
        measurements: List[Dict[str, Any]],
    ) -> None:
        """Batch insert extracted features and calculated measurements."""
        with self._get_connection() as conn:
            for feat in features:
                conn.execute(
                    """
                    INSERT INTO features (file_id, feature_id, geometry_type, geometry_geojson, crs, properties)
                    VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    (
                        file_id,
                        str(feat["feature_id"]),
                        feat["geometry_type"],
                        json.dumps(feat.get("geometry")),
                        feat["crs"],
                        json.dumps(feat.get("properties", {})),
                    ),
                )
            for m in measurements:
                conn.execute(
                    """
                    INSERT INTO measurements (
                        file_id, feature_id, geometry_type, is_supported, measurement_status,
                        area_sq_m, area_hectares, area_sq_km, length_m, length_km,
                        projected_crs, message
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        file_id,
                        str(m["feature_id"]),
                        m["geometry_type"],
                        1 if m["is_supported"] else 0,
                        m["measurement_status"],
                        m.get("area_sq_m"),
                        m.get("area_hectares"),
                        m.get("area_sq_km"),
                        m.get("length_m"),
                        m.get("length_km"),
                        m.get("projected_crs"),
                        m.get("message"),
                    ),
                )

    def get_features(self, file_id: str) -> List[Dict[str, Any]]:
        """Retrieve extracted features for a file."""
        # Verify file exists
        self.get_file(file_id)
        with self._get_connection() as conn:
            cur = conn.execute("SELECT * FROM features WHERE file_id = ? ORDER BY id ASC", (file_id,))
            features = []
            for row in cur.fetchall():
                features.append(
                    {
                        "feature_id": row["feature_id"],
                        "geometry_type": row["geometry_type"],
                        "geometry": json.loads(row["geometry_geojson"]) if row["geometry_geojson"] else None,
                        "crs": row["crs"],
                        "properties": json.loads(row["properties"] or "{}"),
                    }
                )
            return features

    def get_measurements(self, file_id: str) -> List[Dict[str, Any]]:
        """Retrieve measurements for a file."""
        # Verify file exists
        self.get_file(file_id)
        with self._get_connection() as conn:
            cur = conn.execute(
                """
                SELECT m.*, f.properties
                FROM measurements m
                LEFT JOIN features f ON m.file_id = f.file_id AND m.feature_id = f.feature_id
                WHERE m.file_id = ?
                ORDER BY m.id ASC
                """,
                (file_id,),
            )
            measurements = []
            for row in cur.fetchall():
                measurements.append(
                    {
                        "feature_id": row["feature_id"],
                        "geometry_type": row["geometry_type"],
                        "properties": json.loads(row["properties"] or "{}") if row["properties"] else {},
                        "is_supported": bool(row["is_supported"]),
                        "measurement_status": row["measurement_status"],
                        "area_sq_m": row["area_sq_m"],
                        "area_hectares": row["area_hectares"],
                        "area_sq_km": row["area_sq_km"],
                        "length_m": row["length_m"],
                        "length_km": row["length_km"],
                        "projected_crs": row["projected_crs"],
                        "message": row["message"],
                    }
                )
            return measurements

    def delete_file(self, file_id: str) -> None:
        """Delete file record and associated features/measurements."""
        with self._get_connection() as conn:
            conn.execute("DELETE FROM files WHERE id = ?", (file_id,))


storage = StorageManager()
