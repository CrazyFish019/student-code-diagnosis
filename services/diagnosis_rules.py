"""Deterministic diagnosis rules ordered by diagnostic priority."""

from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Callable

from models.diagnosis import Diagnosis
from models.judge_result import JudgeResult, JudgeStatus, TestCaseResult
from models.problem import Problem
from models.submission import Submission


@dataclass(frozen=True, slots=True)
class DiagnosisContext:
    problem: Problem
    submission: Submission
    judge_result: JudgeResult


@dataclass(frozen=True, slots=True)
class RuleOutcome:
    diagnosis: Diagnosis
    secondary_evidence: tuple[str, ...] = ()


DiagnosisRule = Callable[[DiagnosisContext], RuleOutcome | None]

_NUMBER_PATTERN = re.compile(r"[-+]?(?:\d+(?:\.\d*)?|\.\d+)")
_COMPILER_LINE_PATTERN = re.compile(r":(\d+):(?:\d+:)?")
_LOOP_PATTERN = re.compile(r"\b(?:for|while)\s*\(")
_BOUNDARY_OPERATOR_PATTERN = re.compile(r"(?:<=|>=|==|!=)")


def _results_with_status(
    result: JudgeResult, status: JudgeStatus
) -> tuple[TestCaseResult, ...]:
    return tuple(item for item in result.testcase_results if item.status is status)


def _source_lines_matching(source_code: str, pattern: re.Pattern[str]) -> tuple[int, ...]:
    return tuple(
        line_number
        for line_number, line in enumerate(source_code.splitlines(), start=1)
        if pattern.search(line)
    )


def compile_error_rule(context: DiagnosisContext) -> RuleOutcome | None:
    if context.judge_result.final_status is not JudgeStatus.CE:
        return None

    compiler_stderr = context.judge_result.compile_stderr
    evidence = (compiler_stderr,) if compiler_stderr else ("编译器未返回详细错误信息",)
    related_lines = tuple(
        dict.fromkeys(int(match) for match in _COMPILER_LINE_PATTERN.findall(compiler_stderr))
    )
    return RuleOutcome(
        Diagnosis(
            category="compile_error",
            summary="程序无法编译",
            detail="编译器返回了编译错误，请根据编译器信息检查对应源码位置。",
            confidence=1.0,
            related_lines=related_lines,
            evidence=evidence,
        )
    )


def runtime_error_rule(context: DiagnosisContext) -> RuleOutcome | None:
    if context.judge_result.final_status is not JudgeStatus.RE:
        return None

    failed = _results_with_status(context.judge_result, JudgeStatus.RE)
    evidence: list[str] = []
    for result in failed:
        evidence.append(f"测试点 {result.testcase_id} 非零退出，exit_code={result.exit_code}")
        if result.stderr:
            evidence.append(f"测试点 {result.testcase_id} stderr: {result.stderr}")

    array_lines = _source_lines_matching(
        context.submission.source_code, re.compile(r"\[[^\]]+\]")
    )
    secondary = (
        ("源码包含数组下标访问；这只是辅助特征，不能单独确定运行错误原因。",)
        if array_lines
        else ()
    )
    return RuleOutcome(
        Diagnosis(
            category="runtime_error",
            summary="程序运行时异常退出",
            detail="程序在至少一个测试点返回了非零退出码。",
            confidence=0.9,
            related_lines=array_lines,
            evidence=tuple(evidence),
        ),
        secondary_evidence=secondary,
    )


def _input_scale(input_data: str) -> float:
    numbers = [abs(float(value)) for value in _NUMBER_PATTERN.findall(input_data)]
    return max(numbers, default=float(len(input_data)))


def _testcase_scales(context: DiagnosisContext) -> dict[str, float]:
    return {
        testcase.id: _input_scale(testcase.input_data)
        for testcase in context.problem.test_cases
    }


