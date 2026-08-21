"""Console-enabled bundled interpreter entry point for selected Python code."""

from __future__ import annotations

import runpy
import sys
from pathlib import Path


def main(arguments: list[str] | None = None) -> int:
    values = sys.argv[1:] if arguments is None else arguments
    if len(values) != 1:
        raise RuntimeError("Python学生代码执行参数无效。")
    source = Path(values[0]).resolve()
    if not source.is_file() or source.suffix.lower() != ".py":
        raise RuntimeError("Python学生代码文件无效。")
    original_argv = sys.argv
    try:
        sys.argv = [str(source)]
        runpy.run_path(str(source), run_name="__main__")
    finally:
        sys.argv = original_argv
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
