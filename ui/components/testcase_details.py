"""Collapsed, selectable OJ testcase cards and local-only detail dialogs."""

from __future__ import annotations

import re

import streamlit as st

from models.vesibay_submission import OJCaseEvidence
from services.runtime_error_explainer import runtime_error_causes
from ui.state import consume_testcase_details_open, keep_testcase_details_open


_STATUS_VIEW = {
    "AC": ("AC", "success"),
    "WA": ("WA", "error"),
    "RE": ("RE", "error"),
    "TLE": ("TLE", "error"),
}
_INLINE_PREVIEW_CHARACTERS = 20_000


def status_card_view(status: str) -> tuple[str, str]:
    return _STATUS_VIEW.get(status, (status or "?", "error"))


def detail_tab_labels(
    status: str, has_local_execution: bool = False
) -> tuple[str, ...]:
    if status == "WA":
        base = ("输入数据", "标准输出")
        return base + (("学生实际输出",) if has_local_execution else ())
    if status == "RE":
        base = ("运行错误", "输入数据", "标准输出")
        return base + (("本地运行",) if has_local_execution else ())
    return ()


def case_selection_key(submission_id: str, index: int, case_id: str) -> str:
    safe_submission = re.sub(r"[^A-Za-z0-9_-]", "_", submission_id)
    safe_case = re.sub(r"[^A-Za-z0-9_-]", "_", case_id)
    return f"oj_case_selected_{safe_submission}_{index}_{safe_case}"


def render_testcase_details(
    cases: tuple[OJCaseEvidence, ...], submission_id: str
) -> tuple[str, ...]:
    st.session_state.setdefault("selected_oj_case_ids", ())
    with st.expander(
        "测试点详情",
        expanded=consume_testcase_details_open(st.session_state),
    ):
        st.caption("右上角复选框用于选择；点击WA或RE方块可查看详情。")
        _render_card_styles()
        columns = st.columns(min(8, max(1, len(cases))))
        selected = set(st.session_state["selected_oj_case_ids"])
        selected_after_render: list[str] = []
        detail_to_show: tuple[OJCaseEvidence, int] | None = None
        for index, case in enumerate(cases):
            label, tone = status_card_view(case.status)
            checkbox_key = case_selection_key(submission_id, index, case.case_id)
            if checkbox_key not in st.session_state:
                st.session_state[checkbox_key] = case.case_id in selected
            selected_class = "selected" if st.session_state[checkbox_key] else "normal"
            with columns[index % len(columns)]:
                with st.container(key=f"case_card_{tone}_{selected_class}_{index}"):
                    checked = st.checkbox(
                        "",
                        key=checkbox_key,
                        label_visibility="collapsed",
                        on_change=keep_testcase_details_open,
                        args=(st.session_state,),
                    )
                    if checked:
                        selected_after_render.append(case.case_id)
                    if st.button(
                        label,
                        key=f"oj_case_button_{submission_id}_{index}_{case.case_id}",
                        use_container_width=True,
                        on_click=keep_testcase_details_open,
                        args=(st.session_state,),
                    ):
                        if case.status in {"WA", "RE"}:
                            detail_to_show = (case, index)
                st.caption(f"测试点 {index + 1}")

        st.session_state["selected_oj_case_ids"] = tuple(selected_after_render)
        if detail_to_show is not None:
            _show_testcase_dialog(*detail_to_show)
        if not cases:
            st.info("该提交没有可显示的测试点记录。")
    return tuple(st.session_state.get("selected_oj_case_ids", ()))


def render_source_code(source_code: str) -> None:
    with st.expander("学生源码", expanded=False):
        st.code(source_code, language="cpp", line_numbers=True)


