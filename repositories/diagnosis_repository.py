"""SQLite persistence for rule diagnosis records."""

import json
import sqlite3

from models.history import DiagnosisRecord


class DiagnosisRepository:
    def __init__(self, connection: sqlite3.Connection) -> None:
        self.connection = connection

    def save_diagnosis(self, record: DiagnosisRecord) -> None:
        self.connection.execute(
            """INSERT INTO diagnoses(
                submission_id,category,summary,detail,confidence,evidence_json,
                related_lines_json,secondary_evidence_json
            ) VALUES(?,?,?,?,?,?,?,?)
            ON CONFLICT(submission_id) DO UPDATE SET
                category=excluded.category, summary=excluded.summary,
                detail=excluded.detail, confidence=excluded.confidence,
                evidence_json=excluded.evidence_json,
                related_lines_json=excluded.related_lines_json,
                secondary_evidence_json=excluded.secondary_evidence_json""",
            (
                record.submission_id,
                record.category,
                record.summary,
                record.detail,
                record.confidence,
                json.dumps(record.evidence, ensure_ascii=False),
                json.dumps(record.related_lines),
                json.dumps(record.secondary_evidence, ensure_ascii=False),
            ),
        )

    def get_diagnosis(self, submission_id: str) -> DiagnosisRecord | None:
        row = self.connection.execute(
            "SELECT * FROM diagnoses WHERE submission_id = ?", (submission_id,)
        ).fetchone()
        if row is None:
            return None
        return DiagnosisRecord(
            id=row["id"],
            submission_id=row["submission_id"],
            category=row["category"],
            summary=row["summary"],
            detail=row["detail"],
            confidence=row["confidence"],
            evidence=tuple(json.loads(row["evidence_json"])),
            related_lines=tuple(json.loads(row["related_lines_json"])),
            secondary_evidence=tuple(json.loads(row["secondary_evidence_json"])),
        )
