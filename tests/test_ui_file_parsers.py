from io import BytesIO
import json
import zipfile

import pytest

from ui.file_parsers import (
    UIInputError,
    extract_student_name,
    parse_student_uploads,
    parse_testcase_upload,
    validate_workbench_inputs,
)


def make_zip(files: dict[str, bytes | str]) -> bytes:
    output = BytesIO()
    with zipfile.ZipFile(output, mode="w") as archive:
        for filename, content in files.items():
            archive.writestr(
                filename,
                content.encode("utf-8") if isinstance(content, str) else content,
            )
    return output.getvalue()


def test_empty_workbench_input_returns_teacher_prompts() -> None:
    errors = validate_workbench_inputs(
        problem_id="",
        problem_title=" ",
        compiler="",
        standard_uploaded=False,
        test_data_uploaded=False,
        student_upload_count=0,
    )

    assert "请输入题目 ID。" in errors
    assert "请上传标准程序 .cpp 文件。" in errors
    assert "请上传至少一个学生 .cpp 或 ZIP 文件。" in errors
    assert len(errors) == 6


def test_zip_parsing_and_student_name_extraction() -> None:
    archive = make_zip(
        {
            "一班/张三.cpp": "int main() { return 0; }\n",
            "一班/李四.cpp": "int main() { return 1; }\n",
            "readme.txt": "ignored",
        }
    )

    students = parse_student_uploads((("一班代码.zip", archive),))

    assert [student.student_name for student in students] == ["张三", "李四"]
    assert students[0].filename == "一班/张三.cpp"
    assert students[1].source_code.endswith("\n")


def test_single_cpp_student_name_uses_filename_stem() -> None:
    students = parse_student_uploads(
        (("王小明.cpp", b"int main() { return 0; }\n"),)
    )

    assert extract_student_name("folder/王小明.cpp") == "王小明"
    assert students[0].student_name == "王小明"


def test_duplicate_student_names_receive_stable_suffix() -> None:
    archive = make_zip(
        {
            "class-a/Alice.cpp": "int main() {}",
            "class-b/Alice.cpp": "int main() {}",
        }
    )

    students = parse_student_uploads((("duplicates.zip", archive),))

    assert [item.student_name for item in students] == ["Alice", "Alice (2)"]


def test_zip_path_traversal_is_rejected() -> None:
    archive = make_zip({"../outside.cpp": "int main() {}"})

    with pytest.raises(UIInputError, match="不安全路径"):
        parse_student_uploads((("unsafe.zip", archive),))


def test_empty_zip_reports_no_cpp_files() -> None:
    archive = make_zip({"readme.txt": "nothing"})

    with pytest.raises(UIInputError, match="没有找到 cpp"):
        parse_student_uploads((("empty.zip", archive),))


def test_json_testcase_parsing_preserves_newlines() -> None:
    payload = json.dumps(
        {
            "test_cases": [
                {
                    "id": "case-1",
                    "input_data": "1 2\n",
                    "expected_output": "3\n",
                }
            ]
        },
        ensure_ascii=False,
    ).encode("utf-8")

    cases = parse_testcase_upload("tests.json", payload)

    assert cases[0].input_data == "1 2\n"
    assert cases[0].expected_output == "3\n"


def test_zip_testcase_parsing_pairs_in_and_out() -> None:
    archive = make_zip(
        {
            "cases/01.in": "1 2\n",
            "cases/01.out": "3\n",
            "cases/02.in": "10 20\n",
            "cases/02.out": "30\n",
        }
    )

    cases = parse_testcase_upload("tests.zip", archive)

    assert [case.id for case in cases] == ["cases-01", "cases-02"]
    assert cases[1].expected_output == "30\n"
