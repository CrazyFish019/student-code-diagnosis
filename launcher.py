"""Windows-friendly launcher for source and PyInstaller distributions."""

from __future__ import annotations

import os
import socket
import sys
import threading
import time
from pathlib import Path
import webbrowser

# Importing the application makes its complete module graph visible to
# PyInstaller. Streamlit executes app.py itself after the server starts.
from ui import app as _packaged_application  # noqa: F401


def application_script() -> Path:
    bundle_root = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent))
    return bundle_root / "app.py"


def available_port(start: int = 8501, stop: int = 8599) -> int:
    for port in range(start, stop + 1):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
            try:
                probe.bind(("127.0.0.1", port))
            except OSError:
                continue
            return port
    raise RuntimeError("没有可用的本地端口，请关闭其他诊断工具窗口后重试。")


def _open_browser_when_ready(port: int) -> None:
    for _ in range(100):
        try:
            with socket.create_connection(("127.0.0.1", port), timeout=0.2):
                webbrowser.open(f"http://127.0.0.1:{port}")
                return
        except OSError:
            time.sleep(0.1)


def main() -> int:
    from streamlit.web import cli as streamlit_cli

    script = application_script()
    if not script.is_file():
        raise RuntimeError("安装文件不完整：缺少 app.py。")
    port = available_port()
    if os.environ.get("STUDENT_CODE_DIAGNOSIS_NO_BROWSER") != "1":
        threading.Thread(
            target=_open_browser_when_ready, args=(port,), daemon=True
        ).start()
    sys.argv = [
        "streamlit",
        "run",
        str(script),
        "--server.address=127.0.0.1",
        f"--server.port={port}",
        "--server.headless=true",
        "--global.developmentMode=false",
        "--browser.gatherUsageStats=false",
    ]
    return int(streamlit_cli.main() or 0)


if __name__ == "__main__":
    raise SystemExit(main())
