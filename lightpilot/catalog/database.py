"""SQLite catalog database for managing imported photos."""

import sqlite3
from pathlib import Path
from typing import Optional


class CatalogDB:
    """SQLite-backed photo catalog."""

    def __init__(self, db_path: str | Path):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(str(self.db_path))
        self._conn.row_factory = sqlite3.Row
        self._create_tables()

    def _create_tables(self):
        self._conn.executescript("""
            CREATE TABLE IF NOT EXISTS photos (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                file_path TEXT UNIQUE NOT NULL,
                file_name TEXT NOT NULL,
                folder TEXT NOT NULL,
                file_size INTEGER DEFAULT 0,
                width INTEGER DEFAULT 0,
                height INTEGER DEFAULT 0,
                rating INTEGER DEFAULT 0,
                color_label TEXT DEFAULT '',
                import_time TEXT DEFAULT (datetime('now')),
                capture_time TEXT DEFAULT '',
                camera TEXT DEFAULT '',
                lens TEXT DEFAULT '',
                iso INTEGER DEFAULT 0,
                focal_length REAL DEFAULT 0,
                aperture REAL DEFAULT 0,
                shutter_speed TEXT DEFAULT '',
                has_sidecar INTEGER DEFAULT 0
            );
            CREATE INDEX IF NOT EXISTS idx_folder ON photos(folder);
            CREATE INDEX IF NOT EXISTS idx_rating ON photos(rating);
        """)
        self._conn.commit()

    def import_photo(self, file_path: str, **metadata) -> int:
        """Add a photo to the catalog. Returns the photo ID."""
        p = Path(file_path)
        try:
            size = p.stat().st_size
        except OSError:
            size = 0

        self._conn.execute(
            """INSERT OR IGNORE INTO photos (file_path, file_name, folder, file_size,
               camera, lens, iso, focal_length, aperture)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                str(p),
                p.name,
                str(p.parent),
                size,
                metadata.get("camera", ""),
                metadata.get("lens", ""),
                metadata.get("iso", 0),
                metadata.get("focal_length", 0),
                metadata.get("aperture", 0),
            ),
        )
        self._conn.commit()
        row = self._conn.execute(
            "SELECT id FROM photos WHERE file_path = ?", (str(p),)
        ).fetchone()
        return row["id"] if row else 0

    def import_folder(self, folder: str, extensions: set | None = None) -> int:
        """Import all supported images from a folder. Returns count."""
        if extensions is None:
            extensions = {
                ".arw", ".cr2", ".cr3", ".nef", ".dng", ".raf",
                ".orf", ".rw2", ".pef", ".srw",
                ".jpg", ".jpeg", ".tiff", ".tif", ".png",
            }
        count = 0
        for p in Path(folder).iterdir():
            if p.suffix.lower() in extensions and p.is_file():
                self.import_photo(str(p))
                count += 1
        return count

    def get_photos(
        self,
        folder: str | None = None,
        min_rating: int = 0,
        order_by: str = "file_name",
    ) -> list[dict]:
        """Query photos with optional filters."""
        query = "SELECT * FROM photos WHERE rating >= ?"
        params: list = [min_rating]
        if folder:
            query += " AND folder = ?"
            params.append(folder)
        query += f" ORDER BY {order_by}"

        rows = self._conn.execute(query, params).fetchall()
        return [dict(r) for r in rows]

    def set_rating(self, photo_id: int, rating: int) -> None:
        self._conn.execute(
            "UPDATE photos SET rating = ? WHERE id = ?", (rating, photo_id)
        )
        self._conn.commit()

    def get_folders(self) -> list[str]:
        """Get distinct folders that contain imported photos."""
        rows = self._conn.execute(
            "SELECT DISTINCT folder FROM photos ORDER BY folder"
        ).fetchall()
        return [r["folder"] for r in rows]

    def close(self):
        self._conn.close()
