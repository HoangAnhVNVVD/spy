"""Local SQLite storage buffer for offline-first activity recording."""

from __future__ import annotations

import sqlite3
import threading
from contextlib import contextmanager
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Generator, List, Optional


@dataclass
class ActivityEvent:
    """An activity interval recorded by the client."""
    client_id: str
    start_time: str  # ISO-8601 string
    end_time: str    # ISO-8601 string
    duration_seconds: float
    process_name: str
    window_title: str
    category: str = "Uncategorized"
    is_idle: bool = False
    id: Optional[int] = None
    synced: bool = False
    synced_at: Optional[str] = None
    created_at: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class ActivityBuffer:
    """Thread-safe SQLite storage for buffering activity logs locally."""

    def __init__(self, db_path: str | Path):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()
        self._init_db()

    @contextmanager
    def _get_connection(self) -> Generator[sqlite3.Connection, None, None]:
        conn = sqlite3.connect(
            str(self.db_path),
            timeout=10.0,
            check_same_thread=False,
        )
        conn.row_factory = sqlite3.Row
        try:
            yield conn
        finally:
            conn.close()

    def _init_db(self) -> None:
        """Create table and indexes if not existing."""
        with self._lock, self._get_connection() as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS activity_buffer (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    client_id TEXT NOT NULL,
                    start_time TEXT NOT NULL,
                    end_time TEXT NOT NULL,
                    duration_seconds REAL NOT NULL,
                    process_name TEXT NOT NULL,
                    window_title TEXT NOT NULL,
                    category TEXT NOT NULL DEFAULT 'Uncategorized',
                    is_idle INTEGER NOT NULL DEFAULT 0,
                    synced INTEGER NOT NULL DEFAULT 0,
                    synced_at TEXT,
                    created_at TEXT NOT NULL
                );
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_activity_synced 
                ON activity_buffer (synced, id);
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_activity_time 
                ON activity_buffer (start_time);
            """)
            conn.commit()

    def insert(self, event: ActivityEvent) -> int:
        """Insert a single activity record into the local buffer."""
        now_iso = datetime.now(timezone.utc).isoformat()
        with self._lock, self._get_connection() as conn:
            cursor = conn.execute(
                """
                INSERT INTO activity_buffer (
                    client_id, start_time, end_time, duration_seconds,
                    process_name, window_title, category, is_idle,
                    synced, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, 0, ?)
                """,
                (
                    event.client_id,
                    event.start_time,
                    event.end_time,
                    float(event.duration_seconds),
                    event.process_name,
                    event.window_title,
                    event.category,
                    1 if event.is_idle else 0,
                    now_iso,
                ),
            )
            conn.commit()
            return cursor.lastrowid or 0

    def get_unsynced_batch(self, limit: int = 100) -> List[ActivityEvent]:
        """Fetch up to `limit` pending activity records that haven't synced yet."""
        with self._lock, self._get_connection() as conn:
            cursor = conn.execute(
                """
                SELECT id, client_id, start_time, end_time, duration_seconds,
                       process_name, window_title, category, is_idle, synced,
                       synced_at, created_at
                FROM activity_buffer
                WHERE synced = 0
                ORDER BY id ASC
                LIMIT ?
                """,
                (limit,),
            )
            rows = cursor.fetchall()
            results = []
            for r in rows:
                results.append(
                    ActivityEvent(
                        id=r["id"],
                        client_id=r["client_id"],
                        start_time=r["start_time"],
                        end_time=r["end_time"],
                        duration_seconds=float(r["duration_seconds"]),
                        process_name=r["process_name"],
                        window_title=r["window_title"],
                        category=r["category"],
                        is_idle=bool(r["is_idle"]),
                        synced=bool(r["synced"]),
                        synced_at=r["synced_at"],
                        created_at=r["created_at"],
                    )
                )
            return results

    def mark_synced(self, record_ids: List[int]) -> int:
        """Mark the specified records as successfully synced."""
        if not record_ids:
            return 0
        now_iso = datetime.now(timezone.utc).isoformat()
        placeholders = ",".join("?" for _ in record_ids)
        with self._lock, self._get_connection() as conn:
            cursor = conn.execute(
                f"""
                UPDATE activity_buffer
                SET synced = 1, synced_at = ?
                WHERE id IN ({placeholders})
                """,
                [now_iso] + record_ids,
            )
            conn.commit()
            return cursor.rowcount

    def get_stats(self) -> Dict[str, Any]:
        """Return diagnostic statistics about the local buffer."""
        with self._lock, self._get_connection() as conn:
            total = conn.execute("SELECT COUNT(*) FROM activity_buffer").fetchone()[0]
            unsynced = conn.execute("SELECT COUNT(*) FROM activity_buffer WHERE synced = 0").fetchone()[0]
            synced = conn.execute("SELECT COUNT(*) FROM activity_buffer WHERE synced = 1").fetchone()[0]
            oldest = conn.execute(
                "SELECT MIN(start_time) FROM activity_buffer WHERE synced = 0"
            ).fetchone()[0]
            return {
                "total_records": total,
                "unsynced_records": unsynced,
                "synced_records": synced,
                "oldest_unsynced": oldest,
                "db_path": str(self.db_path),
            }

    def prune_synced(self, keep_days: int = 14) -> int:
        """Remove old synced records older than keep_days to free disk space."""
        with self._lock, self._get_connection() as conn:
            cursor = conn.execute(
                """
                DELETE FROM activity_buffer
                WHERE synced = 1
                  AND datetime(created_at) < datetime('now', ?)
                """,
                (f"-{keep_days} days",),
            )
            conn.commit()
            return cursor.rowcount
