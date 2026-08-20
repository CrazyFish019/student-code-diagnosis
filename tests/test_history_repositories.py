from datetime import datetime, timezone

from models.history import (
    DiagnosisRecord,
    ExplanationRecord,
    SubmissionRecord,
    TaskRecord,
)
from repositories import (
    DiagnosisRepository,
    ExplanationRepository,
    SQLiteDatabase,
    SubmissionRepository,
    TaskRepository,
)


def make_task(task_id: str = "task-1") -> TaskRecord:
    return TaskRecord(task_id, "A+B 诊断", "problem-1", datetime.now(timezone.utc), 1)


def make_submission(submission_id: str = "submission-1") -> SubmissionRecord:
    return SubmissionRecord(
        submission_id,
        "task-1",
        "张三",
        "WA",
        1,
        2,
        "tasks/task-1/students/张三.cpp",
        "tasks/task-1/results/张三.json",
    )


def test_database_initialization_creates_all_tables(tmp_path) -> None:
    database = SQLiteDatabase(tmp_path / "history" / "diagnosis.db")
    database.initialize()

    with database.read_connection() as connection:
        tables = {
            row["name"]
            for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            )
        }

    assert database.path.is_file()
    assert {"tasks", "submissions", "diagnoses", "explanations"} <= tables


def test_task_repository_crud(tmp_path) -> None:
    database = SQLiteDatabase(tmp_path / "diagnosis.db")
    database.initialize()
    task = make_task()

    with database.transaction() as connection:
        repository = TaskRepository(connection)
        repository.create_task(task)
        assert repository.get_task(task.id) == task
        assert repository.list_tasks() == (task,)
        assert repository.update_title(task.id, "更新后的任务")
        assert repository.get_task(task.id).title == "更新后的任务"
        assert repository.delete_task(task.id)
        assert repository.get_task(task.id) is None


def test_submission_repository_crud(tmp_path) -> None:
    database = SQLiteDatabase(tmp_path / "diagnosis.db")
    database.initialize()
    submission = make_submission()

    with database.transaction() as connection:
        TaskRepository(connection).create_task(make_task())
        repository = SubmissionRepository(connection)
        repository.save_submission(submission)
        assert repository.get_submission(submission.id) == submission
        assert repository.list_submissions("task-1") == (submission,)
        assert repository.delete_submission(submission.id)
        assert repository.get_submission(submission.id) is None


def test_diagnosis_repository_round_trip_and_update(tmp_path) -> None:
    database = SQLiteDatabase(tmp_path / "diagnosis.db")
    database.initialize()
    record = DiagnosisRecord(
        None,
        "submission-1",
        "boundary_error",
        "边界问题",
        "最大数据失败",
        0.8,
        ("小数据通过", "最大数据失败"),
        (8,),
        ("存在边界比较",),
    )

    with database.transaction() as connection:
        TaskRepository(connection).create_task(make_task())
        SubmissionRepository(connection).save_submission(make_submission())
        repository = DiagnosisRepository(connection)
        repository.save_diagnosis(record)
        loaded = repository.get_diagnosis("submission-1")
        assert loaded is not None
        assert loaded.category == "boundary_error"
        assert loaded.evidence == record.evidence
        repository.save_diagnosis(
            DiagnosisRecord(
                None,
                "submission-1",
                "output_format_error",
                "格式问题",
                "空格不一致",
                0.9,
                ("Token 一致",),
                (),
                (),
            )
        )
        assert repository.get_diagnosis("submission-1").category == "output_format_error"


def test_explanation_repository_round_trip(tmp_path) -> None:
    database = SQLiteDatabase(tmp_path / "diagnosis.db")
    database.initialize()
    record = ExplanationRecord(
        None,
        "submission-1",
        "SUCCESS",
        "请检查边界条件。",
        "检查最小和最大输入。",
        "基于规则证据。",
    )

    with database.transaction() as connection:
        TaskRepository(connection).create_task(make_task())
        SubmissionRepository(connection).save_submission(make_submission())
        repository = ExplanationRepository(connection)
        repository.save_explanation(record)
        loaded = repository.get_explanation("submission-1")

    assert loaded is not None
    assert loaded.teacher_explanation == "请检查边界条件。"


def test_foreign_key_cascade_removes_child_records(tmp_path) -> None:
    database = SQLiteDatabase(tmp_path / "diagnosis.db")
    database.initialize()
    with database.transaction() as connection:
        TaskRepository(connection).create_task(make_task())
        SubmissionRepository(connection).save_submission(make_submission())
        DiagnosisRepository(connection).save_diagnosis(
            DiagnosisRecord(None, "submission-1", None, "", "", 0, (), (), ())
        )
        TaskRepository(connection).delete_task("task-1")
        assert SubmissionRepository(connection).get_submission("submission-1") is None
        assert DiagnosisRepository(connection).get_diagnosis("submission-1") is None
