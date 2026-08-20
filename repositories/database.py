"""SQLite connection and schema management for local history."""

from __future__ import annotations

from contextlib import contextmanager
import os
from pathlib import Path
import sqlite3
from typing import Iterator

from core.config import DATA_DIR

_SCHEMA_VERSION = 1

_SCHEMA = """
CREATE TABLE IF NOT EXISTS tasks (
    id TEXT PRIMARY KEY,
    title TEXT NOT NULL,
    problem_id TEXT NOT NULL,
    created_at TEXT NOT NULL,
    student_count INTEGER NOT NULL CHECK (student_count >= 0)
);

CREATE TABLE IF NOT EXISTS submissions (
    id TEXT PRIMARY KEY,
    task_id TEXT NOT NULL REFERENCES tasks(id) ON DELETE CASCADE,
    student_name TEXT NOT NULL,
    status TEXT NOT NULL,
    passed_count INTEGER NOT NULL CHECK (passed_count >= 0),
    total_count INTEGER NOT NULL CHECK (total_count >= 0),
    source_file_path TEXT NOT NULL,
    result_file_path TEXT NOT NULL,
    error_message TEXT
);
CREATE INDEX IF NOT EXISTS idx_submissions_task_id ON submissions(task_id);

CREATE TABLE IF NOT EXISTS diagnoses (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    submission_id TEXT NOT NULL UNIQUE REFERENCES submissions(id) ON DELETE CASCADE,
    category TEXT,
    summary TEXT NOT NULL,
    detail TEXT NOT NULL,
    confidence REAL NOT NULL CHECK (confidence >= 0 AND confidence <= 1),
    evidence_json TEXT NOT NULL,
    related_lines_json TEXT NOT NULL,
    secondary_evidence_json TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS explanations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    submission_id TEXT NOT NULL UNIQUE REFERENCES submissions(id) ON DELETE CASCADE,
    status TEXT NOT NULL,
    teacher_explanation TEXT,
    student_explanation TEXT,
    confidence_note TEXT,
    error_message TEXT
);
"""


def default_data_directory() -> Path:
    override = os.environ.get("STUDENT_CODE_DIAGNOSIS_DATA_DIR")
    return Path(override).resolve() if override else DATA_DIR


class SQLiteDatabase:
    def __init__(self, path: str | Path | None = None) -> None:
        self.path = (
            Path(path).resolve()
            if path is not None
            else default_data_directory() / "diagnosis.db"
        )
        self.tasks_root = self.path.parent / "tasks"

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.path, timeout=10)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        return connection

    def initialize(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.tasks_root.mkdir(parents=True, exist_ok=True)
        with self.transaction() as connection:
            connection.executescript(_SCHEMA)
            connection.execute(f"PRAGMA user_version = {_SCHEMA_VERSION}")

    @contextmanager
    def transaction(self) -> Iterator[sqlite3.Connection]:
        connection = self._connect()
        try:
            yield connection
            connection.commit()
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()

    @contextmanager
    def read_connection(self) -> Iterator[sqlite3.Connection]:
        connection = self._connect()
        try:
            yield connection
        finally:
            connection.close()
