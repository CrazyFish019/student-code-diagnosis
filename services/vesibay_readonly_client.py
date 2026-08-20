"""Allowlisted Vesibay administrator client for diagnosis evidence imports."""

from __future__ import annotations

import io
import re
import zipfile
from dataclasses import dataclass
from pathlib import PurePosixPath
from typing import Any
from urllib.parse import urlparse

from models.vesibay_submission import OJCaseEvidence, VesibaySubmissionEvidence
from services.json_http_client import (
    JsonHttpResponse,
    JsonHttpTransport,
    NetworkRequestError,
    UrllibJsonHttpTransport,
)
from services.problem_importer import ProblemImportError, import_vesibay_problem_by_id
from services.binary_http_client import (
    BinaryHttpTransport,
    BinaryNetworkError,
    UrllibBinaryHttpTransport,
)


_BASE_URL = "https://www.vesibay.cn"
_SUBMISSION_ID_IN_PATH = re.compile(r"(?:^|/)submission-detail/(\d+)(?:/|$)")
_TESTCASE_FILENAME = re.compile(r"^[^/\\]+\.(?:in|out)$", re.IGNORECASE)
_MAX_ARCHIVE_FILES = 20_000
_MAX_ARCHIVE_UNCOMPRESSED_BYTES = 128 * 1024 * 1024
_MAX_TESTCASE_FILE_BYTES = 16 * 1024 * 1024
_STATUS_NAMES = {
    -10: "PENDING",
    -2: "CE",
    -1: "WA",
    0: "AC",
    1: "TLE",
    2: "MLE",
    3: "RE",
    4: "SYSTEM_ERROR",
    5: "PENDING",
    6: "COMPILING",
    7: "JUDGING",
    8: "PARTIAL_ACCEPTED",
    9: "SUBMIT_FAILED",
}


class VesibayAccessError(RuntimeError):
    """Teacher-facing login, permission, or response validation failure."""


@dataclass(frozen=True, slots=True)
class VesibayCredentials:
    username: str
    password: str

    def __post_init__(self) -> None:
        if not isinstance(self.username, str) or not self.username.strip():
            raise ValueError("username must be non-empty")
        if not isinstance(self.password, str) or not self.password:
            raise ValueError("password must be non-empty")


