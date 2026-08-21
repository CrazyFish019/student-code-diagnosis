"""Windows tray supervisor for the packaged Streamlit application."""

from __future__ import annotations

import ctypes
import json
import os
import secrets
import signal
import socket
import subprocess
import sys
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Callable
from urllib.error import URLError
from urllib.request import Request, urlopen
import webbrowser

from core.launcher_protocol import (
    STREAMLIT_WORKER_ARGUMENT,
)
# Keep the complete application graph visible to PyInstaller. Streamlit executes
# app.py itself inside the worker process after the supervisor starts it.
from ui import app as _packaged_application  # noqa: F401


_CONTROL_TOKEN_HEADER = "X-Student-Code-Diagnosis-Token"
_MUTEX_NAME = "Local\\StudentCodeDiagnosis.Singleton"
_CONTROL_FILENAME = "launcher-control.json"


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
    raise RuntimeError("没有可用的本地端口，请退出已有诊断工具后重试。")


def control_state_path() -> Path:
    from core.config import TEMP_DIR

    return TEMP_DIR / _CONTROL_FILENAME


def worker_command(port: int) -> list[str]:
    if getattr(sys, "frozen", False):
        return [sys.executable, STREAMLIT_WORKER_ARGUMENT, str(port)]
    return [
        sys.executable,
        str(Path(__file__).resolve()),
        STREAMLIT_WORKER_ARGUMENT,
        str(port),
    ]


def _open_browser_when_ready(port: int) -> None:
    for _ in range(150):
        try:
            with socket.create_connection(("127.0.0.1", port), timeout=0.2):
                webbrowser.open(f"http://127.0.0.1:{port}")
                return
        except OSError:
            time.sleep(0.1)


def _run_streamlit_worker(port: int) -> int:
    from streamlit.web import cli as streamlit_cli

    script = application_script()
    if not script.is_file():
        raise RuntimeError("安装文件不完整：缺少 app.py。")
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


class _ControlServer:
    def __init__(
        self,
        *,
        token: str,
        open_page: Callable[[], None],
        shutdown: Callable[[], None],
    ) -> None:
        controller = self

        class Handler(BaseHTTPRequestHandler):
            def do_POST(self) -> None:  # noqa: N802
                if self.headers.get(_CONTROL_TOKEN_HEADER) != controller.token:
                    self.send_error(403)
                    return
                if self.path == "/open":
                    self.send_response(204)
                    self.end_headers()
                    threading.Thread(target=controller.open_page, daemon=True).start()
                    return
                if self.path == "/shutdown":
                    self.send_response(202)
                    self.end_headers()
                    threading.Thread(target=controller.shutdown, daemon=True).start()
                    return
                self.send_error(404)

            def log_message(self, format: str, *args: object) -> None:
                return

        self.token = token
        self.open_page = open_page
        self.shutdown = shutdown
        self._server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self._thread = threading.Thread(
            target=self._server.serve_forever,
            name="application-control",
            daemon=True,
        )

    @property
    def port(self) -> int:
        return int(self._server.server_port)

    def start(self) -> None:
        self._thread.start()

    def close(self) -> None:
        self._server.shutdown()
        self._server.server_close()
        self._thread.join(timeout=2)


class _WindowsSingleInstance:
    def __init__(self) -> None:
        self._handle: int | None = None

    def acquire(self) -> bool:
        if os.name != "nt":
            return True
        kernel32 = ctypes.windll.kernel32
        kernel32.CreateMutexW.restype = ctypes.c_void_p
        kernel32.CreateMutexW.argtypes = (
            ctypes.c_void_p,
            ctypes.c_int,
            ctypes.c_wchar_p,
        )
        handle = kernel32.CreateMutexW(None, False, _MUTEX_NAME)
        if not handle:
            raise OSError("无法创建程序单实例锁。")
        self._handle = int(handle)
        return kernel32.GetLastError() != 183

    def close(self) -> None:
        if self._handle is not None and os.name == "nt":
            ctypes.windll.kernel32.CloseHandle(self._handle)
            self._handle = None


