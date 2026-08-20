"""Class summary and individual student result widgets."""

import streamlit as st

from models.workbench import ClassAnalysisResult
from services.result_query import (
    ResultSort,
    project_current_results,
    query_results,
    result_statistics,
)
from ui.presenters import (
    build_status_counts,
    build_summary_rows,
    diagnosis_label,
    explanation_text,
    result_row_to_view,
)


def render_result_view(
    result: ClassAnalysisResult,
    *,
    default_sort: str = ResultSort.ATTENTION.value,
    default_status_filter: str = "全部",
    default_diagnosis_filter: str = "全部",
) -> None:
    st.subheader("4. 诊断结果")
    projected = project_current_results(result)
    counts = result_statistics(projected)
    total, ac, wa, tle, other = st.columns(5)
    total.metric("总人数", counts.get("TOTAL", 0))
    ac.metric("AC", counts.get("AC", 0))
    wa.metric("WA", counts.get("WA", 0))
    tle.metric("TLE", counts.get("TLE", 0))
    known = counts.get("AC", 0) + counts.get("WA", 0) + counts.get("TLE", 0)
    other.metric("其他", counts.get("TOTAL", 0) - known)

    diagnosis_counts = counts.get("DIAGNOSIS", {})
    st.caption(
        "诊断分布："
        f"边界错误 {diagnosis_counts.get('boundary_error', 0)} · "
        f"复杂度问题 {diagnosis_counts.get('performance_issue', 0)} · "
        f"运行错误 {diagnosis_counts.get('runtime_error', 0)}"
    )
    filter_col, diagnosis_col, sort_col = st.columns(3)
    status_filter = filter_col.selectbox(
        "状态筛选",
        ["全部", "AC", "WA", "CE", "RE", "TLE"],
        index=["全部", "AC", "WA", "CE", "RE", "TLE"].index(default_status_filter)
        if default_status_filter in ["全部", "AC", "WA", "CE", "RE", "TLE"] else 0,
        key="current_status_filter",
    )
    diagnosis_filter = diagnosis_col.selectbox(
        "诊断筛选",
        ["全部", "boundary_error", "performance_issue", "runtime_error", "compile_error"],
        index=["全部", "boundary_error", "performance_issue", "runtime_error", "compile_error"].index(default_diagnosis_filter)
        if default_diagnosis_filter in ["全部", "boundary_error", "performance_issue", "runtime_error", "compile_error"] else 0,
        key="current_diagnosis_filter",
    )
    sort_values = [item.value for item in ResultSort]
    initial_sort = sort_values.index(default_sort) if default_sort in sort_values else 0
    sort_value = sort_col.selectbox(
        "排序", sort_values, index=initial_sort, key="current_result_sort"
    )
    visible_rows = query_results(
        projected,
        sort_by=ResultSort(sort_value),
        status=None if status_filter == "全部" else status_filter,
        diagnosis=None if diagnosis_filter == "全部" else diagnosis_filter,
    )
    st.dataframe(
        [result_row_to_view(row) for row in visible_rows],
        use_container_width=True,
        hide_index=True,
    )
    if not result.students:
        st.info("暂无学生结果。")
        return

    names = [row.student_name for row in visible_rows]
    if not names:
        st.info("没有符合当前筛选条件的学生。")
        return
    selected_name = st.selectbox("查看学生详情", names, key="selected_student")
    student = next(item for item in result.students if item.student_name == selected_name)
    st.markdown(f"### 学生：{student.student_name}")
    st.write(f"题目：**{result.problem_id}**")
    if student.error_message is not None:
        st.error(f"该学生处理失败：{student.error_message}")
        return

    assert student.judge_result is not None
    assert student.diagnosis_report is not None
    judged = student.judge_result
    st.write(f"判题结果：**{judged.final_status.value}**")
    st.write(f"测试点：**{judged.passed_count}/{judged.total_count}**")
    st.write(
        f"规则诊断：**{diagnosis_label(student.diagnosis_report.category)}**"
    )
    st.write(f"诊断置信度：**{student.diagnosis_report.confidence:.0%}**")
    if student.diagnosis_report.evidence:
        st.write("证据：")
        for item in student.diagnosis_report.evidence:
            st.markdown(f"- {item}")
    else:
        st.caption("暂无规则证据。")

    with st.expander("测试点详情"):
        st.dataframe(
            [
                {
                    "测试点": item.testcase_id,
                    "状态": item.status.value,
                    "耗时(ms)": item.execution_time_ms,
                    "退出码": item.exit_code,
                }
                for item in judged.testcase_results
            ],
            use_container_width=True,
            hide_index=True,
        )

    teacher_text, student_text = explanation_text(student)
    st.write("AI 解释：")
    if teacher_text is None and student_text is None:
        st.info("暂无解释。")
    else:
        st.markdown("**面向教师**")
        st.write(teacher_text)
        st.markdown("**面向学生**")
        st.write(student_text)
