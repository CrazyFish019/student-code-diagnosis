from pathlib import Path

from core.config import resolve_user_data_root
from core import runtime_storage


def test_windows_user_data_root_uses_local_appdata() -> None:
    root = resolve_user_data_root(
        {"LOCALAPPDATA": r"C:\Users\Teacher\AppData\Local"},
        home=Path(r"C:\Users\Teacher"),
        platform_name="nt",
    )

    assert root == Path(r"C:\Users\Teacher\AppData\Local\StudentCodeDiagnosis")


def test_user_data_root_supports_explicit_override(tmp_path) -> None:
    expected = tmp_path / "portable-data"

    root = resolve_user_data_root(
        {"STUDENT_CODE_DIAGNOSIS_HOME": str(expected)},
        home=tmp_path,
        platform_name="nt",
    )

    assert root == expected.resolve()


def test_legacy_runtime_data_is_moved_without_overwriting(tmp_path, monkeypatch) -> None:
    legacy_config = tmp_path / "legacy" / "config"
    legacy_data = tmp_path / "legacy" / "data"
    config = tmp_path / "current" / "config"
    data = tmp_path / "current" / "data"
    temporary = tmp_path / "current" / "temp"
    legacy_config.mkdir(parents=True)
    (legacy_config / "settings.json").write_text("legacy", encoding="utf-8")
    (legacy_config / "secrets.json").write_text("protected", encoding="utf-8")
    legacy_data.mkdir(parents=True)
    (legacy_data / "diagnosis.db").write_bytes(b"database")
    (legacy_data / "tasks").mkdir()
    (legacy_data / "tasks" / "one.json").write_text("{}", encoding="utf-8")
    config.mkdir(parents=True)
    (config / "settings.json").write_text("current", encoding="utf-8")

    monkeypatch.setattr(runtime_storage, "LEGACY_CONFIG_DIR", legacy_config)
    monkeypatch.setattr(runtime_storage, "LEGACY_DATA_DIR", legacy_data)
    monkeypatch.setattr(runtime_storage, "CONFIG_DIR", config)
    monkeypatch.setattr(runtime_storage, "DATA_DIR", data)
    monkeypatch.setattr(runtime_storage, "TEMP_DIR", temporary)

    assert runtime_storage.migrate_legacy_runtime_data() == ()
    assert (config / "settings.json").read_text(encoding="utf-8") == "current"
    assert (config / "secrets.json").read_text(encoding="utf-8") == "protected"
    assert (data / "diagnosis.db").read_bytes() == b"database"
    assert (data / "tasks" / "one.json").is_file()
    assert temporary.is_dir()
