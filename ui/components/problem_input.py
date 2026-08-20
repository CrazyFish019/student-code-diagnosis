"""Problem and reference-data input widgets."""

from dataclasses import dataclass
from typing import Any

import streamlit as st


@dataclass(frozen=True, slots=True)
class ProblemInputValues:
    problem_id: str
    title: str
    standard_file: Any
    testcase_file: Any


def render_problem_input() -> ProblemInputValues:
    st.subheader("1. 题目信息")
    left, right = st.columns(2)
    problem_id = left.text_input("题目 ID", value="problem-1")
    title = right.text_input("题目名称", value="A+B")
    standard_file = st.file_uploader(
        "标准程序（.cpp）",
        type=["cpp"],
        key="standard_program_upload",
    )
    testcase_file = st.file_uploader(
        "测试数据（JSON，或包含成对 .in/.out 的 ZIP）",
        type=["json", "zip"],
        key="testcase_upload",
        help="JSON 支持 test_cases 列表；ZIP 中同名 .in/.out 自动配对。",
    )
    return ProblemInputValues(problem_id, title, standard_file, testcase_file)
