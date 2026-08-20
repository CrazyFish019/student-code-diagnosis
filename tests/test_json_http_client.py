import http.client

import pytest

from services.json_http_client import NetworkRequestError, UrllibJsonHttpTransport


class _IncompleteResponse:
    status = 200
    headers = {}

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, traceback):
        return False

    def read(self, size):
        raise http.client.IncompleteRead(b"")


class _IncompleteOpener:
    def open(self, request, timeout):
        return _IncompleteResponse()


def test_incomplete_chunked_response_becomes_network_error() -> None:
    transport = UrllibJsonHttpTransport()
    transport._opener = _IncompleteOpener()

    with pytest.raises(NetworkRequestError, match="失败或超时"):
        transport.request_json("GET", "https://models.example/v1/models")
