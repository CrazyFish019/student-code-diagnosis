"""Read-only Streamlit view of persisted diagnosis tasks."""

from pathlib import Path

import streamlit as st

from services.history_service import HistoryService, HistoryServiceError
from services.report_export import (
    ExportPermissionError,
    ReportExportError,
    export_class_report,
    export_student_feedback,
)
from services.result_query import ResultSort, project_historical_results, query_results
from ui.history_presenters import build_history_student_rows, build_history_task_rows
from ui.presenters import diagnosis_label, result_row_to_view


def render_recent_tasks(service: HistoryService) -> None:
    try:
        tasks = service.list_tasks()[:5]
        st.subheader("最近任务")
        if tasks:
            st.dataframe(
                build_history_task_rows(tasks), use_container_width=True, hide_index=True
            )
        else:
            st.caption("暂无历史任务。")
    except HistoryServiceError:
        st.warning("历史记录不可用。")


def render_history_view(
    service: HistoryService,
    *,
    default_sort: str = ResultSort.ATTENTION.value,
    default_status_filter: str = "全部",
    default_diagnosis_filter: str = "全部",
) -> None:
    st.divider()
    st.subheader("5. 历史任务")
    try:
        tasks = service.list_tasks()
        if not tasks:
            st.info("暂无历史任务。")
            return

        st.dataframe(
            build_history_task_rows(tasks), use_container_width=True, hide_index=True
        )
        selected_id = st.selectbox(
            "查看历史任务",
            [task.id for task in tasks],
            format_func=lambda task_id: _task_label(tasks, task_id),
            key="selected_history_task",
        )
        historical_task = service.get_task(selected_id)
        if historical_task is None:
            st.warning("所选历史任务不存在。")
            return
        projected = project_historical_results(historical_task)
        filter_col, diagnosis_col, sort_col = st.columns(3)
        status_filter = filter_col.selectbox(
            "历史状态筛选",
            ["全部", "AC", "WA", "CE", "RE", "TLE"],
            index=["全部", "AC", "WA", "CE", "RE", "TLE"].index(default_status_filter)
            if default_status_filter in ["全部", "AC", "WA", "CE", "RE", "TLE"] else 0,
        )
        diagnosis_filter = diagnosis_col.selectbox(
            "历史诊断筛选",
            ["全部", "boundary_error", "performance_issue", "runtime_error", "compile_error"],
            index=["全部", "boundary_error", "performance_issue", "runtime_error", "compile_error"].index(default_diagnosis_filter)
            if default_diagnosis_filter in ["全部", "boundary_error", "performance_issue", "runtime_error", "compile_error"] else 0,
        )
        sort_values = [item.value for item in ResultSort]
        initial_sort = sort_values.index(default_sort) if default_sort in sort_values else 0
        sort_value = sort_col.selectbox("历史排序", sort_values, index=initial_sort)
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
        if not visible_rows:
            st.info("没有符合当前筛选条件的学生。")
            return

        class_export_key = f"class_export_path_{selected_id}"
        if st.button("生成班级 Excel", key=f"generate_class_export_{selected_id}"):
            try:
                st.session_state[class_export_key] = str(
                    export_class_report(historical_task)
                )
            except ExportPermissionError:
                st.warning("无法写入导出目录。")
            except ReportExportError:
                st.warning("报告生成失败。")
        class_export_path = st.session_state.get(class_export_key)
        if class_export_path:
            class_path = Path(class_export_path)
            if class_path.is_file():
                st.download_button(
                    "下载班级 Excel",
                    data=class_path.read_bytes(),
                    file_name=class_path.name,
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    key=f"class_export_{selected_id}",
                )

        selected_submission_id = st.selectbox(
            "查看历史学生详情",
            [row.submission_id for row in visible_rows],
            format_func=lambda submission_id: _student_label(
                historical_task, submission_id
            ),
            key=f"selected_history_student_{selected_id}",
        )
        student = next(
            item
            for item in historical_task.students
            if item.submission.id == selected_submission_id
        )
        submission = student.submission
        st.markdown(f"### 历史学生：{submission.student_name}")
        st.write(f"题目：**{historical_task.task.title}（{historical_task.task.problem_id}）**")
        st.write(f"判题结果：**{submission.status}**")
        st.write(f"测试点：**{submission.passed_count}/{submission.total_count}**")
        if submission.error_message:
            st.error(f"该学生处理失败：{submission.error_message}")

        diagnosis = student.diagnosis
        st.write(
            f"规则诊断：**{diagnosis_label(diagnosis.category if diagnosis else None)}**"
        )
        if diagnosis:
            st.write(f"诊断置信度：**{diagnosis.confidence:.0%}**")
        testcase_results = student.result_data.get("testcase_results", [])
        if isinstance(testcase_results, list) and testcase_results:
            with st.expander("历史测试点详情"):
                st.dataframe(
                    [
                        {
                            "编号": item.get("testcase_id", "-"),
                            "状态": item.get("status", "-"),
                            "运行时间(ms)": item.get("execution_time_ms", 0),
                        }
                        for item in testcase_results
                        if isinstance(item, dict)
                    ],
                    use_container_width=True,
                    hide_index=True,
                )
        if diagnosis and diagnosis.evidence:
            st.write("证据：")
            for evidence in diagnosis.evidence:
                st.markdown(f"- {evidence}")
        else:
            st.caption("暂无规则证据。")

        explanation = student.explanation
        st.write("AI 解释：")
        if explanation is None or not (
            explanation.teacher_explanation or explanation.student_explanation
        ):
            st.info("暂无解释。")
        else:
            if explanation.teacher_explanation:
                st.markdown("**面向教师**")
                st.write(explanation.teacher_explanation)
            if explanation.student_explanation:
                st.markdown("**面向学生**")
                st.write(explanation.student_explanation)
        feedback_export_key = f"feedback_export_path_{selected_submission_id}"
        if st.button(
            "生成学生反馈 HTML", key=f"generate_feedback_{selected_submission_id}"
        ):
            try:
                st.session_state[feedback_export_key] = str(
                    export_student_feedback(historical_task, selected_submission_id)
                )
            except ExportPermissionError:
                st.warning("无法写入导出目录。")
            except ReportExportError:
                st.warning("报告生成失败。")
        feedback_export_path = st.session_state.get(feedback_export_key)
        if feedback_export_path:
            feedback_path = Path(feedback_export_path)
            if feedback_path.is_file():
                st.download_button(
                    "下载学生反馈 HTML",
                    data=feedback_path.read_bytes(),
                    file_name=feedback_path.name,
                    mime="text/html",
                    key=f"student_export_{selected_submission_id}",
                )
    except HistoryServiceError:
        st.warning("历史记录不可用。")


def _task_label(tasks: tuple, task_id: str) -> str:
    task = next(item for item in tasks if item.id == task_id)
    local_time = task.created_at.astimezone().strftime("%Y-%m-%d %H:%M")
    return f"{task.title} · {local_time}"


def _student_label(task, submission_id: str) -> str:
    student = next(
        item for item in task.students if item.submission.id == submission_id
    )
    return student.submission.student_name