class VesibayReadOnlyClient:
    """Uses an admin token but exposes only four hard-coded GET operations."""

    def __init__(
        self,
        *,
        transport: JsonHttpTransport | None = None,
        binary_transport: BinaryHttpTransport | None = None,
        timeout_seconds: int = 20,
    ) -> None:
        self._transport = transport or UrllibJsonHttpTransport(
            max_response_bytes=8 * 1024 * 1024
        )
        self._binary_transport = binary_transport or UrllibBinaryHttpTransport()
        self._timeout_seconds = timeout_seconds

    def verify_credentials(self, credentials: VesibayCredentials) -> None:
        token = self._login(credentials)
        self._authorized_get("/api/get-user-auth-info", token)

    def import_submission(
        self,
        url: str,
        credentials: VesibayCredentials,
    ) -> VesibaySubmissionEvidence:
        submission_id = parse_submission_url(url)
        token = self._login(credentials)
        detail = self._authorized_get(
            f"/api/get-submission-detail?submitId={submission_id}", token
        )
        case_result = self._authorized_get(
            f"/api/get-all-case-result?submitId={submission_id}", token
        )
        submission = _mapping(_mapping(detail.payload.get("data")).get("submission"))
        if not submission:
            raise VesibayAccessError("提交详情数据不完整。")
        source_code = _required_visible_text(submission.get("code"), "无法读取提交源码。")
        problem_id = _required_visible_text(
            submission.get("displayPid"), "提交记录中没有有效题号。"
        )
        try:
            problem = import_vesibay_problem_by_id(
                problem_id,
                source_url=f"{_BASE_URL}/problem/{problem_id}",
                authorization=token,
                transport=self._transport,
                timeout_seconds=self._timeout_seconds,
            )
        except ProblemImportError as exc:
            raise VesibayAccessError(str(exc)) from exc

        data = _mapping(case_result.payload.get("data"))
        raw_cases = data.get("judgeCaseList")
        if not isinstance(raw_cases, list):
            raise VesibayAccessError("测试点结果数据不完整。")
        referenced_files = _referenced_testcase_files(raw_cases)
        file_contents = (
            self._download_testcase_files(submission.get("pid"), token, referenced_files)
            if referenced_files
            else {}
        )
        cases = tuple(
            _parse_case(item, index, file_contents)
            for index, item in enumerate(raw_cases, start=1)
            if isinstance(item, dict)
        )
        return VesibaySubmissionEvidence(
            submission_id=submission_id,
            problem=problem,
            source_code=source_code,
            final_status=_status_name(submission.get("status")),
            score=_optional_number(submission.get("score")),
            cases=cases,
        )

    def _login(self, credentials: VesibayCredentials) -> str:
        response = self._request(
            "POST",
            "/api/admin/login",
            payload={
                "username": credentials.username.strip(),
                "password": credentials.password,
            },
        )
        token = next(
            (
                value
                for key, value in response.headers.items()
                if key.lower() == "authorization" and value
            ),
            None,
        )
        if not token:
            raise VesibayAccessError("登录成功，但网站没有返回授权令牌。")
        return token

    def _authorized_get(self, path: str, token: str) -> JsonHttpResponse:
        return self._request(
            "GET", path, headers={"Authorization": token, "Url-Type": "general"}
        )

    def _request(
        self,
        method: str,
        path: str,
        *,
        headers: dict[str, str] | None = None,
        payload: dict[str, Any] | None = None,
    ) -> JsonHttpResponse:
        request_headers = {"Url-Type": "admin" if path.startswith("/api/admin/") else "general"}
        request_headers.update(headers or {})
        try:
            response = self._transport.request_json(
                method,
                _BASE_URL + path,
                headers=request_headers,
                payload=payload,
                timeout_seconds=self._timeout_seconds,
            )
        except NetworkRequestError as exc:
            raise VesibayAccessError("题目网站连接失败或超时。") from exc
        response_status = response.payload.get("status")
        if response.status_code == 401 or response_status == 401:
            if path.startswith("/api/admin/"):
                raise VesibayAccessError("网站账号、密码或登录状态无效。")
            raise VesibayAccessError("当前网站账号无权读取该信息，或登录状态已失效。")
        if response.status_code == 403 or response_status == 403:
            raise VesibayAccessError("当前网站账号无权读取该信息。")
        if response.status_code == 404 or response_status == 404:
            raise VesibayAccessError("没有找到对应的提交报告，请检查网址是否正确。")
        if response.status_code != 200 or response_status != 200:
            message = response.payload.get("msg")
            raise VesibayAccessError(
                str(message).strip() if isinstance(message, str) and message.strip()
                else "题目网站返回了异常结果。"
            )
        return response

    def _download_testcase_files(
        self,
        pid: Any,
        token: str,
        filenames: set[str],
    ) -> dict[str, str]:
        if isinstance(pid, bool):
            raise VesibayAccessError("提交记录中没有有效的题目内部ID。")
        try:
            numeric_pid = int(pid)
        except (TypeError, ValueError) as exc:
            raise VesibayAccessError("提交记录中没有有效的题目内部ID。") from exc
        if numeric_pid <= 0:
            raise VesibayAccessError("提交记录中没有有效的题目内部ID。")
        try:
            response = self._binary_transport.request(
                "GET",
                f"{_BASE_URL}/api/file/download-testcase?pid={numeric_pid}",
                headers={"Authorization": token, "Url-Type": "general"},
                timeout_seconds=max(60, self._timeout_seconds),
            )
        except BinaryNetworkError as exc:
            raise VesibayAccessError(str(exc)) from exc
        if response.status_code == 401:
            raise VesibayAccessError("网站登录状态已失效。")
        if response.status_code == 403:
            raise VesibayAccessError("当前网站账号无权下载测试数据。")
        if response.status_code != 200:
            raise VesibayAccessError("测试数据下载失败。")
        return _read_testcase_archive(response.body, filenames)


def parse_submission_url(url: str) -> str:
    if not isinstance(url, str) or not url.strip():
        raise VesibayAccessError("请输入提交详情网址。")
    normalized = url.strip()
    if not normalized.startswith(f"{_BASE_URL}/"):
        raise VesibayAccessError("网址必须是指定题目网站的提交详情页面。")
    parsed = urlparse(normalized)
    match = _SUBMISSION_ID_IN_PATH.search(parsed.path)
    if match is None:
        raise VesibayAccessError("该网址中没有可识别的提交编号，请确认它是提交报告网址。")
    return match.group(1)


