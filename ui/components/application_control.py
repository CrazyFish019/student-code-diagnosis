"""Desktop lifecycle controls shown only in packaged launcher sessions."""

from __future__ import annotations

import streamlit as st

from services.application_control import (
    ApplicationControlError,
    application_shutdown_available,
    request_application_shutdown,
)


def render_application_control(*, diagnosis_active: bool) -> None:
    if not application_shutdown_available():
        return
    with st.sidebar:
        st.divider()
        st.caption("关闭网页不会退出后台程序，也可以从任务栏托盘退出。")
        if st.button(
            "退出诊断工具",
            use_container_width=True,
            disabled=diagnosis_active,
            help=(
                "请等待当前诊断完成后再退出。"
                if diagnosis_active
                else "关闭网页和本地后台服务。"
            ),
        ):
            try:
                request_application_shutdown()
            except ApplicationControlError as exc:
                st.error(str(exc))
            else:
                st.success("正在退出诊断工具，可以关闭此页面。")
