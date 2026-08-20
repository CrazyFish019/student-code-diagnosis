"""Create per-user storage and migrate data from pre-1.0 source layouts."""

from __future__ import annotations

import shutil
import os
from pathlib import Path

from core.config import (
    CONFIG_DIR,
    DATA_DIR,
    LEGACY_CONFIG_DIR,
    LEGACY_DATA_DIR,
    TEMP_DIR,
)


def ensure_runtime_directories() -> None:
    for directory in (CONFIG_DIR, DATA_DIR, TEMP_DIR):
        directory.mkdir(parents=True, exist_ok=True)


def migrate_legacy_runtime_data() -> tuple[str, ...]:
    """Move legacy mutable files when the per-user destination is still empty.

    Existing destination files always win, so an update can never overwrite a
    newer local setting or database. Failures are returned for the UI to report
    and do not prevent the application from starting.
    """

    if any(
        os.environ.get(name)
        for name in (
            "STUDENT_CODE_DIAGNOSIS_SETTINGS_PATH",
            "STUDENT_CODE_DIAGNOSIS_SECRET_PATH",
            "STUDENT_CODE_DIAGNOSIS_DATA_DIR",
        )
    ):
        return ()
    ensure_runtime_directories()
    warnings: list[str] = []
    for source, destination in (
        (LEGACY_CONFIG_DIR / "settings.json", CONFIG_DIR / "settings.json"),
        (LEGACY_CONFIG_DIR / "secrets.json", CONFIG_DIR / "secrets.json"),
        (LEGACY_DATA_DIR / "diagnosis.db", DATA_DIR / "diagnosis.db"),
    ):
        _move_if_destination_missing(source, destination, warnings)
    _move_if_destination_missing(
        LEGACY_DATA_DIR / "tasks", DATA_DIR / "tasks", warnings
    )
    return tuple(warnings)


def _move_if_destination_missing(
    source: Path, destination: Path, warnings: list[str]
) -> None:
    if not source.exists() or destination.exists():
        return
    try:
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(source), str(destination))
    except OSError:
        warnings.append(f"无法迁移旧版数据：{source.name}")
