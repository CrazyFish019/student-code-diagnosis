from services.result_query import ResultSort, StudentResultRow, query_results, result_statistics
from ui.presenters import result_row_to_view


def row(name: str, status: str, passed: int, total: int, diagnosis=None):
    return StudentResultRow(name, name, status, passed, total, diagnosis, "NOT_AVAILABLE")


def test_attention_sort_places_wa_before_ac() -> None:
    rows = (row("AC学生", "AC", 10, 10), row("WA学生", "WA", 8, 10))

    assert [item.status for item in query_results(rows)] == ["WA", "AC"]


def test_status_sort_prioritizes_tle() -> None:
    rows = (row("WA学生", "WA", 2, 10), row("TLE学生", "TLE", 2, 10))

    assert query_results(rows, sort_by=ResultSort.STATUS)[0].status == "TLE"


def test_status_filter() -> None:
    rows = (row("甲", "WA", 1, 2), row("乙", "AC", 2, 2))

    assert [item.student_name for item in query_results(rows, status="WA")] == ["甲"]


def test_diagnosis_filter() -> None:
    rows = (
        row("甲", "WA", 1, 2, "boundary_error"),
        row("乙", "TLE", 0, 2, "performance_issue"),
    )

    assert query_results(rows, diagnosis="boundary_error")[0].student_name == "甲"


def test_statistics_include_status_and_diagnosis_distribution() -> None:
    statistics = result_statistics(
        (row("甲", "WA", 1, 2, "boundary_error"), row("乙", "AC", 2, 2))
    )

    assert statistics["TOTAL"] == 2
    assert statistics["WA"] == 1
    assert statistics["DIAGNOSIS"] == {"boundary_error": 1}


def test_result_view_conversion_contains_teacher_columns() -> None:
    view = result_row_to_view(row("张三", "WA", 8, 10, "boundary_error"))

    assert view["通过数"] == 8
    assert view["总测试点"] == 10
    assert view["通过率"] == "80%"
    assert view["主要诊断"] == "边界问题"
