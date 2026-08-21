"""Vesibay URL import and editable statement widgets."""

from __future__ import annotations

import streamlit as st

from models.imported_problem import ImportedProblem, ProblemExample
from services.problem_importer import ProblemImportError, import_public_problem
from ui.state import clear_ai_diagnosis, is_ai_diagnosis_active


def render_problem_import() -> ImportedProblem | None:
    st.subheader("1. 获取题目")
    url = st.text_input(
        "题目网址",
        placeholder="请粘贴公开题目网址",
        key="problem_url",
    )
    if st.button(
        "获取题目信息",
        type="primary",
        disabled=is_ai_diagnosis_active(st.session_state),
    ):
        clear_ai_diagnosis(st.session_state)
        try:
            with st.spinner("正在获取题目…"):
                problem = import_public_problem(url)
            _store_problem(problem)
            st.success(f"已获取：{problem.external_problem_id} {problem.title}")
        except ProblemImportError as exc:
            st.error(str(exc))
    problem = st.session_state.get("imported_problem")
    if not isinstance(problem, ImportedProblem):
        st.info("请输入公开题目网址并获取题目信息。")
        return None
    st.subheader("2. 题目信息")
    title = st.text_input("题目标题", key="imported_title")
    description = st.text_area("题目描述", height=140, key="imported_description")
    input_description = st.text_area(
        "输入描述", height=120, key="imported_input_description"
    )
    output_description = st.text_area(
        "输出描述", height=100, key="imported_output_description"
    )
    hint = st.text_area("提示", height=80, key="imported_hint")
    examples: list[ProblemExample] = []
    if problem.examples:
        st.markdown("**公开样例**")
        for index in range(len(problem.examples)):
            input_col, output_col = st.columns(2)
            examples.append(
                ProblemExample(
                    input_col.text_area(
                        f"样例 {index + 1} 输入", key=f"imported_example_input_{index}"
                    ),
                    output_col.text_area(
                        f"样例 {index + 1} 输出", key=f"imported_example_output_{index}"
                    ),
                )
            )
    else:
        st.warning("该题没有公开样例，AI诊断可信度可能降低。")
    try:
        return ImportedProblem(
            source_url=problem.source_url,
            oj_name=problem.oj_name,
            external_problem_id=problem.external_problem_id,
            title=title,
            description=description,
            input_description=input_description,
            output_description=output_description,
            hint=hint,
            time_limit_ms=problem.time_limit_ms,
            memory_limit_mb=problem.memory_limit_mb,
            examples=tuple(examples),
        )
    except Exception:
        st.warning("题目信息不完整，请检查标题和内容。")
        return None


def _store_problem(problem: ImportedProblem) -> None:
    clear_ai_diagnosis(st.session_state)
    st.session_state["imported_problem"] = problem
    st.session_state["imported_title"] = problem.title
    st.session_state["imported_description"] = problem.description
    st.session_state["imported_input_description"] = problem.input_description
    st.session_state["imported_output_description"] = problem.output_description
    st.session_state["imported_hint"] = problem.hint
    for index, example in enumerate(problem.examples):
        st.session_state[f"imported_example_input_{index}"] = example.input_data
        st.session_state[f"imported_example_output_{index}"] = example.expected_output
