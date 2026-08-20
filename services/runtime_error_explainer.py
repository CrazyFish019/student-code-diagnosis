"""Deterministic teacher-facing hints for common runtime error messages."""

from __future__ import annotations

import re


def runtime_error_causes(message: str) -> tuple[str, ...]:
    text = message.lower() if isinstance(message, str) else ""
    causes: list[str] = []

    if (
        "segmentation fault" in text
        or "sigsegv" in text
        or "0xc0000005" in text
        or "-1073741819" in text
        or re.search(r"(?:status|exit)(?:\s+status)?\s+code\s*:\s*(?:11|139)\b", text)
    ):
        causes.append(
            "可能访问了无效内存，例如数组越界、空指针或失效指针，也可能发生了递归过深导致的栈溢出。"
        )
    if (
        "floating point exception" in text
        or "sigfpe" in text
        or re.search(r"(?:status|exit)(?:\s+status)?\s+code\s*:\s*8\b", text)
    ):
        causes.append("可能发生整数除零、取模除零或非法算术运算。")
    if "bad_alloc" in text or "cannot allocate memory" in text:
        causes.append("可能申请了过大的内存，或容器持续增长导致内存耗尽。")
    if "stack overflow" in text:
        causes.append("可能存在无限递归、递归层数过深或栈上局部数组过大。")
    if "out_of_range" in text:
        causes.append("可能使用了越界下标，或调用了会检查边界的容器访问函数。")
    if (
        "assertion" in text
        or "sigabrt" in text
        or "abort" in text
        or re.search(r"(?:status|exit)(?:\s+status)?\s+code\s*:\s*(?:6|134)\b", text)
    ):
        causes.append("程序可能触发了断言、主动终止，或未处理的异常导致运行库中止。")
    if (
        "sigkill" in text
        or "killed" in text
        or re.search(r"(?:status|exit)(?:\s+status)?\s+code\s*:\s*(?:9|137)\b", text)
    ):
        causes.append("程序可能被系统强制终止，常见原因是资源使用过高。")
    if "terminate called after throwing" in text or "uncaught exception" in text:
        causes.append("程序抛出了未捕获的异常，请检查异常信息附近的容器、转换或内存操作。")

    if not causes:
        causes.append("程序以非正常状态结束，请结合源码检查数组边界、指针、除零、递归和异常处理。")
    return tuple(dict.fromkeys(causes))
