"""SQLite persistence for download jobs.

SQLite is deliberately used instead of an in-memory dictionary so history and
error states survive browser refreshes and application restarts.
"""

from __future__ import annotations

import sqlite3
import threading
import time
from pathlib import Path
from typing import Any

from .models import JobRecord, JobStatus


_COLUMNS = {
    "url",
    "platform",
    "platform_name",
    "media_type",
    "quality",
    "status",
    "message",
    "updated_at",
    "finished_at",
    "progress",
    "downloaded_bytes",
    "total_bytes",
    "speed",
    "eta",
    "attempts",
    "title",
    "uploader",
    "duration",
    "result_relpath",
    "result_size",
    "error_code",
    "error_message",
}


class JobStore:
    def __init__(self, db_path: Path):
        self.db_path = db_path
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.RLock()
        self._conn = sqlite3.connect(self.db_path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        with self._lock:
            self._conn.execute("PRAGMA journal_mode=WAL")
            self._conn.execute("PRAGMA foreign_keys=ON")
            self._conn.execute("PRAGMA busy_timeout=5000")
            self._migrate()

    def _migrate(self) -> None:
        self._conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS jobs (
                id TEXT PRIMARY KEY,
                url TEXT NOT NULL,
                platform TEXT NOT NULL,
                platform_name TEXT NOT NULL,
                media_type TEXT NOT NULL,
                quality TEXT NOT NULL,
                status TEXT NOT NULL,
                message TEXT NOT NULL,
                created_at REAL NOT NULL,
                updated_at REAL NOT NULL,
                finished_at REAL,
                progress REAL NOT NULL DEFAULT 0,
                downloaded_bytes INTEGER,
                total_bytes INTEGER,
                speed REAL,
                eta INTEGER,
                attempts INTEGER NOT NULL DEFAULT 0,
                title TEXT,
                uploader TEXT,
                duration REAL,
                result_relpath TEXT,
                result_size INTEGER,
                error_code TEXT,
                error_message TEXT
            );
            CREATE INDEX IF NOT EXISTS idx_jobs_created_at ON jobs(created_at DESC);
            CREATE INDEX IF NOT EXISTS idx_jobs_status ON jobs(status);
            """
        )
        self._conn.commit()

    @staticmethod
    def _from_row(row: sqlite3.Row) -> JobRecord:
        values = dict(row)
        values["status"] = JobStatus(values["status"])
        return JobRecord(**values)

    def create(self, job: JobRecord) -> None:
        data = job.__dict__ if hasattr(job, "__dict__") else {
            field: getattr(job, field) for field in JobRecord.__dataclass_fields__
        }
        data = dict(data)
        data["status"] = job.status.value
        columns = ", ".join(data)
        placeholders = ", ".join("?" for _ in data)
        with self._lock:
            self._conn.execute(
                f"INSERT INTO jobs ({columns}) VALUES ({placeholders})",
                tuple(data.values()),
            )
            self._conn.commit()

    def get(self, job_id: str) -> JobRecord | None:
        with self._lock:
            row = self._conn.execute("SELECT * FROM jobs WHERE id = ?", (job_id,)).fetchone()
        return self._from_row(row) if row else None

    def list_recent(self, limit: int = 25) -> list[JobRecord]:
        limit = max(1, min(100, int(limit)))
        with self._lock:
            rows = self._conn.execute(
                "SELECT * FROM jobs ORDER BY created_at DESC LIMIT ?", (limit,)
            ).fetchall()
        return [self._from_row(row) for row in rows]

    def update(self, job_id: str, **fields: Any) -> JobRecord | None:
        if not fields:
            return self.get(job_id)
        invalid = set(fields) - _COLUMNS
        if invalid:
            raise ValueError(f"Campos não permitidos: {', '.join(sorted(invalid))}")
        fields.setdefault("updated_at", time.time())
        if isinstance(fields.get("status"), JobStatus):
            fields["status"] = fields["status"].value
        assignments = ", ".join(f"{name} = ?" for name in fields)
        with self._lock:
            self._conn.execute(
                f"UPDATE jobs SET {assignments} WHERE id = ?",
                (*fields.values(), job_id),
            )
            self._conn.commit()
        return self.get(job_id)

    def delete(self, job_id: str) -> bool:
        with self._lock:
            cursor = self._conn.execute("DELETE FROM jobs WHERE id = ?", (job_id,))
            self._conn.commit()
            return cursor.rowcount > 0

    def mark_active_as_interrupted(self) -> int:
        now = time.time()
        active = (
            JobStatus.QUEUED.value,
            JobStatus.DOWNLOADING.value,
            JobStatus.PROCESSING.value,
            JobStatus.RETRYING.value,
            JobStatus.CANCELLING.value,
        )
        placeholders = ",".join("?" for _ in active)
        with self._lock:
            cursor = self._conn.execute(
                f"""
                UPDATE jobs
                SET status = ?, message = ?, error_code = ?, error_message = ?,
                    updated_at = ?, finished_at = ?
                WHERE status IN ({placeholders})
                """,
                (
                    JobStatus.INTERRUPTED.value,
                    "Interrompido porque a aplicação foi encerrada.",
                    "APP_RESTARTED",
                    "O download foi interrompido por um reinício. Use Tentar novamente.",
                    now,
                    now,
                    *active,
                ),
            )
            self._conn.commit()
            return cursor.rowcount

    def old_terminal_jobs(self, older_than: float) -> list[JobRecord]:
        terminal = tuple(status.value for status in JobStatus if status.terminal)
        placeholders = ",".join("?" for _ in terminal)
        with self._lock:
            rows = self._conn.execute(
                f"SELECT * FROM jobs WHERE created_at < ? AND status IN ({placeholders})",
                (older_than, *terminal),
            ).fetchall()
        return [self._from_row(row) for row in rows]

    def close(self) -> None:
        with self._lock:
            self._conn.close()
