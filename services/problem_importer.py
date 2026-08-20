"""Safe import of public Vesibay problem statements."""

from __future__ import annotations

import html
import re
from urllib.parse import quote, unquote, urlparse

from models.imported_problem import ImportedProblem, ProblemExample
from services.json_http_client import (
    JsonHttpTransport,
    NetworkRequestError,
    UrllibJsonHttpTransport,
)

_PUBLIC_PROBLEM_PATH = re.compile(r"^/problem/([^/]+)/?$")
_TRAINING_PROBLEM_PATH = re.compile(r"^/training/[^/]+/problem/([^/]+)/?$")
_EXAMPLE_PATTERN = re.compile(
    r"<input>(.*?)</input>\s*<output>(.*?)</output>", re.IGNORECASE | re.DOTALL
)


class ProblemImportError(RuntimeError):
    """Teacher-facing failure while importing an OJ statement."""


def import_public_problem(
    url: str,
    *,
    transport: JsonHttpTransport | None = None,
    timeout_seconds: int = 20,
) -> ImportedProblem:
    problem_id = _parse_vesibay_public_url(url)
    return import_vesibay_problem_by_id(
        problem_id,
        source_url=url.strip(),
        transport=transport,
        timeout_seconds=timeout_seconds,
    )


def import_vesibay_problem_by_id(
    problem_id: str,
    *,
    source_url: str,
    authorization: str | None = None,
    transport: JsonHttpTransport | None = None,
    timeout_seconds: int = 20,
) -> ImportedProblem:
    """Import a problem by ID, optionally using an authorized read-only request."""

    if not isinstance(problem_id, str) or not problem_id.strip():
        raise ProblemImportError("题目编号无效。")
    endpoint = (
        "https://www.vesibay.cn/api/get-problem-detail?problemId="
        f"{quote(problem_id.strip(), safe='')}"
    )
    headers = {"Authorization": authorization} if authorization else None
    try:
        response = (transport or UrllibJsonHttpTransport()).request_json(
            "GET", endpoint, headers=headers, timeout_seconds=timeout_seconds
        )
    except NetworkRequestError as exc:
        raise ProblemImportError("题目网站暂时不可用，请稍后重试。") from exc
    if response.status_code != 200:
        raise ProblemImportError("未能获取题目信息。")
    payload = response.payload
    if payload.get("status") != 200:
        raise ProblemImportError(str(payload.get("msg") or "未找到题目信息。"))
    try:
        problem = payload["data"]["problem"]
        if not isinstance(problem, dict):
            raise TypeError
        return ImportedProblem(
            source_url=source_url.strip(),
            oj_name="Vesibay",
            external_problem_id=_required_string(problem, "problemId"),
            title=_required_string(problem, "title"),
            description=_optional_string(problem, "description"),
            input_description=_optional_string(problem, "input"),
            output_description=_optional_string(problem, "output"),
            hint=_optional_string(problem, "hint"),
            time_limit_ms=_positive_integer(problem, "timeLimit"),
            memory_limit_mb=_positive_integer(problem, "memoryLimit"),
            examples=_parse_examples(_optional_string(problem, "examples")),
        )
    except (KeyError, TypeError, ValueError) as exc:
        raise ProblemImportError("题目网站返回的数据格式不完整。") from exc


def _parse_vesibay_public_url(url: str) -> str:
    if not isinstance(url, str) or not url.strip():
        raise ProblemImportError("请输入题目网址。")
    parsed = urlparse(url.strip())
    if parsed.scheme != "https" or parsed.hostname != "www.vesibay.cn":
        raise ProblemImportError("当前仅支持指定题目网站的公开题网址。")
    try:
        port = parsed.port
    except ValueError as exc:
        raise ProblemImportError("题目网址格式不安全。") from exc
    if parsed.username or parsed.password or port not in (None, 443):
        raise ProblemImportError("题目网址格式不安全。")
    match = _PUBLIC_PROBLEM_PATH.fullmatch(parsed.path)
    if match is None:
        match = _TRAINING_PROBLEM_PATH.fullmatch(parsed.path)
    if match is None:
        if parsed.path.startswith("/group/"):
            raise ProblemImportError("该题目需要登录或小组权限，当前仅支持公开题。")
        raise ProblemImportError("当前仅支持指定题目网站的公开题网址。")
    problem_id = html.unescape(unquote(match.group(1))).strip()
    if not problem_id or len(problem_id) > 100:
        raise ProblemImportError("题目编号无效。")
    return problem_id


def _parse_examples(value: str) -> tuple[ProblemExample, ...]:
    return tuple(
        ProblemExample(_clean_example(match.group(1)), _clean_example(match.group(2)))
        for match in _EXAMPLE_PATTERN.finditer(value)
    )


def _clean_example(value: str) -> str:
    value = re.sub(r"<br\s*/?>", "\n", value, flags=re.IGNORECASE)
    value = re.sub(r"<[^>]+>", "", value)
    return html.unescape(value).strip("\r\n")


def _required_string(problem: dict, key: str) -> str:
    value = problem.get(key)
    if not isinstance(value, str) or not value.strip():
        raise ValueError(key)
    return value


def _optional_string(problem: dict, key: str) -> str:
    value = problem.get(key, "")
    if value is None:
        return ""
    if not isinstance(value, str):
        raise TypeError(key)
    return value


def _positive_integer(problem: dict, key: str) -> int:
    value = problem.get(key)
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise TypeError(key)
    integer = int(value)
    if integer <= 0:
        raise ValueError(key)
    return integer
