"""Bounded binary HTTP transport for authorized testcase archives."""

from __future__ import annotations

import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Protocol


class BinaryNetworkError(RuntimeError):
    """A binary HTTP response could not be downloaded safely."""


@dataclass(frozen=True, slots=True)
class BinaryHttpResponse:
    status_code: int
    headers: dict[str, str]
    body: bytes


class BinaryHttpTransport(Protocol):
    def request(
        self,
        method: str,
        url: str,
        *,
        headers: dict[str, str] | None = None,
        timeout_seconds: int = 60,
    ) -> BinaryHttpResponse: ...


class _NoRedirectHandler(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


class UrllibBinaryHttpTransport:
    def __init__(self, *, max_response_bytes: int = 64 * 1024 * 1024) -> None:
        self._max_response_bytes = max_response_bytes
        self._opener = urllib.request.build_opener(_NoRedirectHandler())

    def request(
        self,
        method: str,
        url: str,
        *,
        headers: dict[str, str] | None = None,
        timeout_seconds: int = 60,
    ) -> BinaryHttpResponse:
        request = urllib.request.Request(
            url,
            headers={"Accept": "application/octet-stream, application/zip", **(headers or {})},
            method=method.upper(),
        )
        try:
            with self._opener.open(request, timeout=timeout_seconds) as response:
                body = response.read(self._max_response_bytes + 1)
                if len(body) > self._max_response_bytes:
                    raise BinaryNetworkError("测试数据下载超过大小限制。")
                return BinaryHttpResponse(
                    response.status,
                    dict(response.headers.items()),
                    body,
                )
        except urllib.error.HTTPError as exc:
            return BinaryHttpResponse(
                exc.code,
                dict(exc.headers.items()) if exc.headers else {},
                b"",
            )
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            raise BinaryNetworkError("测试数据下载失败或超时。") from exc
