import json

from services.settings_service import AppSettings, SettingsService


def test_first_load_creates_new_ai_defaults(tmp_path) -> None:
    path = tmp_path / "config" / "settings.json"

    settings = SettingsService(path).load()

    assert settings == AppSettings()
    assert settings.model == "deepseek-v4-flash"
    assert settings.thinking_mode == "disabled"
    assert settings.request_timeout_seconds == 300
    assert settings.max_output_tokens == 12000
    assert path.is_file()


def test_read_and_save_existing_model_settings_without_api_key(tmp_path) -> None:
    path = tmp_path / "settings.json"
    service = SettingsService(path)
    expected = AppSettings(
        provider="openai_compatible",
        base_url="https://models.example/v1",
        model="teacher-model",
        thinking_mode="enabled",
        request_timeout_seconds=90,
        max_output_tokens=3000,
    )
    service.save(expected)

    payload = json.loads(path.read_text(encoding="utf-8"))
    assert service.load() == expected
    assert "api_key" not in payload


def test_corrupt_or_legacy_settings_restore_ai_defaults(tmp_path) -> None:
    path = tmp_path / "settings.json"
    path.write_text('{"compiler":"g++"}', encoding="utf-8")

    settings = SettingsService(path).load()

    assert settings == AppSettings()
    assert json.loads(path.read_text(encoding="utf-8"))["provider"] == "deepseek"
