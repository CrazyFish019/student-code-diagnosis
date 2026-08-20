"""Local JSON settings independent from Streamlit and SQLite."""

from __future__ import annotations

import json
import os
import tempfile
from dataclasses import asdict, dataclass
from pathlib import Path
from urllib.parse import urlparse

from core.config import CONFIG_DIR


@dataclass(frozen=True, slots=True)
class AppSettings:
    provider: str = "deepseek"
    base_url: str = "https://api.deepseek.com"
    model: str = "deepseek-v4-flash"
    thinking_mode: str = "disabled"
    request_timeout_seconds: int = 300
    max_output_tokens: int = 12_000

    def __post_init__(self) -> None:
        if self.provider not in {"deepseek", "openai_compatible"}:
            raise ValueError("provider is invalid")
        for field_name in ("base_url", "model"):
            value = getattr(self, field_name)
            if not isinstance(value, str) or not value.strip():
                raise ValueError(f"{field_name} must be non-empty")
        parsed = urlparse(self.base_url)
        if parsed.scheme not in {"http", "https"} or not parsed.netloc:
            raise ValueError("base_url must be an HTTP(S) URL")
        if self.thinking_mode not in {"disabled", "enabled"}:
            raise ValueError("thinking_mode is invalid")
        for field_name in ("request_timeout_seconds", "max_output_tokens"):
            value = getattr(self, field_name)
            if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
                raise ValueError(f"{field_name} must be positive")


class SettingsService:
    def __init__(self, path: str | Path | None = None) -> None:
        override = os.environ.get("STUDENT_CODE_DIAGNOSIS_SETTINGS_PATH")
        self.path = Path(path or override or CONFIG_DIR / "settings.json")

    def load(self) -> AppSettings:
        if not self.path.exists():
            settings = AppSettings()
            self._try_save_default(settings)
            return settings
        try:
            payload = json.loads(self.path.read_text(encoding="utf-8"))
            if not isinstance(payload, dict):
                raise ValueError("settings root must be an object")
            return AppSettings(**payload)
        except (OSError, UnicodeError, json.JSONDecodeError, TypeError, ValueError):
            settings = AppSettings()
            self._try_save_default(settings)
            return settings

    def save(self, settings: AppSettings) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        descriptor, temporary_name = tempfile.mkstemp(
            prefix=".settings-", suffix=".json", dir=self.path.parent
        )
        try:
            with os.fdopen(descriptor, "w", encoding="utf-8", newline="\n") as file:
                json.dump(asdict(settings), file, ensure_ascii=False, indent=2)
                file.write("\n")
            os.replace(temporary_name, self.path)
        except Exception:
            try:
                Path(temporary_name).unlink(missing_ok=True)
            except OSError:
                pass
            raise

    def _try_save_default(self, settings: AppSettings) -> None:
        try:
            self.save(settings)
        except OSError:
            pass