@st.dialog("测试点详情")
def _show_testcase_dialog(case: OJCaseEvidence, index: int) -> None:
    st.markdown(f"**测试点 {index + 1} · {case.status}**")
    has_local_execution = case.local_execution_status is not None
    if case.status == "WA":
        tabs = st.tabs(detail_tab_labels(case.status, has_local_execution))
        input_tab, expected_tab = tabs[:2]
        with input_tab:
            _render_text_content(
                case.input_data,
                empty_label="（空输入）",
                filename=f"testcase_{index + 1}.in",
                key=f"download_case_input_{index}",
            )
        with expected_tab:
            _render_text_content(
                case.expected_output,
                empty_label="（空输出）",
                filename=f"testcase_{index + 1}.out",
                key=f"download_case_expected_{index}",
            )
        if has_local_execution:
            with tabs[2]:
                _render_local_execution(case, index)
    elif case.status == "RE":
        tabs = st.tabs(detail_tab_labels(case.status, has_local_execution))
        error_tab, input_tab, expected_tab = tabs[:3]
        with error_tab:
            raw_message = case.error_message or "程序以非零状态结束。"
            st.error(raw_message)
            st.markdown("**可能原因**")
            for cause in runtime_error_causes(raw_message):
                st.markdown(f"- {cause}")
        with input_tab:
            _render_text_content(
                case.input_data,
                empty_label="（空输入）",
                filename=f"testcase_{index + 1}.in",
                key=f"download_re_case_input_{index}",
            )
        with expected_tab:
            _render_text_content(
                case.expected_output,
                empty_label="（空输出）",
                filename=f"testcase_{index + 1}.out",
                key=f"download_re_case_expected_{index}",
            )
        if has_local_execution:
            with tabs[3]:
                _render_local_execution(case, index)
    if st.button("关闭", key=f"close_oj_case_dialog_{index}"):
        st.rerun()


def _render_text_content(
    value: str,
    *,
    empty_label: str,
    filename: str,
    key: str,
) -> None:
    if not value:
        st.code(empty_label, language="text")
        return
    if len(value) <= _INLINE_PREVIEW_CHARACTERS:
        st.code(value, language="text")
        return
    st.warning(
        f"内容共 {len(value):,} 个字符，页面仅预览前 "
        f"{_INLINE_PREVIEW_CHARACTERS:,} 个字符。"
    )
    st.code(value[:_INLINE_PREVIEW_CHARACTERS] + "\n……（预览已截断）", language="text")
    st.download_button(
        "下载完整内容",
        data=value.encode("utf-8"),
        file_name=filename,
        mime="text/plain; charset=utf-8",
        key=key,
    )


def _render_local_execution(case: OJCaseEvidence, index: int) -> None:
    assert case.local_execution_status is not None
    st.caption(
        f"本地状态：{case.local_execution_status.value} · "
        f"耗时：{case.local_execution_time_ms} ms · "
        f"退出码：{case.local_exit_code if case.local_exit_code is not None else '-'}"
    )
    _render_text_content(
        case.locally_captured_stdout or "",
        empty_label="（空输出）",
        filename=f"testcase_{index + 1}_local_stdout.txt",
        key=f"download_case_local_stdout_{index}",
    )
    if case.locally_captured_stderr:
        st.markdown("**标准错误**")
        _render_text_content(
            case.locally_captured_stderr,
            empty_label="（空）",
            filename=f"testcase_{index + 1}_local_stderr.txt",
            key=f"download_case_local_stderr_{index}",
        )
    if case.local_error_message:
        st.warning(case.local_error_message)


def _render_card_styles() -> None:
    st.markdown(
        """
        <style>
        div[class*="st-key-case_card_"] button {
            aspect-ratio: 1 / 1;
            min-height: 58px;
            border-width: 2px;
            border-style: solid;
            border-radius: 8px;
            font-size: 1.1rem;
            font-weight: 700;
            padding: 0;
        }
        div[class*="st-key-case_card_"] {
            position: relative;
        }
        div[class*="st-key-case_card_"] [data-testid="stCheckbox"] {
            position: absolute;
            right: 0.2rem;
            top: 0.2rem;
            width: auto;
            z-index: 5;
        }
        div[class*="st-key-case_card_"] [data-testid="stCheckbox"] label {
            padding: 0;
        }
        div[class*="st-key-case_card_success_"] button {
            border-color: #18864b;
            color: #18864b;
        }
        div[class*="st-key-case_card_error_"] button {
            border-color: #d32f2f;
            color: #d32f2f;
        }
        div[class*="st-key-case_card_"][class*="_selected_"] button {
            background: rgba(66, 133, 244, 0.14);
            box-shadow: 0 0 0 3px rgba(66, 133, 244, 0.28);
        }
        </style>
        """,
        unsafe_allow_html=True,
    )
