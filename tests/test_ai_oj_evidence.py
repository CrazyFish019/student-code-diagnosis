import json
from dataclasses import replace

from models.imported_problem import ImportedProblem
from models.code_language import CodeLanguage
from models.execution_result import ExecutionStatus
from models.vesibay_submission import OJCaseEvidence, VesibaySubmissionEvidence
from services.ai_code_diagnosis_service import (
    _normalize_diagnosis_payload,
    _user_prompt,
)


def _evidence() -> VesibaySubmissionEvidence:
    problem = ImportedProblem(
        source_url="https://www.vesibay.cn/problem/P1000",
        oj_name="Vesibay",
        external_problem_id="P1000",
        title="A+B",
        description="求和",
        input_description="两个整数",
        output_description="和",
        hint="",
        time_limit_ms=1000,
        memory_limit_mb=128,
    )
    return VesibaySubmissionEvidence(
        submission_id="48543",
        problem=problem,
        source_code="int main(){}",
        final_status="WA",
        score=50,
        cases=(
            OJCaseEvidence("1", "AC", 1, 100, "1 2", "3", "3"),
            OJCaseEvidence("2", "WA", 2, 100, "2 3", "5", "4"),
        ),
    )


def test_oj_prompt_contains_failed_case_without_identity_fields() -> None:
    evidence = _evidence()

    prompt = _user_prompt(
        evidence.problem,
        evidence.source_code,
        oj_evidence=evidence,
        selected_case_ids=("2",),
    )
    payload = json.loads(prompt.split("\n", 1)[1])

    oj = payload["oj_judge_evidence"]
    assert oj["final_status"] == "WA"
    assert payload["code_language"] == "cpp"
    assert oj["code_language"] == "cpp"
    assert oj["case_status_counts"] == {"AC": 1, "WA": 1}
    assert oj["student_output_available"] is False
    assert "权威标准答案" in oj["evidence_semantics"]
    assert len(oj["selected_cases"]) == 1
    assert oj["selected_cases"][0]["input"] == "2 3"
    assert oj["selected_cases"][0]["authoritative_expected_output"] == "5"
    assert "expected_output" not in oj["selected_cases"][0]
    assert "user_output" not in oj["selected_cases"][0]
    assert "username" not in prompt
    assert "ip" not in oj
    assert "uid" not in oj


def test_oj_prompt_does_not_send_testcase_contents_without_teacher_opt_in() -> None:
    evidence = _evidence()

    prompt = _user_prompt(
        evidence.problem, evidence.source_code, oj_evidence=evidence
    )
    oj = json.loads(prompt.split("\n", 1)[1])["oj_judge_evidence"]

    assert oj["selected_cases"] == []
    assert oj["case_status_counts"] == {"AC": 1, "WA": 1}
    assert "未授权发送" in oj["selected_cases_note"]


def test_oj_system_prompt_forbids_inventing_student_output() -> None:
    from services.ai_code_diagnosis_service import _system_prompt

    prompt = _system_prompt(has_oj_evidence=True)

    assert "权威标准答案" in prompt
    assert "不得臆测或声称学生输出" in prompt
    assert "逐行对应" in prompt
    assert "明确验算" in prompt
    assert "循环起止范围" in prompt


def test_python_submission_prompt_uses_python_language_rules() -> None:
    from services.ai_code_diagnosis_service import _system_prompt

    evidence = replace(
        _evidence(),
        source_code="print(input())",
        language=CodeLanguage.PYTHON,
    )
    prompt = _user_prompt(
        evidence.problem,
        evidence.source_code,
        oj_evidence=evidence,
    )
    payload = json.loads(prompt.split("\n", 1)[1])
    system = _system_prompt(language=CodeLanguage.PYTHON)

    assert payload["code_language"] == "python"
    assert payload["oj_judge_evidence"]["code_language"] == "python"
    assert "Python 3代码" in system
    assert "不得套用其他语言规则" in system


def test_local_execution_output_is_labeled_and_sent_to_model() -> None:
    evidence = _evidence()
    local_case = replace(
        evidence.cases[1],
        local_execution_status=ExecutionStatus.SUCCESS,
        locally_captured_stdout="1002001\n",
        locally_captured_stderr="",
        local_exit_code=0,
        local_execution_time_ms=12,
    )
    evidence = replace(evidence, cases=(evidence.cases[0], local_case))

    prompt = _user_prompt(
        evidence.problem,
        evidence.source_code,
        oj_evidence=evidence,
        selected_case_ids=("2",),
    )
    oj = json.loads(prompt.split("\n", 1)[1])["oj_judge_evidence"]

    assert oj["student_output_available"] is True
    local = oj["selected_cases"][0]["local_execution"]
    assert local["locally_captured_stdout"] == "1002001\n"
    assert local["status"] == "SUCCESS"
    comparison = local["output_comparison"]
    assert comparison["matches_under_judge_rules"] is False
    assert comparison["first_differing_line"] == 1
    assert comparison["expected_at_first_difference"] == "5"
    assert comparison["actual_at_first_difference"] == "1002001"


def test_local_execution_system_prompt_distinguishes_both_outputs() -> None:
    from services.ai_code_diagnosis_service import _system_prompt

    prompt = _system_prompt(has_oj_evidence=True, has_local_execution=True)

    assert "权威标准答案" in prompt
    assert "真实捕获的学生输出" in prompt
    assert "逐行比较" in prompt
    assert "output_comparison" in prompt
    assert "不得再穷举模拟" in prompt
    assert "root_cause不超过500" in prompt


def test_oj_diagnosis_limitations_do_not_claim_hidden_tests_were_absent() -> None:
    payload = {
        "conclusion": "likely_incorrect",
        "summary": "边界错误",
        "categories": ["boundary_error"],
        "root_cause": "遗漏边界",
        "evidence": [],
        "sample_analysis": [],
        "suggestions": ["补充判断"],
        "teacher_feedback": "建议检查边界",
        "student_feedback": "请检查边界",
        "confidence": 0.9,
        "limitations": ["没有使用隐藏测试数据"],
    }

    normalized = _normalize_diagnosis_payload(payload, has_oj_evidence=True)

    assert not any("没有使用隐藏测试数据" in item for item in normalized["limitations"])
    assert any("OJ已有判题记录" in item for item in normalized["limitations"])
