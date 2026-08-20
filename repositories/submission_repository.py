"""SQLite persistence for historical student submissions."""

import sqlite3

from models.history import SubmissionRecord


class SubmissionRepository:
    def __init__(self, connection: sqlite3.Connection) -> None:
        self.connection = connection

    def save_submission(self, record: SubmissionRecord) -> None:
        self.connection.execute(
            """INSERT INTO submissions(
                id,task_id,student_name,status,passed_count,total_count,
                source_file_path,result_file_path,error_message
            ) VALUES(?,?,?,?,?,?,?,?,?)""",
            (
                record.id,
                record.task_id,
                record.student_name,
                record.status,
                record.passed_count,
                record.total_count,
                record.source_file_path,
                record.result_file_path,
                record.error_message,
            ),
        )

    def get_submission(self, submission_id: str) -> SubmissionRecord | None:
        row = self.connection.execute(
            "SELECT * FROM submissions WHERE id = ?", (submission_id,)
        ).fetchone()
        return None if row is None else self._record(row)

    def list_submissions(self, task_id: str) -> tuple[SubmissionRecord, ...]:
        rows = self.connection.execute(
            "SELECT * FROM submissions WHERE task_id = ? ORDER BY rowid", (task_id,)
        ).fetchall()
        return tuple(self._record(row) for row in rows)

    def delete_submission(self, submission_id: str) -> bool:
        cursor = self.connection.execute(
            "DELETE FROM submissions WHERE id = ?", (submission_id,)
        )
        return cursor.rowcount > 0

    @staticmethod
    def _record(row: sqlite3.Row) -> SubmissionRecord:
        return SubmissionRecord(
            id=row["id"],
            task_id=row["task_id"],
            student_name=row["student_name"],
            status=row["status"],
            passed_count=row["passed_count"],
            total_count=row["total_count"],
            source_file_path=row["source_file_path"],
            result_file_path=row["result_file_path"],
            error_message=row["error_message"],
        )