def performance_issue_rule(context: DiagnosisContext) -> RuleOutcome | None:
    if context.judge_result.final_status is not JudgeStatus.TLE:
        return None

    timed_out = _results_with_status(context.judge_result, JudgeStatus.TLE)
    evidence = [
        f"测试点 {result.testcase_id} 超时，execution_time_ms={result.execution_time_ms}"
        for result in timed_out
    ]
    scales = _testcase_scales(context)
    passed = _results_with_status(context.judge_result, JudgeStatus.AC)
    complexity_pattern = False
    if timed_out and passed and scales:
        timed_out_scales = [scales[item.testcase_id] for item in timed_out]
        passed_scales = [scales[item.testcase_id] for item in passed]
        complexity_pattern = min(timed_out_scales) > min(passed_scales) and max(
            timed_out_scales
        ) == max(scales.values())
    if complexity_pattern:
        evidence.append("小规模测试点通过，而最大规模测试点超时")

    loop_lines = _source_lines_matching(context.submission.source_code, _LOOP_PATTERN)
    loop_count = len(_LOOP_PATTERN.findall(context.submission.source_code))
    secondary = (
        (f"源码检测到 {loop_count} 个循环语句；仅作为复杂度辅助证据。",)
        if loop_count >= 2
        else ()
    )
    detail = (
        "运行结果呈现小数据通过、大数据超时的模式，疑似算法复杂度过高。"
        if complexity_pattern
        else "程序在至少一个测试点超过题目时间限制。"
    )
    return RuleOutcome(
        Diagnosis(
            category="performance_issue",
            summary="程序运行时间超过限制",
            detail=detail,
            confidence=0.95 if complexity_pattern else 0.9,
            related_lines=loop_lines,
            evidence=tuple(evidence),
        ),
        secondary_evidence=secondary,
    )


def _whitespace_tokens(output: str) -> tuple[str, ...]:
    return tuple(output.replace("\r\n", "\n").replace("\r", "\n").split())


def output_format_error_rule(context: DiagnosisContext) -> RuleOutcome | None:
    if context.judge_result.final_status is not JudgeStatus.WA:
        return None

    expected_by_id = {
        testcase.id: testcase.expected_output for testcase in context.problem.test_cases
    }
    wrong_answers = _results_with_status(context.judge_result, JudgeStatus.WA)
    if len(wrong_answers) < 2:
        return None

    formatting_failures = tuple(
        result
        for result in wrong_answers
        if result.testcase_id in expected_by_id
        and _whitespace_tokens(result.stdout)
        == _whitespace_tokens(expected_by_id[result.testcase_id])
        and bool(_whitespace_tokens(expected_by_id[result.testcase_id]))
    )
    if len(formatting_failures) != len(wrong_answers):
        return None

    evidence = tuple(
        f"测试点 {result.testcase_id} 的非空 token 与标准答案一致，但空白布局不同"
        for result in formatting_failures
    )
    return RuleOutcome(
        Diagnosis(
            category="output_format_error",
            summary="疑似输出格式问题",
            detail="多个测试点的答案 token 一致，差异集中在行内空白或前导空白。",
            confidence=0.7,
            evidence=evidence,
        )
    )


def boundary_error_rule(context: DiagnosisContext) -> RuleOutcome | None:
    if context.judge_result.final_status is not JudgeStatus.WA:
        return None
    results = context.judge_result.testcase_results
    if len(results) < 5 or any(
        item.status not in (JudgeStatus.AC, JudgeStatus.WA) for item in results
    ):
        return None

    passed = _results_with_status(context.judge_result, JudgeStatus.AC)
    failed = _results_with_status(context.judge_result, JudgeStatus.WA)
    pass_ratio = len(passed) / len(results)
    if pass_ratio < 0.6 or not failed:
        return None

    scales = _testcase_scales(context)
    if not scales:
        return None
    minimum_scale = min(scales.values())
    maximum_scale = max(scales.values())
    if minimum_scale == maximum_scale:
        return None
    extreme_ids = {
        testcase_id
        for testcase_id, scale in scales.items()
        if scale in (minimum_scale, maximum_scale)
    }
    if any(item.testcase_id not in extreme_ids for item in failed):
        return None
    if not any(item.testcase_id not in extreme_ids for item in passed):
        return None

    testcase_by_id = {testcase.id: testcase for testcase in context.problem.test_cases}
    evidence = [f"通过 {len(passed)}/{len(results)} 个测试点，大部分普通数据正确"]
    evidence.extend(
        f"边界候选测试点 {item.testcase_id} 失败，输入={testcase_by_id[item.testcase_id].input_data!r}"
        for item in failed
    )
    boundary_lines = _source_lines_matching(
        context.submission.source_code, _BOUNDARY_OPERATOR_PATTERN
    )
    secondary = (
        ("源码包含边界比较运算；仅用于补充运行结果证据。",)
        if boundary_lines
        else ()
    )
    return RuleOutcome(
        Diagnosis(
            category="boundary_error",
            summary="疑似边界条件处理错误",
            detail="失败集中在输入规模的最小值或最大值测试点。",
            confidence=min(0.85, 0.6 + 0.25 * pass_ratio),
            related_lines=boundary_lines,
            evidence=tuple(evidence),
        ),
        secondary_evidence=secondary,
    )


# This tuple is the single source of truth for diagnostic priority.
DIAGNOSIS_RULES: tuple[DiagnosisRule, ...] = (
    compile_error_rule,
    runtime_error_rule,
    performance_issue_rule,
    output_format_error_rule,
    boundary_error_rule,
)
