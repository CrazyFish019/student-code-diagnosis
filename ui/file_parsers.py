"""Safe, browser-independent parsing of teacher-uploaded local files."""

from __future__ import annotations

from io import BytesIO
import json
from pathlib import Path, PurePosixPath
import tempfile
from typing import Iterable, Sequence
import zipfile

from core.config import TEMP_DIR
from models.testcase import TestCase
from models.workbench import StudentSource

_MAX_ARCHIVE_FILES = 1_000
_MAX_ARCHIVE_BYTES = 50 * 1024 * 1024


class UIInputError(ValueError):
    """Raised for an uploaded file problem that can be shown to a teacher."""


def decode_text(data: bytes) -> str:
    """Decode common source/data encodings without crashing on unknown bytes."""
    for encoding in ("utf-8-sig", "gb18030"):
        try:
            return data.decode(encoding)
        except UnicodeDecodeError:
            continue
    return data.decode("utf-8", errors="replace")


def extract_student_name(filename: str) -> str:
    normalized = filename.replace("\\", "/")
    name = PurePosixPath(normalized).stem.strip()
    if not name:
        raise UIInputError(f"无法从文件名提取学生姓名：{filename}")
    return name


def _safe_archive_members(archive: zipfile.ZipFile) -> tuple[zipfile.ZipInfo, ...]:
    members = tuple(item for item in archive.infolist() if not item.is_dir())
    if len(members) > _MAX_ARCHIVE_FILES:
        raise UIInputError("ZIP 文件数量过多。")
    if sum(item.file_size for item in members) > _MAX_ARCHIVE_BYTES:
        raise UIInputError("ZIP 解压后内容过大。")
    for item in members:
        path = PurePosixPath(item.filename.replace("\\", "/"))
        if path.is_absolute() or ".." in path.parts:
            raise UIInputError(f"ZIP 包含不安全路径：{item.filename}")
    return members


def _extract_selected_files(
    archive_data: bytes,
    *,
    suffixes: set[str],
) -> list[tuple[str, bytes]]:
    try:
        with zipfile.ZipFile(BytesIO(archive_data)) as archive:
            members = _safe_archive_members(archive)
            selected = [
                item
                for item in members
                if PurePosixPath(item.filename).suffix.lower() in suffixes
            ]
            TEMP_DIR.mkdir(parents=True, exist_ok=True)
            with tempfile.TemporaryDirectory(
                prefix="student-code-upload-", dir=TEMP_DIR
            ) as temp:
                root = Path(temp).resolve()
                extracted: list[tuple[str, bytes]] = []
                for index, item in enumerate(selected, start=1):
                    archive_path = PurePosixPath(item.filename.replace("\\", "/"))
                    target = root / f"{index:04d}-{archive_path.name}"
                    data = archive.read(item)
                    target.write_bytes(data)
                    extracted.append((item.filename, target.read_bytes()))
                return extracted
    except zipfile.BadZipFile as exc:
        raise UIInputError("ZIP 文件损坏或格式不正确。") from exc
    except (RuntimeError, OSError) as exc:
        raise UIInputError(f"无法读取 ZIP 文件：{exc}") from exc


def parse_student_uploads(
    uploads: Sequence[tuple[str, bytes]],
) -> tuple[StudentSource, ...]:
    candidates: list[tuple[str, bytes]] = []
    for filename, data in uploads:
        suffix = Path(filename).suffix.lower()
        if suffix == ".cpp":
            candidates.append((filename, data))
        elif suffix == ".zip":
            extracted = _extract_selected_files(data, suffixes={".cpp"})
            if not extracted:
                raise UIInputError(f"ZIP 中没有找到 cpp 文件：{filename}")
            candidates.extend(extracted)
        else:
            raise UIInputError(f"不支持的学生文件类型：{filename}")

    if not candidates:
        raise UIInputError("没有找到学生 C++ 文件。")

    name_counts: dict[str, int] = {}
    students: list[StudentSource] = []
    for filename, data in candidates:
        base_name = extract_student_name(filename)
        count = name_counts.get(base_name, 0) + 1
        name_counts[base_name] = count
        display_name = base_name if count == 1 else f"{base_name} ({count})"
        source_code = decode_text(data)
        if not source_code.strip():
            raise UIInputError(f"学生代码文件为空：{filename}")
        students.append(StudentSource(display_name, filename, source_code))
    return tuple(students)


