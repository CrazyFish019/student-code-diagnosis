"""One-time, read-only Vesibay administrator access verifier.

Credentials and the returned authorization token are kept in memory only.  The
script deliberately prints metadata about sensitive values, never the values
themselves.
"""

from __future__ import annotations

import argparse
import getpass
import json
import ssl
import sys
import urllib.error
import urllib.parse
import urllib.request
from collections.abc import Mapping
from typing import Any


BASE_URL = "https://www.vesibay.cn"
DEFAULT_SUBMISSION_ID = "48543"
REQUEST_TIMEOUT_SECONDS = 20
_HIDDEN_MARKERS = ("not support viewing", "不支持查看", "无权查看")


class VerificationError(RuntimeError):
    """An expected login, permission, network, or response-format failure."""


def _ssl_context(insecure: bool) -> ssl.SSLContext:
    if insecure:
        return ssl._create_unverified_context()  # noqa: SLF001 - explicit test option
    return ssl.create_default_context()


def _read_json_response(response: Any) -> dict[str, Any]:
    raw = response.read()
    try:
        value = json.loads(raw.decode("utf-8", errors="replace"))
    except json.JSONDecodeError as exc:
        raise VerificationError("服务器没有返回有效的 JSON。") from exc
    if not isinstance(value, dict):
        raise VerificationError("服务器返回的数据结构不是 JSON 对象。")
    return value


def _server_message(payload: Mapping[str, Any]) -> str:
    message = payload.get("msg", payload.get("message", ""))
    return str(message).strip() or "服务器拒绝了请求。"


def _request_json(
    path: str,
    *,
    context: ssl.SSLContext,
    method: str = "GET",
    authorization: str | None = None,
    body: Mapping[str, Any] | None = None,
) -> tuple[dict[str, Any], Any]:
    data = None
    headers = {
        "Accept": "application/json",
        "User-Agent": "Student-Code-Diagnosis-ReadOnly-Verifier/1.0",
        "Url-Type": "admin" if path.startswith("/api/admin/") else "general",
    }
    if body is not None:
        data = json.dumps(dict(body), ensure_ascii=False).encode("utf-8")
        headers["Content-Type"] = "application/json; charset=utf-8"
    if authorization:
        headers["Authorization"] = authorization

    request = urllib.request.Request(
        BASE_URL + path,
        data=data,
        headers=headers,
        method=method,
    )
    try:
        response = urllib.request.urlopen(  # noqa: S310 - fixed trusted host
            request,
            context=context,
            timeout=REQUEST_TIMEOUT_SECONDS,
        )
        payload = _read_json_response(response)
    except urllib.error.HTTPError as exc:
        try:
            payload = _read_json_response(exc)
            message = _server_message(payload)
        except VerificationError:
            message = "服务器拒绝了请求。"
        raise VerificationError(f"HTTP {exc.code}：{message}") from exc
    except urllib.error.URLError as exc:
        raise VerificationError(f"网络连接失败：{exc.reason}") from exc
    except TimeoutError as exc:
        raise VerificationError("请求超时。") from exc

    api_status = payload.get("status", payload.get("code", 200))
    if api_status != 200:
        raise VerificationError(f"API {api_status}：{_server_message(payload)}")
    return payload, response.headers


def _has_visible_value(value: Any) -> bool:
    if value is None or str(value) == "":
        return False
    lowered = str(value).lower()
    return not any(marker in lowered for marker in _HIDDEN_MARKERS)


