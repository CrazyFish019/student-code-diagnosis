"""Widgets for source input and structured diagnosis presentation."""

from __future__ import annotations

import re

import streamlit as st

from models.ai_code_diagnosis import AICodeDiagnosis
from models.code_language import CodeLanguage


_CATEGORY_LABELS = {
    "syntax_error": "语法错误",
    "compile_risk": "编译风险",
    "logic_error": "逻辑错误",
    "boundary_error": "边界条件错误",
    "input_error": "输入处理错误",
    "output_format_error": "输出格式错误",
    "complexity_risk": "时间或空间复杂度风险",
    "data_type_error": "数据类型或数值溢出错误",
    "array_index_error": "数组下标或越界错误",
    "uncertain": "暂时无法确定",
}


def category_label(category: str) -> str:
    return _CATEGORY_LABELS.get(category, "其他问题")


def format_cpp_for_display(code: str, *, line_width: int = 96) -> str:
    """Make compact model-generated C++ readable without changing stored data."""

    value = code.replace("\r\n", "\n").replace("\r", "\n").strip()
    fenced = re.fullmatch(
        r"```(?:cpp|c\+\+|cxx)?\s*\n?(.*?)\n?```",
        value,
        re.DOTALL | re.IGNORECASE,
    )
    if fenced:
        value = fenced.group(1).strip()
    if "\n" in value:
        return value

    lines: list[str] = []
    current: list[str] = []
    indent = 0
    paren_depth = 0
    quote: str | None = None
    escaped = False

    def flush() -> None:
        text = "".join(current).strip()
        if text:
            lines.append("    " * indent + text)
        current.clear()

    for char in value:
        if quote is not None:
            current.append(char)
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == quote:
                quote = None
            continue
        if char in {'"', "'"}:
            quote = char
            current.append(char)
        elif char == "(":
            paren_depth += 1
            current.append(char)
        elif char == ")":
            paren_depth = max(0, paren_depth - 1)
            current.append(char)
        elif char == "{" and paren_depth == 0:
            current.append(char)
            flush()
            indent += 1
        elif char == "}" and paren_depth == 0:
            flush()
            indent = max(0, indent - 1)
            current.append(char)
        elif char == ";" and paren_depth == 0:
            current.append(char)
            flush()
        else:
            current.append(char)
    flush()

    formatted = "\n".join(lines) if lines else value
    return "\n".join(_wrap_cpp_line(line, line_width) for line in formatted.splitlines())


def split_cpp_example(text: str) -> tuple[str, str | None]:
    """Separate a C++ example from suggestion prose when a model combines them."""

    fenced = re.search(
        r"```(?:cpp|c\+\+|cxx)?\s*\n?(.*?)\n?```",
        text,
        re.DOTALL | re.IGNORECASE,
    )
    if fenced:
        prose = (text[: fenced.start()] + text[fenced.end() :]).strip()
        return prose, format_cpp_for_display(fenced.group(1))
    for marker in ("例如：", "示例：", "例如:", "示例:"):
        if marker not in text:
            continue
        prose, _, candidate = text.partition(marker)
        if _looks_like_cpp(candidate):
            return f"{prose.strip()}（示例）".strip(), format_cpp_for_display(candidate)
    return text, None


def format_code_for_display(code: str, language: CodeLanguage) -> str:
    if language is CodeLanguage.CPP:
        return format_cpp_for_display(code)
    value = code.replace("\r\n", "\n").replace("\r", "\n").strip()
    fenced = re.fullmatch(
        r"```(?:python|py|python3)?\s*\n?(.*?)\n?```",
        value,
        re.DOTALL | re.IGNORECASE,
    )
    return fenced.group(1).strip() if fenced else value


def split_code_example(
    text: str, language: CodeLanguage
) -> tuple[str, str | None]:
    if language is CodeLanguage.CPP:
        return split_cpp_example(text)
    fenced = re.search(
        r"```(?:python|py|python3)?\s*\n?(.*?)\n?```",
        text,
        re.DOTALL | re.IGNORECASE,
    )
    if fenced:
        prose = (text[: fenced.start()] + text[fenced.end() :]).strip()
        return prose, format_code_for_display(fenced.group(1), language)
    return text, None


