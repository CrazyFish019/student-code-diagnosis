"""Pure conversion of persisted history records into view-friendly rows."""

from __future__ import annotations

from models.history import HistoricalTask, TaskRecord
from ui.presenters import diagnosis_label


def build_history_task_rows(tasks: tuple[TaskRecord, ...]) -> list[dict[str, object]]:
    return [
        {
            "任务名称": task.title,
            "题目 ID": task.problem_id,
            "创建时间": task.created_at.astimezone().strftime("%Y-%m-%d %H:%M:%S"),
            "学生数": task.student_count,
        }
        for task in tasks
    ]


def build_history_student_rows(task: HistoricalTask) -> list[dict[str, object]]:
    return [
        {
            "学生": student.submission.student_name,
            "状态": student.submission.status,
            "通过": (
                f"{student.submission.passed_count}/{student.submission.total_count}"
            ),
            "诊断": diagnosis_label(
                student.diagnosis.category if student.diagnosis else None
            ),
        }
        for student in task.students
    ]
