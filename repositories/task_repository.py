"""SQLite persistence for task records."""

from datetime import datetime
import sqlite3

from models.history import TaskRecord


class TaskRepository:
    def __init__(self, connection: sqlite3.Connection) -> None:
        self.connection = connection

    def create_task(self, task: TaskRecord) -> None:
        self.connection.execute(
            "INSERT INTO tasks(id,title,problem_id,created_at,student_count) VALUES(?,?,?,?,?)",
            (
                task.id,
                task.title,
                task.problem_id,
                task.created_at.isoformat(),
                task.student_count,
            ),
        )

    def get_task(self, task_id: str) -> TaskRecord | None:
        row = self.connection.execute(
            "SELECT * FROM tasks WHERE id = ?", (task_id,)
        ).fetchone()
        return None if row is None else self._record(row)

    def list_tasks(self) -> tuple[TaskRecord, ...]:
        rows = self.connection.execute(
            "SELECT * FROM tasks ORDER BY created_at DESC, id DESC"
        ).fetchall()
        return tuple(self._record(row) for row in rows)

    def update_title(self, task_id: str, title: str) -> bool:
        cursor = self.connection.execute(
            "UPDATE tasks SET title = ? WHERE id = ?", (title, task_id)
        )
        return cursor.rowcount > 0

    def delete_task(self, task_id: str) -> bool:
        cursor = self.connection.execute("DELETE FROM tasks WHERE id = ?", (task_id,))
        return cursor.rowcount > 0

    @staticmethod
    def _record(row: sqlite3.Row) -> TaskRecord:
        return TaskRecord(
            id=row["id"],
            title=row["title"],
            problem_id=row["problem_id"],
            created_at=datetime.fromisoformat(row["created_at"]),
            student_count=row["student_count"],
        )