def _write_control_state(
    path: Path,
    *,
    port: int,
    token: str,
    application_url: str | None = None,
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(".tmp")
    temporary.write_text(
        json.dumps(
            {
                "port": port,
                "token": token,
                "application_url": application_url,
            }
        ),
        encoding="utf-8",
    )
    temporary.replace(path)


def _send_control_request(path: Path, action: str, timeout: float = 1.5) -> bool:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
        port = int(payload["port"])
        token = str(payload["token"])
        request = Request(
            f"http://127.0.0.1:{port}/{action}",
            method="POST",
            headers={_CONTROL_TOKEN_HEADER: token},
        )
        with urlopen(request, timeout=timeout) as response:
            return response.status in {202, 204}
    except (OSError, ValueError, KeyError, TypeError, URLError, json.JSONDecodeError):
        return False


def terminate_process_tree(process: subprocess.Popen[bytes]) -> None:
    if process.poll() is not None:
        return
    if os.name == "nt":
        try:
            subprocess.run(
                ["taskkill", "/PID", str(process.pid), "/T", "/F"],
                check=False,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                timeout=8,
            )
        except (OSError, subprocess.SubprocessError):
            pass
    else:
        try:
            os.killpg(process.pid, signal.SIGTERM)
            process.wait(timeout=3)
        except (ProcessLookupError, subprocess.TimeoutExpired):
            try:
                os.killpg(process.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
    if process.poll() is None:
        try:
            process.kill()
        except OSError:
            pass
    try:
        process.wait(timeout=3)
    except subprocess.TimeoutExpired:
        pass


def _tray_image():
    from PIL import Image, ImageDraw

    image = Image.new("RGBA", (64, 64), (28, 105, 180, 255))
    draw = ImageDraw.Draw(image)
    draw.ellipse((13, 10, 43, 40), outline="white", width=6)
    draw.line((39, 37, 54, 53), fill="white", width=7)
    return image


def _start_worker(port: int, control: _ControlServer) -> subprocess.Popen[bytes]:
    environment = os.environ.copy()
    environment["STUDENT_CODE_DIAGNOSIS_CONTROL_URL"] = (
        f"http://127.0.0.1:{control.port}"
    )
    environment["STUDENT_CODE_DIAGNOSIS_CONTROL_TOKEN"] = control.token
    options: dict[str, object] = {"env": environment}
    if os.name == "nt":
        options["creationflags"] = subprocess.CREATE_NEW_PROCESS_GROUP
    else:
        options["start_new_session"] = True
    return subprocess.Popen(worker_command(port), **options)  # type: ignore[arg-type]


def _run_supervisor() -> int:
    import pystray

    state_path = control_state_path()
    instance = _WindowsSingleInstance()
    if not instance.acquire():
        try:
            for _ in range(10):
                if _send_control_request(state_path, "open"):
                    return 0
                time.sleep(0.2)
            return 1
        finally:
            instance.close()

    streamlit_port = available_port()
    page_url = f"http://127.0.0.1:{streamlit_port}"
    icon: pystray.Icon | None = None
    shutdown_requested = threading.Event()

    def open_page() -> None:
        webbrowser.open(page_url)

    def request_shutdown() -> None:
        shutdown_requested.set()
        if icon is not None:
            icon.stop()

    def tray_open_page(_icon: object, _item: object) -> None:
        open_page()

    def tray_request_shutdown(_icon: object, _item: object) -> None:
        request_shutdown()

    control = _ControlServer(
        token=secrets.token_urlsafe(32),
        open_page=open_page,
        shutdown=request_shutdown,
    )
    worker: subprocess.Popen[bytes] | None = None
    try:
        control.start()
        _write_control_state(
            state_path,
            port=control.port,
            token=control.token,
            application_url=page_url,
        )
        worker = _start_worker(streamlit_port, control)
        if os.environ.get("STUDENT_CODE_DIAGNOSIS_NO_BROWSER") != "1":
            threading.Thread(
                target=_open_browser_when_ready,
                args=(streamlit_port,),
                daemon=True,
            ).start()

        def monitor_worker() -> None:
            worker.wait()
            request_shutdown()

        threading.Thread(target=monitor_worker, daemon=True).start()
        icon = pystray.Icon(
            "StudentCodeDiagnosis",
            _tray_image(),
            "学生代码诊断助手",
            menu=pystray.Menu(
                pystray.MenuItem("打开诊断页面", tray_open_page, default=True),
                pystray.MenuItem("退出程序", tray_request_shutdown),
            ),
        )
        if not shutdown_requested.is_set():
            icon.run()
        return 0
    finally:
        control.close()
        if worker is not None:
            terminate_process_tree(worker)
        try:
            state_path.unlink(missing_ok=True)
        except OSError:
            pass
        instance.close()


def main() -> int:
    if len(sys.argv) == 3 and sys.argv[1] == STREAMLIT_WORKER_ARGUMENT:
        try:
            port = int(sys.argv[2])
        except ValueError as exc:
            raise RuntimeError("后台服务端口无效。") from exc
        return _run_streamlit_worker(port)
    return _run_supervisor()


if __name__ == "__main__":
    raise SystemExit(main())
