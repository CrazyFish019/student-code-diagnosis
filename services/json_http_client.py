"""Small injectable JSON HTTP client used by OJ and model integrations."""

from __future__ import annotations

import json
import http.client
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from typing import Any, Protocol


class NetworkRequestError(RuntimeError):
    """Raised when an HTTP request cannot be completed or decoded."""


@dataclass(frozen=True, slots=True)
class JsonHttpResponse:
    status_code: int
    payload: dict[str, Any]
    headers: dict[str, str] = field(default_factory=dict)


class JsonHttpTransport(Protocol):
    def request_json(
        self,
        method: str,
        url: str,
        *,
        headers: dict[str, str] | None = None,
        payload: dict[str, Any] | None = None,
        timeout_seconds: int = 30,
    ) -> JsonHttpResponse: ...


class _NoRedirectHandler(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


class UrllibJsonHttpTransport:
    def __init__(self, *, max_response_bytes: int = 2 * 1024 * 1024) -> None:
        self._max_response_bytes = max_response_bytes
        self._opener = urllib.request.build_opener(_NoRedirectHandler())

    def request_json(
        self,
        method: str,
        url: str,
        *,
        headers: dict[str, str] | None = None,
        payload: dict[str, Any] | None = None,
        timeout_seconds: int = 30,
    ) -> JsonHttpResponse:
        body = None
        request_headers = {"Accept": "application/json", **(headers or {})}
        if payload is not None:
            body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
            request_headers["Content-Type"] = "application/json; charset=utf-8"
        request = urllib.request.Request(
            url, data=body, headers=request_headers, method=method.upper()
        )
        try:
            with self._opener.open(request, timeout=timeout_seconds) as response:
                return JsonHttpResponse(
                    status_code=response.status,
                    payload=self._read_payload(response),
                    headers=dict(response.headers.items()),
                )
        except urllib.error.HTTPError as exc:
            try:
                response_payload = self._read_payload(exc)
            except NetworkRequestError:
                response_payload = {}
            return JsonHttpResponse(
                exc.code, response_payload, dict(exc.headers.items()) if exc.headers else {}
            )
        except (
            urllib.error.URLError,
            http.client.HTTPException,
            TimeoutError,
            OSError,
        ) as exc:
            raise NetworkRequestError("网络请求失败或超时。") from exc

    def _read_payload(self, response) -> dict[str, Any]:
        raw = response.read(self._max_response_bytes + 1)
        if len(raw) > self._max_response_bytes:
            raise NetworkRequestError("网络响应内容过大。")
        try:
            value = json.loads(raw.decode("utf-8"))
        except (UnicodeError, json.JSONDecodeError) as exc:
            raise NetworkRequestError("服务器返回了无效的JSON。") from exc
        if not isinstance(value, dict):
            raise NetworkRequestError("服务器JSON顶层必须是对象。")
        return value
