from models import (
    ClassAnalysisResult,
    DiagnosisReport,
    JudgeResult,
    JudgeStatus,
    StudentAnalysis,
    TestCaseResult as DomainTestCaseResult,
)
from services.teacher_workflow import TeacherWorkflowError
from ui.file_parsers import UIInputError
from ui.presenters import (
    build_status_counts,
    build_summary_rows,
    exception_to_user_message,
)
from ui.state import (
    TaskStatus,
    clear_ai_diagnosis,
    initialize_session_state,
    mark_task_completed,
    mark_task_failed,
    mark_task_running,
    consume_ai_diagnosis_request,
    finish_ai_diagnosis,
    pop_ai_diagnosis_notice,
    request_ai_diagnosis,
    consume_testcase_details_open,
    keep_testcase_details_open,
)


def make_judge_result(status: JudgeStatus) -> JudgeResult:
    case_status = JudgeStatus.AC if status is JudgeStatus.AC else status
    return JudgeResult(
        submission_id="submission-1",
        problem_id="problem-1",
        final_status=status,
        testcase_results=(
            DomainTestCaseResult("case-1", case_status, 10, "", "", 0),
        ),
    )


def test_task_state_survives_rerun_initialization() -> None:
    state: dict[str, object] = {}
    initialize_session_state(state)
    mark_task_running(state, upload_info=("standard.cpp", "students.zip"))
    result = object()
    mark_task_completed(state, result)
    initialize_session_state(state)

    assert state["task_status"] is TaskStatus.COMPLETED
    assert state["analysis_result"] is result
    assert state["upload_info"] == ("standard.cpp", "students.zip")


def test_task_failure_keeps_user_message() -> None:
    state: dict[str, object] = {}
    initialize_session_state(state)
    mark_task_failed(state, "编译器不可用")

    assert state["task_status"] is TaskStatus.FAILED
    assert state["task_error"] == "编译器不可用"


def test_new_import_clears_previous_ai_report() -> None:
    report = object()
    state: dict[str, object] = {
        "ai_code_diagnosis": report,
        "ai_diagnosis_has_oj_evidence": True,
        "selected_oj_case_ids": ("1", "2"),
        "send_selected_oj_cases": True,
        "oj_case_selected_48543_0_1": True,
    }

    clear_ai_diagnosis(state)

    assert state["ai_code_diagnosis"] is None
    assert state["ai_diagnosis_has_oj_evidence"] is False
    assert state["selected_oj_case_ids"] == ()
    assert state["send_selected_oj_cases"] is False
    assert "oj_case_selected_48543_0_1" not in state


def test_ai_diagnosis_request_is_locked_and_consumed_once() -> None:
    state: dict[str, object] = {"ai_code_diagnosis": object()}

    assert request_ai_diagnosis(state) is True
    assert request_ai_diagnosis(state) is False
    assert state["ai_diagnosis_running"] is True
    assert state["ai_code_diagnosis"] is None
    assert consume_ai_diagnosis_request(state) is True
    assert consume_ai_diagnosis_request(state) is False

    finish_ai_diagnosis(state, level="error", message="请求超时")
    assert state["ai_diagnosis_running"] is False
    assert pop_ai_diagnosis_notice(state) == ("error", "请求超时")
    assert pop_ai_diagnosis_notice(state) is None


def test_testcase_action_keeps_expander_open_for_exactly_one_rerun() -> None:
    state: dict[str, object] = {}

    keep_testcase_details_open(state)

    assert consume_testcase_details_open(state) is True
    assert consume_testcase_details_open(state) is False


def test_result_conversion_builds_summary_and_counts() -> None:
    standard = make_judge_result(JudgeStatus.AC)
    ac = StudentAnalysis(
        "张三",
        "submission-1",
        make_judge_result(JudgeStatus.AC),
        DiagnosisReport("submission-1", "problem-1", None),
    )
    wa = StudentAnalysis(
        "李四",
        "submission-2",
        JudgeResult(
            submission_id="submission-2",
            problem_id="problem-1",
            final_status=JudgeStatus.WA,
            testcase_results=(
                DomainTestCaseResult("case-1", JudgeStatus.WA, 10, "2\n", "", 0),
            ),
        ),
        DiagnosisReport.from_fields(
            submission_id="submission-2",
            problem_id="problem-1",
            category="boundary_error",
            summary="边界问题",
            detail="边界失败",
            confidence=0.8,
        ),
    )
    result = ClassAnalysisResult("problem-1", standard, (ac, wa))

    rows = build_summary_rows(result)
    counts = build_status_counts(result)

    assert rows[0] == {"学生": "张三", "状态": "AC", "通过": "1/1", "诊断": "-"}
    assert rows[1]["诊断"] == "边界问题"
    assert counts == {"TOTAL": 2, "AC": 1, "WA": 1}


def test_known_exceptions_convert_to_teacher_messages() -> None:
    assert exception_to_user_message(UIInputError("ZIP为空")) == "ZIP为空"
    assert (
        exception_to_user_message(TeacherWorkflowError("编译器不可用"))
        == "编译器不可用"
    )
    assert "处理失败" in exception_to_user_message(RuntimeError("secret traceback"))
    assert "secret traceback" not in exception_to_user_message(
        RuntimeError("secret traceback")
    )
