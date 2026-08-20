"""Application and per-user filesystem locations."""

import os
from pathlib import Path
from typing import Mapping

PROJECT_ROOT: Path = Path(__file__).resolve().parent.parent
APP_DIRECTORY_NAME = "StudentCodeDiagnosis"


def resolve_user_data_root(
    environment: Mapping[str, str] | None = None,
    *,
    home: Path | None = None,
    platform_name: str | None = None,
) -> Path:
    """Return a writable per-user root without depending on the install path."""

    values = os.environ if environment is None else environment
    override = values.get("STUDENT_CODE_DIAGNOSIS_HOME")
    if override:
        return Path(override).expanduser().resolve()
    platform = os.name if platform_name is None else platform_name
    user_home = Path.home() if home is None else home
    if platform == "nt":
        local_app_data = values.get("LOCALAPPDATA")
        base = Path(local_app_data) if local_app_data else user_home / "AppData" / "Local"
    else:
        base = Path(values.get("XDG_DATA_HOME", user_home / ".local" / "share"))
    return (base / APP_DIRECTORY_NAME).resolve()


USER_DATA_ROOT: Path = resolve_user_data_root()
CONFIG_DIR: Path = USER_DATA_ROOT / "config"
DATA_DIR: Path = USER_DATA_ROOT / "data"
TEMP_DIR: Path = USER_DATA_ROOT / "temp"

LEGACY_CONFIG_DIR: Path = PROJECT_ROOT / "config"
LEGACY_DATA_DIR: Path = PROJECT_ROOT / "data"