def parse_standard_source(filename: str, data: bytes) -> str:
    if Path(filename).suffix.lower() != ".cpp":
        raise UIInputError("标准程序必须是 .cpp 文件。")
    source_code = decode_text(data)
    if not source_code.strip():
        raise UIInputError("标准程序为空。")
    return source_code


def _testcases_from_json(data: bytes) -> tuple[TestCase, ...]:
    try:
        payload = json.loads(decode_text(data))
    except json.JSONDecodeError as exc:
        raise UIInputError(f"测试数据 JSON 格式错误：{exc}") from exc
    raw_cases = payload.get("test_cases") if isinstance(payload, dict) else payload
    if not isinstance(raw_cases, list) or not raw_cases:
        raise UIInputError("测试数据 JSON 必须包含非空 test_cases 列表。")

    cases: list[TestCase] = []
    for index, item in enumerate(raw_cases, start=1):
        if not isinstance(item, dict):
            raise UIInputError(f"第 {index} 个测试点必须是对象。")
        testcase_id = item.get("id", f"case-{index}")
        input_data = item.get("input_data", item.get("input"))
        expected_output = item.get("expected_output", item.get("output"))
        if not isinstance(input_data, str) or not isinstance(expected_output, str):
            raise UIInputError(
                f"测试点 {testcase_id} 缺少字符串 input_data/expected_output。"
            )
        cases.append(TestCase(str(testcase_id), input_data, expected_output))
    return tuple(cases)


def _testcases_from_zip(data: bytes) -> tuple[TestCase, ...]:
    files = _extract_selected_files(data, suffixes={".in", ".out"})
    paired: dict[str, dict[str, bytes]] = {}
    for filename, content in files:
        normalized = filename.replace("\\", "/")
        path = PurePosixPath(normalized)
        key = str(path.with_suffix(""))
        paired.setdefault(key, {})[path.suffix.lower()] = content
    complete = [key for key, values in paired.items() if {".in", ".out"} <= values.keys()]
    incomplete = [key for key, values in paired.items() if set(values) != {".in", ".out"}]
    if incomplete:
        raise UIInputError(f"测试数据缺少配对的 .in/.out：{', '.join(incomplete)}")
    if not complete:
        raise UIInputError("ZIP 中没有找到成对的 .in/.out 测试数据。")
    return tuple(
        TestCase(
            testcase_id.replace("/", "-"),
            decode_text(paired[testcase_id][".in"]),
            decode_text(paired[testcase_id][".out"]),
        )
        for testcase_id in sorted(complete)
    )


def parse_testcase_upload(filename: str, data: bytes) -> tuple[TestCase, ...]:
    suffix = Path(filename).suffix.lower()
    if suffix == ".json":
        return _testcases_from_json(data)
    if suffix == ".zip":
        return _testcases_from_zip(data)
    raise UIInputError("测试数据仅支持 JSON 或包含成对 .in/.out 的 ZIP。")


def validate_workbench_inputs(
    *,
    problem_id: str,
    problem_title: str,
    compiler: str,
    standard_uploaded: bool,
    test_data_uploaded: bool,
    student_upload_count: int,
) -> tuple[str, ...]:
    errors: list[str] = []
    if not problem_id.strip():
        errors.append("请输入题目 ID。")
    if not problem_title.strip():
        errors.append("请输入题目名称。")
    if not compiler.strip():
        errors.append("请输入编译器路径或命令。")
    if not standard_uploaded:
        errors.append("请上传标准程序 .cpp 文件。")
    if not test_data_uploaded:
        errors.append("请上传测试数据 JSON 或 ZIP 文件。")
    if student_upload_count <= 0:
        errors.append("请上传至少一个学生 .cpp 或 ZIP 文件。")
    return tuple(errors)