def _looks_like_cpp(value: str) -> bool:
    return ";" in value and bool(
        re.search(
            r"(?:\b(?:if|for|while|return|auto|int|size_t|vector)\b|std::|[{}=])",
            value,
        )
    )


def _wrap_cpp_line(line: str, width: int) -> str:
    """Wrap a long display line after safe C++ punctuation."""

    if len(line) <= width:
        return line
    leading = line[: len(line) - len(line.lstrip())]
    remaining = line.lstrip()
    wrapped: list[str] = []
    while len(leading) + len(remaining) > width:
        limit = max(20, width - len(leading))
        candidates = [
            index + 1
            for index, char in enumerate(remaining[:limit])
            if char in {",", "?"}
            or (char == ":" and remaining[index : index + 2] != "::")
        ]
        if not candidates:
            break
        split_at = candidates[-1]
        wrapped.append(leading + remaining[:split_at].rstrip())
        remaining = remaining[split_at:].lstrip()
        leading += "    "
    wrapped.append(leading + remaining)
    return "\n".join(wrapped)


def render_source_input() -> str:
    st.subheader("3. 待诊断代码")
    return st.text_area(
        "粘贴C++代码",
        height=420,
        placeholder="#include <iostream>\nusing namespace std;\n\nint main() {\n    // ...\n}",
        key="diagnosis_source_code",
    )


def render_ai_diagnosis(
    diagnosis: AICodeDiagnosis,
    *,
    has_oj_evidence: bool = False,
    has_local_execution: bool = False,
    language: CodeLanguage = CodeLanguage.CPP,
) -> None:
    st.subheader("5. AI诊断结果")
    if has_local_execution:
        st.info("本结果结合OJ判题记录和教师选中测试点的本地运行结果生成。")
    elif has_oj_evidence:
        st.info("本结果结合OJ已有判题记录生成；本工具没有重新运行学生代码。")
    else:
        st.warning("本结果基于题面、公开样例和学生代码生成，未经编译运行或隐藏测试验证。")
    labels = {
        "likely_correct": "可能正确",
        "likely_incorrect": "可能存在错误",
        "uncertain": "无法确定",
    }
    conclusion, confidence = st.columns(2)
    conclusion.metric("诊断结论", labels[diagnosis.conclusion.value])
    confidence.metric("可信度", f"{diagnosis.confidence:.0%}")
    st.markdown("### 概要")
    st.write(diagnosis.summary)
    st.write("问题类别：", "、".join(category_label(item) for item in diagnosis.categories))
    st.markdown("### 根本原因")
    st.write(diagnosis.root_cause)
    if diagnosis.evidence:
        st.markdown("### 代码证据")
        for item in diagnosis.evidence:
            line = f"第 {item.line} 行" if item.line else "未定位行号"
            st.markdown(f"**{line}：** {item.explanation}")
            if item.code:
                st.code(
                    format_code_for_display(item.code, language),
                    language=language.syntax_name,
                    wrap_lines=True,
                )
    if diagnosis.sample_analysis:
        st.markdown("### 公开样例推演")
        for item in diagnosis.sample_analysis:
            st.markdown(f"- 样例 {item.sample_index}：{item.analysis}")
    st.markdown("### 修改建议")
    for item in diagnosis.suggestions:
        prose, code = split_code_example(item, language)
        if prose:
            st.markdown(f"- {prose}")
        if code:
            st.code(code, language=language.syntax_name, wrap_lines=True)
    teacher, learner = st.columns(2)
    with teacher:
        st.markdown("### 教师参考")
        st.write(diagnosis.teacher_feedback)
    with learner:
        st.markdown("### 代码反馈")
        st.write(diagnosis.student_feedback)
    with st.expander("诊断限制"):
        for item in diagnosis.limitations:
            st.markdown(f"- {item}")
