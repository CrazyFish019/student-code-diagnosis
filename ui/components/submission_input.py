"""Student source upload widgets."""

from typing import Any

import streamlit as st


def render_submission_input() -> list[Any]:
    st.subheader("2. 学生代码导入")
    uploads = st.file_uploader(
        "上传单个/多个 .cpp，或包含学生代码的 ZIP",
        type=["cpp", "zip"],
        accept_multiple_files=True,
        key="student_source_uploads",
    )
    if uploads:
        st.caption(f"已选择 {len(uploads)} 个上传文件。")
    return list(uploads or [])
