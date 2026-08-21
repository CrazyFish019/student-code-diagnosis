from models.code_language import CodeLanguage
from ui.components.ai_diagnosis_view import (
    category_label,
    format_code_for_display,
    format_cpp_for_display,
    split_code_example,
    split_cpp_example,
)


def test_internal_diagnosis_categories_have_teacher_friendly_chinese_labels() -> None:
    assert category_label("logic_error") == "逻辑错误"
    assert category_label("boundary_error") == "边界条件错误"
    assert category_label("array_index_error") == "数组下标或越界错误"
    assert category_label("unknown_future_value") == "其他问题"


def test_compact_cpp_statements_are_split_for_display() -> None:
    source = "size_t result=judge(i,j); if(result!=0){max_=std::max(result,max_);num++;}"

    formatted = format_cpp_for_display(source)

    assert "judge(i,j);\n" in formatted
    assert "if(result!=0){\n" in formatted
    assert "    max_=std::max(result,max_);\n" in formatted
    assert "    num++;\n" in formatted


def test_cpp_formatter_keeps_for_header_and_quoted_semicolon_intact() -> None:
    source = 'for(int i=0;i<n;i++){cout << ";";}'

    formatted = format_cpp_for_display(source)

    assert "for(int i=0;i<n;i++){" in formatted
    assert '    cout << ";";' in formatted


def test_existing_cpp_newlines_and_indentation_are_preserved() -> None:
    source = "if (ok) {\r\n    return 1;\r\n}"

    assert format_cpp_for_display(source) == "if (ok) {\n    return 1;\n}"


def test_suggestion_cpp_example_is_separated_and_formatted() -> None:
    prose, code = split_cpp_example(
        "保存返回值，避免重复调用。例如：size_t result=judge(i,j); if(result!=0){num++;}"
    )

    assert prose == "保存返回值，避免重复调用。（示例）"
    assert code is not None
    assert "judge(i,j);\n" in code
    assert "    num++;" in code


def test_python_code_keeps_meaningful_newlines_and_python_highlighting() -> None:
    source = "```python\nfor value in values:\n    print(value)\n```"

    formatted = format_code_for_display(source, CodeLanguage.PYTHON)
    prose, code = split_code_example(
        "使用循环：\n```python\nfor value in values:\n    print(value)\n```",
        CodeLanguage.PYTHON,
    )

    assert formatted == "for value in values:\n    print(value)"
    assert prose == "使用循环："
    assert code == formatted