def _parse_case(
    item: dict[str, Any], index: int, file_contents: dict[str, str]
) -> OJCaseEvidence:
    case_id = item.get("caseId", item.get("id", index))
    status = _status_name(item.get("status"))
    input_reference = _optional_text(item.get("inputData"))
    output_reference = _optional_text(item.get("outputData"))
    user_output = _optional_text(item.get("userOutput"))
    explicit_error = _optional_text(
        item.get("errorMessage", item.get("stderr", ""))
    )
    return OJCaseEvidence(
        case_id=str(case_id),
        status=status,
        execution_time_ms=_optional_integer(item.get("time")),
        memory_bytes=_optional_integer(item.get("memory")),
        input_data=_resolve_testcase_value(input_reference, file_contents),
        expected_output=_resolve_testcase_value(output_reference, file_contents),
        user_output=user_output,
        error_message=explicit_error or (user_output if status == "RE" else ""),
    )


def _referenced_testcase_files(raw_cases: list[Any]) -> set[str]:
    pairs = [
        (item.get("inputData"), item.get("outputData"))
        for item in raw_cases
        if isinstance(item, dict)
    ]
    if not pairs or not all(
        isinstance(input_name, str)
        and isinstance(output_name, str)
        and _archive_basename(input_name).lower().endswith(".in")
        and _archive_basename(output_name).lower().endswith(".out")
        for input_name, output_name in pairs
    ):
        return set()
    return {
        _archive_basename(value)
        for pair in pairs
        for value in pair
        if isinstance(value, str)
    }


def _resolve_testcase_value(value: str, contents: dict[str, str]) -> str:
    filename = _archive_basename(value)
    if _TESTCASE_FILENAME.fullmatch(filename):
        try:
            return contents[filename]
        except KeyError as exc:
            raise VesibayAccessError(f"测试数据包中缺少文件：{filename}") from exc
    return value


def _read_testcase_archive(body: bytes, filenames: set[str]) -> dict[str, str]:
    stream = io.BytesIO(body)
    if not zipfile.is_zipfile(stream):
        raise VesibayAccessError("下载的测试数据不是有效ZIP文件。")
    stream.seek(0)
    result: dict[str, str] = {}
    with zipfile.ZipFile(stream) as archive:
        members = [item for item in archive.infolist() if not item.is_dir()]
        if len(members) > _MAX_ARCHIVE_FILES:
            raise VesibayAccessError("测试数据包文件数量过多。")
        if sum(item.file_size for item in members) > _MAX_ARCHIVE_UNCOMPRESSED_BYTES:
            raise VesibayAccessError("测试数据解压后超过大小限制。")
        by_basename: dict[str, zipfile.ZipInfo] = {}
        for item in members:
            name = _archive_basename(item.filename)
            if name in by_basename:
                raise VesibayAccessError(f"测试数据包存在重复文件名：{name}")
            by_basename[name] = item
        for filename in filenames:
            item = by_basename.get(filename)
            if item is None:
                raise VesibayAccessError(f"测试数据包中缺少文件：{filename}")
            if item.flag_bits & 0x1:
                raise VesibayAccessError(f"测试数据文件已加密，无法读取：{filename}")
            if item.file_size > _MAX_TESTCASE_FILE_BYTES:
                raise VesibayAccessError(f"测试数据文件过大：{filename}")
            result[filename] = _decode_testcase_text(archive.read(item))
    return result


def _archive_basename(value: str) -> str:
    return PurePosixPath(value.replace("\\", "/")).name


def _decode_testcase_text(value: bytes) -> str:
    for encoding in ("utf-8-sig", "gb18030"):
        try:
            return value.decode(encoding)
        except UnicodeDecodeError:
            pass
    return value.decode("utf-8", errors="replace")


def _status_name(value: Any) -> str:
    if isinstance(value, bool):
        return "UNKNOWN"
    try:
        number = int(value)
    except (TypeError, ValueError):
        return "UNKNOWN"
    return _STATUS_NAMES.get(number, f"STATUS_{number}")


def _optional_integer(value: Any) -> int | None:
    if value is None or isinstance(value, bool):
        return None
    try:
        result = int(value)
    except (TypeError, ValueError):
        return None
    return result if result >= 0 else None


def _optional_number(value: Any) -> float | None:
    if value is None or isinstance(value, bool):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _optional_text(value: Any) -> str:
    return value if isinstance(value, str) else ""


def _required_visible_text(value: Any, message: str) -> str:
    if not isinstance(value, str) or not value.strip() or "not support viewing" in value.lower():
        raise VesibayAccessError(message)
    return value


def _mapping(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}
