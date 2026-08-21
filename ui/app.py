"""Streamlit composition for single-problem AI code diagnosis."""

from collections.abc import MutableMapping
from concurrent.futures import Future, ThreadPoolExecutor
from typing import Any

import streamlit as st

from core.runtime_storage import migrate_legacy_runtime_data
from models.ai_code_diagnosis import AICodeDiagnosis
from models.imported_problem import ImportedProblem
from models.vesibay_submission import VesibaySubmissionEvidence
from services.ai_code_diagnosis_service import AIDiagnosisError, diagnose_code
from services.selected_case_runner import (
    SelectedCaseExecutionError,
    run_selected_testcases,
)
from services.settings_service import AppSettings
from ui.components.ai_diagnosis_view import render_ai_diagnosis, render_source_input
from ui.components.model_settings import render_model_settings
from ui.components.problem_import import render_problem_import
from ui.components.submission_import import render_submission_import
from ui.components.update_view import render_update_view
from ui.components.vesibay_settings import render_vesibay_settings
from ui.state import (
    consume_ai_diagnosis_request,
    finish_ai_diagnosis,
    initialize_session_state,
    is_ai_diagnosis_active,
    pop_ai_diagnosis_notice,
    request_ai_diagnosis,
)

_DIAGNOSIS_EXECUTOR = ThreadPoolExecutor(
    max_workers=2,
    thread_name_prefix="ai-diagnosis",
)


def _queue_ai_diagnosis() -> None:
    request_ai_diagnosis(st.session_state)


def main() -> None:
    st.set_page_config(page_title="学生代码AI诊断助手", page_icon="🔎", layout="wide")
    for warning in migrate_legacy_runtime_data():
        st.warning(warning)
    initialize_session_state(st.session_state)
    st.title("学生代码AI诊断助手")
    st.caption("粘贴代码进行静态诊断，或读取提交记录进行证据增强诊断。")

    credentials = render_vesibay_settings()
    settings, api_key = render_model_settings()
    render_update_view()
    diagnosis_active = is_ai_diagnosis_active(st.session_state)
    mode = st.radio(
        "诊断方式",
        ("题目网址＋粘贴代码", "提交详情网址"),
        horizontal=True,
        disabled=diagnosis_active,
    )
    oj_evidence = None
    if mode == "题目网址＋粘贴代码":
        problem = render_problem_import()
        source_code = render_source_input()
    else:
        oj_evidence = render_submission_import(credentials)
        problem = oj_evidence.problem if oj_evidence is not None else None
        source_code = oj_evidence.source_code if oj_evidence is not None else ""

    _render_diagnosis_section(
        problem=problem,
        source_code=source_code,
        settings=settings,
        api_key=api_key,
        oj_evidence=oj_evidence,
    )


