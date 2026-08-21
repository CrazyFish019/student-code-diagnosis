"""Authorized Vesibay submission import widgets."""

from __future__ import annotations

import streamlit as st

from models.vesibay_submission import VesibaySubmissionEvidence
from services.vesibay_readonly_client import (
    VesibayAccessError,
    VesibayCredentials,
    VesibayReadOnlyClient,
)
from ui.state import clear_ai_diagnosis, is_ai_diagnosis_active
from ui.components.testcase_details import render_source_code, render_testcase_details


def render_submission_import(
    credentials: VesibayCredentials | None,
) -> VesibaySubmissionEvidence | None:
    st.subheader("1. 获取OJ提交")
    url = st.text_input(
        "提交详情网址",
        placeholder="请粘贴提交详情网址",
        key="submission_detail_url",
    )
    if st.button(
        "获取提交信息",
        type="primary",
        disabled=is_ai_diagnosis_active(st.session_state),
    ):
        clear_ai_diagnosis(st.session_state)
        if credentials is None:
            st.error("请先在侧边栏填写并保存有效的网站账号。")
        else:
            try:
                with st.spinner("正在读取题目、源码和判题证据…"):
                    evidence = VesibayReadOnlyClient().import_submission(url, credentials)
                st.session_state["vesibay_submission_evidence"] = evidence
                st.success(
                    f"已获取提交 {evidence.submission_id}："
                    f"{evidence.problem.external_problem_id} {evidence.problem.title}"
                )
            except VesibayAccessError as exc:
                st.error(str(exc))

    evidence = st.session_state.get("vesibay_submission_evidence")
    if not isinstance(evidence, VesibaySubmissionEvidence):
        st.info("请输入提交详情网址并获取信息。")
        return None

    st.subheader("2. OJ判题证据")
    status_col, score_col, case_col = st.columns(3)
    status_col.metric("状态", evidence.final_status)
    score_col.metric("得分", "-" if evidence.score is None else f"{evidence.score:g}")
    case_col.metric("测试点", len(evidence.cases))
    st.write(f"题目：{evidence.problem.external_problem_id} {evidence.problem.title}")
    render_testcase_details(evidence.cases, evidence.submission_id)
    render_source_code(evidence.source_code)
    st.caption("测试点内容默认仅在本机查看；身份信息和IP不会发送给模型。")
    return evidence
