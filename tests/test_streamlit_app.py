"""Browser-free smoke tests for the simplified AI diagnosis page."""

from concurrent.futures import Future
from pathlib import Path

from streamlit.testing.v1 import AppTest

from models.ai_code_diagnosis import AICodeDiagnosis, AIConclusion
from ui.app import _finish_background_diagnosis_if_ready

APP_PATH = Path(__file__).resolve().parents[1] / "app.py"


def configure_settings(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv(
        "STUDENT_CODE_DIAGNOSIS_SETTINGS_PATH",
        str(tmp_path / "config" / "settings.json"),
    )
    monkeypatch.setenv(
        "STUDENT_CODE_DIAGNOSIS_SECRET_PATH",
        str(tmp_path / "config" / "secrets.json"),
    )
    monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)


def test_streamlit_ai_page_opens_without_legacy_judge_inputs(tmp_path, monkeypatch) -> None:
    configure_settings(monkeypatch, tmp_path)

    app = AppTest.from_file(APP_PATH).run(timeout=15)

    assert not app.exception
    assert app.title[0].value == "学生代码AI诊断助手"
    labels = [item.label for item in app.text_input]
    assert "题目网址" in labels
    assert "模型名称" in labels
    assert "API Key" in labels
    assert "网站用户名" in labels
    assert "网站密码" in labels
    assert labels.index("网站用户名") < labels.index("模型名称")
    service_selector = next(
        item for item in app.selectbox if item.label == "API格式/服务"
    )
    assert "OpenAI" in service_selector.options
    assert "通义千问（兼容模式）" in service_selector.options
    assert "Kimi（月之暗面）" in service_selector.options
    assert "自定义OpenAI兼容服务" in service_selector.options
    send_checkbox = next(
        item for item in app.checkbox if item.label == "发送选中的测试点详情给模型"
    )
    assert send_checkbox.value is False
    assert send_checkbox.disabled is True
    assert not any("编译器" in label for label in labels)
    assert any(item.label == "开始AI诊断" for item in app.button)


def test_empty_problem_url_shows_teacher_message_without_network(tmp_path, monkeypatch) -> None:
    configure_settings(monkeypatch, tmp_path)
    app = AppTest.from_file(APP_PATH).run(timeout=15)

    next(item for item in app.button if item.label == "获取题目信息").click().run(timeout=15)

    assert not app.exception
    assert any("请输入题目网址" in item.value for item in app.error)


def test_diagnose_requires_imported_problem(tmp_path, monkeypatch) -> None:
    configure_settings(monkeypatch, tmp_path)
    app = AppTest.from_file(APP_PATH).run(timeout=15)

    next(item for item in app.button if item.label == "开始AI诊断").click().run(timeout=15)

    assert not app.exception
    assert any("请先获取有效的题目信息" in item.value for item in app.error)
    diagnosis_buttons = [item for item in app.button if item.label == "开始AI诊断"]
    assert len(diagnosis_buttons) == 1
    assert diagnosis_buttons[0].disabled is False


def test_running_diagnosis_keeps_one_disabled_button_in_place(
    tmp_path, monkeypatch
) -> None:
    configure_settings(monkeypatch, tmp_path)
    app = AppTest.from_file(APP_PATH).run(timeout=15)

    app.session_state["ai_diagnosis_running"] = True
    app = app.run(timeout=15)

    diagnosis_buttons = [item for item in app.button if item.label == "开始AI诊断"]
    assert len(diagnosis_buttons) == 1
    assert diagnosis_buttons[0].disabled is True
    assert not any(item.label == "诊断进行中…" for item in app.button)
    assert app.radio[0].disabled is True
    import_button = next(item for item in app.button if item.label == "获取题目信息")
    assert import_button.disabled is True


def test_report_section_is_not_configured_for_permanent_auto_refresh() -> None:
    source = (APP_PATH.parent / "ui" / "app.py").read_text(encoding="utf-8")

    assert "@st.fragment(run_every=0.75)\ndef _render_diagnosis_section" not in source
    assert "@st.fragment(run_every=0.75)\ndef _render_diagnosis_progress" in source


def test_completed_background_diagnosis_is_collected_exactly_once() -> None:
    diagnosis = AICodeDiagnosis(
        conclusion=AIConclusion.UNCERTAIN,
        summary="需要结合更多数据判断。",
        categories=("uncertain",),
        root_cause="证据不足。",
        evidence=(),
        sample_analysis=(),
        suggestions=("补充测试数据。",),
        teacher_feedback="建议人工复核。",
        student_feedback="请补充更多测试。",
        confidence=0.5,
        limitations=("仅供教学参考。",),
    )
    future: Future[tuple[AICodeDiagnosis, None]] = Future()
    future.set_result((diagnosis, None))
    state: dict[str, object] = {
        "ai_diagnosis_future": future,
        "ai_diagnosis_running": True,
    }

    assert _finish_background_diagnosis_if_ready(state) is True
    assert state["ai_code_diagnosis"] is diagnosis
    assert state["ai_diagnosis_running"] is False
    assert "ai_diagnosis_future" not in state
    assert _finish_background_diagnosis_if_ready(state) is False


def test_submission_mode_requires_saved_website_credentials(tmp_path, monkeypatch) -> None:
    configure_settings(monkeypatch, tmp_path)
    app = AppTest.from_file(APP_PATH).run(timeout=15)

    app.radio[0].set_value("提交详情网址").run(timeout=15)
    next(item for item in app.button if item.label == "获取提交信息").click().run(
        timeout=15
    )

    assert not app.exception
    assert any("请先在侧边栏" in item.value for item in app.error)


def test_common_model_preset_updates_compatible_api_base_url(tmp_path, monkeypatch) -> None:
    configure_settings(monkeypatch, tmp_path)
    app = AppTest.from_file(APP_PATH).run(timeout=15)

    selector = next(item for item in app.selectbox if item.label == "API格式/服务")
    selector.set_value("Kimi（月之暗面）").run(timeout=15)

    base_url = next(item for item in app.text_input if item.label == "API基础地址")
    assert base_url.value == "https://api.moonshot.cn/v1"