def _render_diagnosis_section(
    *,
    problem: ImportedProblem | None,
    source_code: str,
    settings: AppSettings,
    api_key: str,
    oj_evidence: VesibaySubmissionEvidence | None,
) -> None:
    _finish_background_diagnosis_if_ready()
    st.subheader("3. 开始诊断" if oj_evidence is not None else "4. 开始诊断")
    notice_slot = st.empty()
    progress_slot = st.empty()
    report_slot = st.empty()

    notice = pop_ai_diagnosis_notice(st.session_state)
    if notice is not None:
        level, message = notice
        (notice_slot.success if level == "success" else notice_slot.error)(message)
    diagnosis_running = is_ai_diagnosis_active(st.session_state)
    button_column, option_column = st.columns((1, 3), vertical_alignment="center")
    with button_column:
        st.button(
            "开始AI诊断",
            type="primary",
            key="start_ai_diagnosis_button",
            disabled=diagnosis_running,
            on_click=_queue_ai_diagnosis,
        )
    with option_column:
        send_selected_cases = st.checkbox(
            "发送选中的测试点详情给模型",
            value=False,
            key="send_selected_oj_cases",
            disabled=oj_evidence is None or diagnosis_running,
            help=(
                "默认关闭。开启后会在本机编译一次学生代码，仅运行勾选的测试点，"
                "再把实际输出和标准输出发送给模型。"
            ),
        )
        selected_case_ids = tuple(st.session_state.get("selected_oj_case_ids", ()))
        if oj_evidence is not None:
            st.caption(f"当前已选 {len(selected_case_ids)} 个测试点。")
        if send_selected_cases:
            st.caption("本地执行有超时和进程树清理，但不是恶意代码安全沙箱。")
    if diagnosis_running:
        with progress_slot.container():
            _render_diagnosis_progress()
    if consume_ai_diagnosis_request(st.session_state):
        if problem is None:
            finish_ai_diagnosis(
                st.session_state,
                level="error",
                message="请先获取有效的题目信息。",
            )
            st.rerun()
        if send_selected_cases and not selected_case_ids:
            finish_ai_diagnosis(
                st.session_state,
                level="error",
                message="请先选择至少一个测试点，或关闭测试点详情发送选项。",
            )
            st.rerun()
        st.session_state["ai_diagnosis_future"] = _DIAGNOSIS_EXECUTOR.submit(
            _perform_diagnosis,
            problem,
            source_code,
            api_key,
            settings,
            oj_evidence,
            selected_case_ids if send_selected_cases else (),
        )
        st.session_state["ai_diagnosis_running"] = True
        if not diagnosis_running:
            with progress_slot.container():
                _render_diagnosis_progress()

    diagnosis = st.session_state.get("ai_code_diagnosis")
    if isinstance(diagnosis, AICodeDiagnosis):
        with report_slot.container():
            render_ai_diagnosis(
                diagnosis,
                has_oj_evidence=bool(
                    st.session_state.get("ai_diagnosis_has_oj_evidence")
                ),
            )


@st.fragment(run_every=0.75)
def _render_diagnosis_progress() -> None:
    """Poll only while a diagnosis is active; stop after one full rerun."""

    if _finish_background_diagnosis_if_ready():
        st.rerun()
    st.info("模型正在分析题目和代码，请勿重复点击…")


def _perform_diagnosis(
    problem: ImportedProblem,
    source_code: str,
    api_key: str,
    settings: AppSettings,
    oj_evidence: VesibaySubmissionEvidence | None,
    selected_case_ids: tuple[str, ...],
) -> tuple[AICodeDiagnosis, VesibaySubmissionEvidence | None]:
    updated_evidence = oj_evidence
    if updated_evidence is not None and selected_case_ids:
        updated_evidence = run_selected_testcases(
            updated_evidence,
            selected_case_ids,
        )
    diagnosis = diagnose_code(
        problem,
        source_code,
        api_key=api_key,
        settings=settings,
        oj_evidence=updated_evidence,
        selected_case_ids=selected_case_ids,
    )
    return diagnosis, updated_evidence


def _finish_background_diagnosis_if_ready(
    state: MutableMapping[str, Any] | None = None,
) -> bool:
    session = st.session_state if state is None else state
    future = session.get("ai_diagnosis_future")
    if not isinstance(future, Future) or not future.done():
        return False
    session.pop("ai_diagnosis_future", None)
    try:
        diagnosis, updated_evidence = future.result()
    except (AIDiagnosisError, SelectedCaseExecutionError) as exc:
        finish_ai_diagnosis(
            session,
            level="error",
            message=str(exc),
        )
    except Exception:
        finish_ai_diagnosis(
            session,
            level="error",
            message="诊断过程中发生内部错误，请稍后重试。",
        )
    else:
        if updated_evidence is not None:
            session["vesibay_submission_evidence"] = updated_evidence
        session["ai_code_diagnosis"] = diagnosis
        session["ai_diagnosis_has_oj_evidence"] = (
            updated_evidence is not None
        )
        finish_ai_diagnosis(
            session,
            level="success",
            message="AI诊断完成。",
        )
    return True
