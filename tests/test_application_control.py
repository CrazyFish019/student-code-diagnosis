from threading import Event

import pytest

import launcher
from services.application_control import (
    ApplicationControlError,
    application_shutdown_available,
    request_application_shutdown,
)


def test_page_shutdown_control_is_hidden_without_packaged_launcher(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("STUDENT_CODE_DIAGNOSIS_CONTROL_URL", raising=False)
    monkeypatch.delenv("STUDENT_CODE_DIAGNOSIS_CONTROL_TOKEN", raising=False)

    assert application_shutdown_available() is False
    with pytest.raises(ApplicationControlError, match="不支持"):
        request_application_shutdown()


def test_authenticated_local_control_opens_page_and_stops_application(
    tmp_path, monkeypatch: pytest.MonkeyPatch
) -> None:
    opened = Event()
    stopped = Event()
    controller = launcher._ControlServer(
        token="local-secret",
        open_page=opened.set,
        shutdown=stopped.set,
    )
    controller.start()
    state_path = tmp_path / "launcher.json"
    launcher._write_control_state(
        state_path,
        port=controller.port,
        token="local-secret",
    )
    monkeypatch.setenv(
        "STUDENT_CODE_DIAGNOSIS_CONTROL_URL",
        f"http://127.0.0.1:{controller.port}",
    )
    monkeypatch.setenv("STUDENT_CODE_DIAGNOSIS_CONTROL_TOKEN", "local-secret")
    try:
        assert launcher._send_control_request(state_path, "open") is True
        assert opened.wait(timeout=1)
        assert application_shutdown_available() is True
        request_application_shutdown()
        assert stopped.wait(timeout=1)
    finally:
        controller.close()


def test_local_control_rejects_an_invalid_token(tmp_path) -> None:
    controller = launcher._ControlServer(
        token="correct-token",
        open_page=lambda: None,
        shutdown=lambda: None,
    )
    controller.start()
    state_path = tmp_path / "launcher.json"
    launcher._write_control_state(
        state_path,
        port=controller.port,
        token="wrong-token",
    )
    try:
        assert launcher._send_control_request(state_path, "shutdown") is False
    finally:
        controller.close()
