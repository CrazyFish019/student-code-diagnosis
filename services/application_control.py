"""Authenticated local control requests for the packaged desktop launcher."""

from __future__ import annotations

import os
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


_TOKEN_HEADER = "X-Student-Code-Diagnosis-Token"


class ApplicationControlError(RuntimeError):
    """Raised when the local desktop launcher cannot process a request."""


def application_shutdown_available() -> bool:
    return bool(
        os.environ.get("STUDENT_CODE_DIAGNOSIS_CONTROL_URL", "").strip()
        and os.environ.get("STUDENT_CODE_DIAGNOSIS_CONTROL_TOKEN", "").strip()
    )


def request_application_shutdown(*, timeout_seconds: float = 2.0) -> None:
    base_url = os.environ.get("STUDENT_CODE_DIAGNOSIS_CONTROL_URL", "").strip()
    token = os.environ.get("STUDENT_CODE_DIAGNOSIS_CONTROL_TOKEN", "").strip()
    if not base_url or not token:
        raise ApplicationControlError("当前启动方式不支持从页面退出程序。")
    request = Request(
        f"{base_url.rstrip('/')}/shutdown",
        method="POST",
        headers={_TOKEN_HEADER: token},
    )
    try:
        with urlopen(request, timeout=timeout_seconds) as response:
            if response.status != 202:
                raise ApplicationControlError("本地启动器未接受退出请求。")
    except (HTTPError, URLError, OSError) as exc:
        raise ApplicationControlError("无法连接本地启动器，请从系统托盘退出。") from exc
