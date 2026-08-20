from datetime import datetime, timezone

from models.history import (
    DiagnosisRecord,
    HistoricalStudent,
    HistoricalTask,
    SubmissionRecord,
    TaskRecord,
)
from ui.history_presenters import build_history_student_rows, build_history_task_rows


def test_empty_history_rows() -> None:
    assert build_history_task_rows(()) == []


def test_history_rows_preserve_task_and_student_facts() -> None:
    task = TaskRecord(
        "task-1", "A+B", "problem-1", datetime.now(timezone.utc), 1
    )
    submission = SubmissionRecord(
        "submission-1",
        "task-1",
        "张三",
        "WA",
        8,
        10,
        "tasks/task-1/students/a.cpp",
        "tasks/task-1/results/a.json",
    )
    diagnosis = DiagnosisRecord(
        None, submission.id, "boundary_error", "边界", "详情", 0.8, (), (), ()
    )
    historical = HistoricalTask(
        task, (HistoricalStudent(submission, diagnosis, None, {"status": "WA"}),)
    )

    assert build_history_task_rows((task,))[0]["任务名称"] == "A+B"
    assert build_history_student_rows(historical)[0] == {
        "学生": "张三",
        "状态": "WA",
        "通过": "8/10",
        "诊断": "边界问题",
    }
