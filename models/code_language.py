"""Programming languages supported by the active diagnosis workflow."""

from __future__ import annotations

from enum import Enum


class CodeLanguage(str, Enum):
    CPP = "cpp"
    PYTHON = "python"

    @property
    def display_name(self) -> str:
        return "C++" if self is CodeLanguage.CPP else "Python 3"

    @property
    def syntax_name(self) -> str:
        return "cpp" if self is CodeLanguage.CPP else "python"
