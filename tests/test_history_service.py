import json

import pytest

from models import (
    AIExplanation,
    ClassAnalysisResult,
    DiagnosisReport,
    ExplanationResult,
    ExplanationStatus,
    JudgeResult,
    JudgeStatus,
    StudentAnalysis,
    StudentSource,
    TestCaseResult as DomainTestCaseResult,
)
from repositories import SQLiteDatabase
from services.history_service import HistoryService, HistoryServiceError


def make_judge(submission_id: str, status: JudgeStatus) -> JudgeResult:
    return JudgeResult(
        submission_id=submission_id,
        problem_id="problem-1",
        final_status=status,
        testcase_results=(
            DomainTestCaseResult(
                "case-1",
                JudgeStatus.AC if status is JudgeStatus.AC else status,
                12,
                "3\n" if status is JudgeStatus.AC else "4\n",
                "",
                0,
            ),
        ),
    )


def make_analysis_result() -> tuple[ClassAnalysisResult, tuple[StudentSource, ...]]:
    submission_id = "student-1-problem-1"
    diagnosis = DiagnosisReport.from_fields(
        submission_id=submission_id,
        problem_id="problem-1",
        category="boundary_error",
        summary="边界条件处理不足",
        detail="最大输入失败",
        confidence=0.8,
        evidence=("小数据通过", "最大数据失败"),
        related_lines=(6,),
    )
    explanation = AIExplanation(
        submission_id=submission_id,
        problem_id="problem-1",
        source_diagnosis_category="boundary_error",
        teacher_explanation="算法主体正确，但边界处理不足。",
        student_explanation="请检查最小和最大输入。",
        confidence_note="基于规则诊断。",
    )
    student = StudentAnalysis(
        "张三",
        submission_id,
        make_judge(submission_id, JudgeStatus.WA),
        diagnosis,
        ExplanationResult(ExplanationStatus.SUCCESS, explanation),
    )
    result = ClassAnalysisResult(
        "problem-1", make_judge("standard", JudgeStatus.AC), (student,)
    )
    sources = (StudentSource("张三", "张三.cpp", "#include <iostream>\nint main() {}\n"),)
    return result, sources


def test_history_service_empty_history(tmp_path) -> None:
    service = HistoryService(SQLiteDatabase(tmp_path / "diagnosis.db"))

    assert service.list_tasks() == ()
    assert service.get_task("missing") is None


def test_complete_analysis_save_writes_database_and_files(tmp_path) -> None:
    database = SQLiteDatabase(tmp_path / "data" / "diagnosis.db")
    service = HistoryService(database)
    result, sources = make_analysis_result()

    task = service.save_analysis_result(title="A+B 诊断", result=result, sources=sources)
    loaded = service.get_task(task.id)

    assert loaded is not None
    assert loaded.task.student_count == 1
    assert loaded.students[0].submission.status == "WA"
    assert loaded.students[0].diagnosis.category == "boundary_error"
    assert loaded.students[0].explanation.status == "SUCCESS"
    source_path = database.path.parent / loaded.students[0].submission.source_file_path
    result_path = database.path.parent / loaded.students[0].submission.result_file_path
    assert source_path.read_text(encoding="utf-8") == sources[0].source_code
    assert json.loads(result_path.read_text(encoding="utf-8"))["status"] == "WA"
    assert "source_code" not in result_path.read_text(encoding="utf-8")


def test_history_survives_new_database_connection(tmp_path) -> None:
    path = tmp_path / "data" / "diagnosis.db"
    result, sources = make_analysis_result()
    first = HistoryService(SQLiteDatabase(path))
    task = first.save_analysis_result(title="持久化任务", result=result, sources=sources)

    reopened = HistoryService(SQLiteDatabase(path))
    loaded = reopened.get_task(task.id)

    assert loaded is not None
    assert loaded.task.title == "持久化任务"
    assert loaded.students[0].result_data["student_name"] == "张三"


def test_service_update_and_delete_task_cascades_and_cleans_files(tmp_path) -> None:
    database = SQLiteDatabase(tmp_path / "data" / "diagnosis.db")
    service = HistoryService(database)
    result, sources = make_analysis_result()
    task = service.save_analysis_result(title="原名称", result=result, sources=sources)
    task_directory = database.tasks_root / task.id

    updated = service.update_task_title(task.id, "新名称")
    deleted = service.delete_task(task.id)

    assert updated is not None and updated.title == "新名称"
    assert deleted
    assert service.get_task(task.id) is None
    assert not task_directory.exists()


def test_failed_save_rolls_back_metadata_and_staging_files(tmp_path) -> None:
    database = SQLiteDatabase(tmp_path / "data" / "diagnosis.db")
    service = HistoryService(database)
    result, _ = make_analysis_result()

    with pytest.raises(HistoryServiceError, match="缺少学生源码"):
        service.save_analysis_result(title="失败任务", result=result, sources=())

    assert service.list_tasks() == ()
    assert list(database.tasks_root.iterdir()) == []


def test_same_submission_identity_can_be_saved_in_multiple_tasks(tmp_path) -> None:
    service = HistoryService(SQLiteDatabase(tmp_path / "data" / "diagnosis.db"))
    result, sources = make_analysis_result()

    first = service.save_analysis_result(title="第一次", result=result, sources=sources)
    second = service.save_analysis_result(title="第二次", result=result, sources=sources)

    assert first.id != second.id
    assert len(service.list_tasks()) == 2
    assert service.get_task(first.id).students[0].submission.id != service.get_task(second.id).students[0].submission.id
