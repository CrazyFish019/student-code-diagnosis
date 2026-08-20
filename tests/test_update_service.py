from services.json_http_client import JsonHttpResponse
from services.update_service import UpdateCheckError, check_for_updates


class FakeTransport:
    def __init__(self, response: JsonHttpResponse) -> None:
        self.response = response
        self.calls = []

    def request_json(self, method, url, **kwargs):
        self.calls.append((method, url, kwargs))
        return self.response


def test_newer_github_release_and_installer_are_detected() -> None:
    transport = FakeTransport(
        JsonHttpResponse(
            200,
            {
                "tag_name": "v1.2.0",
                "html_url": "https://github.com/teacher/tool/releases/tag/v1.2.0",
                "assets": [
                    {
                        "name": "StudentCodeDiagnosis-Setup-1.2.0.exe",
                        "browser_download_url": "https://github.com/teacher/tool/releases/download/v1.2.0/setup.exe",
                    }
                ],
            },
        )
    )

    info = check_for_updates(
        repository="teacher/tool", current_version="1.0.0", transport=transport
    )

    assert info.update_available is True
    assert info.installer_url is not None
    assert transport.calls[0][1].endswith("/repos/teacher/tool/releases/latest")
    assert transport.calls[0][2]["headers"]["User-Agent"].endswith("/1.0.0")


def test_same_release_is_not_an_update() -> None:
    info = check_for_updates(
        repository="teacher/tool",
        current_version="1.0.0",
        transport=FakeTransport(
            JsonHttpResponse(
                200,
                {
                    "tag_name": "v1.0.0",
                    "html_url": "https://github.com/teacher/tool/releases/tag/v1.0.0",
                    "assets": [],
                },
            )
        ),
    )

    assert info.update_available is False


def test_update_source_and_missing_release_fail_safely() -> None:
    try:
        check_for_updates(repository="", transport=FakeTransport(JsonHttpResponse(200, {})))
    except UpdateCheckError as exc:
        assert "更新源" in str(exc)
    else:
        raise AssertionError("empty repository was accepted")

    try:
        check_for_updates(
            repository="teacher/tool",
            transport=FakeTransport(JsonHttpResponse(404, {})),
        )
    except UpdateCheckError as exc:
        assert "正式版本" in str(exc)
    else:
        raise AssertionError("missing release was accepted")
