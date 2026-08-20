"""Common OpenAI-compatible model settings and protected API-key storage."""

from __future__ import annotations

import os

import streamlit as st

from services.ai_code_diagnosis_service import AIDiagnosisError, test_model_connection
from services.credential_service import CredentialService
from services.secret_store import SecretStoreError
from services.settings_service import AppSettings, SettingsService


_SERVICE_PRESETS: dict[str, tuple[str, str | None]] = {
    "DeepSeek": ("deepseek", "https://api.deepseek.com"),
    "OpenAI": ("openai_compatible", "https://api.openai.com/v1"),
    "通义千问（兼容模式）": (
        "openai_compatible",
        "https://dashscope.aliyuncs.com/compatible-mode/v1",
    ),
    "Kimi（月之暗面）": ("openai_compatible", "https://api.moonshot.cn/v1"),
    "智谱GLM": ("openai_compatible", "https://open.bigmodel.cn/api/paas/v4"),
    "硅基流动": ("openai_compatible", "https://api.siliconflow.cn/v1"),
    "Google Gemini（兼容模式）": (
        "openai_compatible",
        "https://generativelanguage.googleapis.com/v1beta/openai",
    ),
    "自定义OpenAI兼容服务": ("openai_compatible", None),
}


def _infer_service_preset(settings: AppSettings) -> str:
    if settings.provider == "deepseek":
        return "DeepSeek"
    normalized = settings.base_url.rstrip("/")
    for label, (_, base_url) in _SERVICE_PRESETS.items():
        if base_url and normalized == base_url.rstrip("/"):
            return label
    return "自定义OpenAI兼容服务"


def _apply_service_preset() -> None:
    label = st.session_state["model_service_preset"]
    base_url = _SERVICE_PRESETS[label][1]
    if base_url:
        st.session_state["model_base_url"] = base_url


def render_model_settings() -> tuple[AppSettings, str]:
    service = SettingsService()
    credential_service = CredentialService()
    stored = service.load()
    if "model_api_key" not in st.session_state:
        try:
            saved_api_key = credential_service.load_model_api_key()
        except (SecretStoreError, OSError, ValueError):
            saved_api_key = ""
        st.session_state["model_api_key"] = os.environ.get(
            "MODEL_API_KEY", os.environ.get("DEEPSEEK_API_KEY", saved_api_key)
        )
    st.session_state.setdefault("model_service_preset", _infer_service_preset(stored))
    st.session_state.setdefault("model_base_url", stored.base_url)
    st.session_state.setdefault("model_name", stored.model)
    with st.sidebar:
        st.divider()
        st.header("模型设置")
        provider_label = st.selectbox(
            "API格式/服务",
            list(_SERVICE_PRESETS),
            key="model_service_preset",
            on_change=_apply_service_preset,
            help="这些服务使用OpenAI兼容的chat/completions格式；也可填写自定义地址。",
        )
        base_url = st.text_input("API基础地址", key="model_base_url")
        model = st.text_input("模型名称", key="model_name")
        api_key = st.text_input(
            "API Key",
            type="password",
            key="model_api_key",
            help="保存后使用Windows当前用户保护机制加密存放在本机。",
        )
        modes = {"非思考模式": "disabled", "思考模式": "enabled"}
        current_mode = next(k for k, v in modes.items() if v == stored.thinking_mode)
        mode_label = st.selectbox(
            "模型模式",
            list(modes),
            index=list(modes).index(current_mode),
            help="DeepSeek请求会显式发送thinking开关。",
        )
        timeout = st.number_input(
            "请求超时（秒）", min_value=5, max_value=600, value=stored.request_timeout_seconds
        )
        max_tokens = st.number_input(
            "最大输出Token",
            min_value=500,
            max_value=20_000,
            value=stored.max_output_tokens,
            step=500,
        )
        try:
            settings = AppSettings(
                provider=_SERVICE_PRESETS[provider_label][0],
                base_url=base_url.strip(),
                model=model.strip(),
                thinking_mode=modes[mode_label],
                request_timeout_seconds=int(timeout),
                max_output_tokens=int(max_tokens),
            )
        except ValueError as exc:
            st.warning(f"模型设置无效：{exc}")
            settings = stored
        save_col, test_col, clear_col = st.columns(3)
        if save_col.button("保存设置"):
            try:
                service.save(settings)
                if api_key.strip():
                    credential_service.save_model_api_key(api_key)
                st.success("模型设置和API Key已保存到本机。")
            except (OSError, SecretStoreError, ValueError):
                st.warning("模型设置或API Key无法保存。")
        if test_col.button("测试连接"):
            try:
                with st.spinner("正在测试模型连接…"):
                    test_model_connection(api_key=api_key, settings=settings)
                st.success("模型连接成功。")
            except AIDiagnosisError as exc:
                st.warning(str(exc))
        if clear_col.button("清除Key"):
            try:
                credential_service.clear_model_api_key()
                st.session_state["model_api_key"] = ""
                st.success("本地API Key已清除。")
                st.rerun()
            except (OSError, SecretStoreError):
                st.warning("本地API Key无法清除。")
        st.caption("题目和代码会发送给所配置的第三方模型服务。")
    return settings, api_key
