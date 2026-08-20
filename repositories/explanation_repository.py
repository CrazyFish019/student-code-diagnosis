"""SQLite persistence for explanation results."""

import sqlite3

from models.history import ExplanationRecord


class ExplanationRepository:
    def __init__(self, connection: sqlite3.Connection) -> None:
        self.connection = connection

    def save_explanation(self, record: ExplanationRecord) -> None:
        self.connection.execute(
            """INSERT INTO explanations(
                submission_id,status,teacher_explanation,student_explanation,
                confidence_note,error_message
            ) VALUES(?,?,?,?,?,?)
            ON CONFLICT(submission_id) DO UPDATE SET
                status=excluded.status,
                teacher_explanation=excluded.teacher_explanation,
                student_explanation=excluded.student_explanation,
                confidence_note=excluded.confidence_note,
                error_message=excluded.error_message""",
            (
                record.submission_id,
                record.status,
                record.teacher_explanation,
                record.student_explanation,
                record.confidence_note,
                record.error_message,
            ),
        )

    def get_explanation(self, submission_id: str) -> ExplanationRecord | None:
        row = self.connection.execute(
            "SELECT * FROM explanations WHERE submission_id = ?", (submission_id,)
        ).fetchone()
        if row is None:
            return None
        return ExplanationRecord(
            id=row["id"],
            submission_id=row["submission_id"],
            status=row["status"],
            teacher_explanation=row["teacher_explanation"],
            student_explanation=row["student_explanation"],
            confidence_note=row["confidence_note"],
            error_message=row["error_message"],
        )
