"""Vesibay administrator credential settings."""

from __future__ import annotations

import streamlit as st

from services.credential_service import CredentialService
from services.secret_store import SecretStoreError
from services.vesibay_readonly_client import (
    VesibayAccessError,
    VesibayCredentials,
    VesibayReadOnlyClient,
)


def render_vesibay_settings() -> VesibayCredentials | None:
    service = CredentialService()
    if "vesibay_username" not in st.session_state:
        try:
            saved = service.load_vesibay_credentials()
        except (SecretStoreError, OSError, ValueError):
            saved = None
        st.session_state["vesibay_username"] = saved.username if saved else ""
        st.session_state["vesibay_password"] = saved.password if saved else ""

    with st.sidebar:
        st.divider()
        st.header("网站只读访问")
        username = st.text_input("网站用户名", key="vesibay_username")
        password = st.text_input(
            "网站密码",
            type="password",
            key="vesibay_password",
            help="使用Windows当前用户保护机制加密存放；不会保存登录令牌。",
        )
        save_col, clear_col = st.columns(2)
        if save_col.button("验证并保存网站账号"):
            try:
                credentials = VesibayCredentials(username, password)
                with st.spinner("正在验证只读访问…"):
                    VesibayReadOnlyClient().verify_credentials(credentials)
                service.save_vesibay_credentials(credentials)
                st.success("网站账号验证成功并已保存。")
            except (ValueError, VesibayAccessError) as exc:
                st.warning(str(exc))
            except (SecretStoreError, OSError):
                st.warning("网站账号无法保存到本机。")
        if clear_col.button("清除网站账号"):
            try:
                service.clear_vesibay_credentials()
                st.session_state["vesibay_username"] = ""
                st.session_state["vesibay_password"] = ""
                st.success("本地网站账号已清除。")
                st.rerun()
            except (SecretStoreError, OSError):
                st.warning("本地网站账号无法清除。")
        st.caption("程序只调用登录、身份、提交、测试点和题目读取接口。")

    try:
        return VesibayCredentials(username, password)
    except ValueError:
        return None