def _mapping(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def _print_submission_summary(payload: Mapping[str, Any]) -> None:
    data = _mapping(payload.get("data"))
    submission = _mapping(data.get("submission"))
    if not submission:
        raise VerificationError("响应中没有 submission 对象。")

    print("\n[提交详情]")
    print(f"字段数量：{len(submission)}")
    print(f"源码可见：{_has_visible_value(submission.get('code'))}")
    print(f"错误信息可见：{_has_visible_value(submission.get('errorMessage'))}")
    print(f"IP 字段有值：{_has_visible_value(submission.get('ip'))}")
    print(
        "vjudgePassword 字段有值："
        f"{_has_visible_value(submission.get('vjudgePassword'))}"
    )
    if _has_visible_value(submission.get("code")):
        print(f"源码长度：{len(str(submission['code']))} 字符（内容未输出）")


def _content_stats(cases: list[Any], field: str) -> tuple[int, int]:
    values = [item.get(field) for item in cases if isinstance(item, dict)]
    visible = [str(value) for value in values if _has_visible_value(value)]
    return len(visible), max((len(value) for value in visible), default=0)


def _print_case_summary(payload: Mapping[str, Any]) -> None:
    data = _mapping(payload.get("data"))
    cases = _list(data.get("judgeCaseList"))

    print("\n[测试点结果]")
    print(f"测试点数量：{len(cases)}")
    for field, label in (
        ("inputData", "输入数据"),
        ("outputData", "标准输出"),
        ("userOutput", "用户输出"),
    ):
        count, maximum = _content_stats(cases, field)
        print(f"{label}：{count} 项可见，最大长度 {maximum}（内容未输出）")


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="使用 Vesibay 管理员登录态，只读验证提交字段的可见性。"
    )
    parser.add_argument(
        "--submission-id",
        default=DEFAULT_SUBMISSION_ID,
        help=f"待验证的数字提交 ID（默认：{DEFAULT_SUBMISSION_ID}）",
    )
    parser.add_argument(
        "--insecure",
        action="store_true",
        help="仅在本机证书握手失败时跳过 TLS 证书校验。",
    )
    args = parser.parse_args()
    if not str(args.submission_id).isdigit():
        parser.error("--submission-id 只能包含数字。")
    return args


def _configure_console() -> None:
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if reconfigure is not None:
            reconfigure(encoding="utf-8", errors="replace")


def main() -> int:
    _configure_console()
    args = _parse_args()
    if args.insecure:
        print("警告：本次请求不校验 TLS 证书，仅限临时本地验证。")

    username = input("Vesibay 管理员用户名：").strip()
    if not username:
        print("验证失败：用户名不能为空。", file=sys.stderr)
        return 2
    password = getpass.getpass("Vesibay 管理员密码（不会回显）：")
    if not password:
        print("验证失败：密码不能为空。", file=sys.stderr)
        return 2

    authorization: str | None = None
    try:
        context = _ssl_context(args.insecure)
        login_payload, login_headers = _request_json(
            "/api/admin/login",
            context=context,
            method="POST",
            body={"username": username, "password": password},
        )
        authorization = login_headers.get("Authorization")
        if not authorization:
            raise VerificationError("登录成功响应中没有 Authorization 令牌。")

        print("\n管理员登录成功；令牌已保存在当前进程内存中（不会输出或保存）。")
        login_data = _mapping(login_payload.get("data"))
        print(f"登录响应字段：{', '.join(sorted(login_data)) or '无'}")

        auth_payload, _ = _request_json(
            "/api/get-user-auth-info",
            context=context,
            authorization=authorization,
        )
        print(f"身份权限接口：成功（字段数 {len(_mapping(auth_payload.get('data'))) }）")

        encoded_id = urllib.parse.quote(str(args.submission_id), safe="")
        submission_payload, _ = _request_json(
            f"/api/get-submission-detail?submitId={encoded_id}",
            context=context,
            authorization=authorization,
        )
        case_payload, _ = _request_json(
            f"/api/get-all-case-result?submitId={encoded_id}",
            context=context,
            authorization=authorization,
        )
        _print_submission_summary(submission_payload)
        _print_case_summary(case_payload)
        print("\n只读验证完成，没有执行修改操作，也没有保存凭据或响应内容。")
        return 0
    except VerificationError as exc:
        print(f"\n验证失败：{exc}", file=sys.stderr)
        return 1
    finally:
        password = ""
        authorization = None


if __name__ == "__main__":
    raise SystemExit(main())
