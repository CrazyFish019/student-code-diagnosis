"""Version and GitHub Release update controls."""

from __future__ import annotations

import streamlit as st

from core.version import UPDATE_REPOSITORY, __version__
from services.update_service import UpdateCheckError, UpdateInfo, check_for_updates


def render_update_view() -> None:
    with st.sidebar:
        st.divider()
        st.caption(f"学生代码诊断助手 v{__version__}")
        if not UPDATE_REPOSITORY:
            st.caption("正式发布后可在此检查更新。")
            return
        if st.button("检查更新", key="check_for_application_updates"):
            try:
                with st.spinner("正在检查更新…"):
                    st.session_state["application_update_info"] = check_for_updates()
                st.session_state.pop("application_update_error", None)
            except UpdateCheckError as exc:
                st.session_state["application_update_error"] = str(exc)
                st.session_state.pop("application_update_info", None)
        error = st.session_state.get("application_update_error")
        if isinstance(error, str):
            st.warning(error)
        info = st.session_state.get("application_update_info")
        if not isinstance(info, UpdateInfo):
            return
        if not info.update_available:
            st.success("当前已经是最新版本。")
            return
        st.info(f"发现新版本 v{info.latest_version}。")
        st.link_button(
            "下载更新",
            info.installer_url or info.release_url,
            use_container_width=True,
        )
