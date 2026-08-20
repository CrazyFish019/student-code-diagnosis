"""Deterministic output comparison for judging."""

from __future__ import annotations


def normalize_output(output: str) -> tuple[str, ...]:
    """Return comparable output lines without erasing meaningful content.

    CRLF and lone CR are normalized to LF, spaces and tabs at the end of each
    line are ignored, and blank/whitespace-only lines are omitted. Leading
    whitespace and the order and content of non-blank lines remain significant.
    """
    if not isinstance(output, str):
        raise TypeError("output must be a string")

    newline_normalized = output.replace("\r\n", "\n").replace("\r", "\n")
    lines = (line.rstrip(" \t") for line in newline_normalized.split("\n"))
    return tuple(line for line in lines if line != "")


def compare_output(expected_output: str, actual_output: str) -> bool:
    """Return whether actual output matches expected output under judge rules."""
    return normalize_output(expected_output) == normalize_output(actual_output)
