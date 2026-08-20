import pytest

from services.json_http_client import JsonHttpResponse
from services.problem_importer import ProblemImportError, import_public_problem


class FakeTransport:
    def __init__(self, response):
        self.response = response
        self.calls = []

    def request_json(self, method, url, **kwargs):
        self.calls.append((method, url, kwargs))
        return self.response


def successful_response() -> JsonHttpResponse:
    return JsonHttpResponse(
        200,
        {
            "status": 200,
            "msg": "success",
            "data": {
                "problem": {
                    "problemId": "AC743",
                    "title": "数组中的行",
                    "description": "描述",
                    "input": "输入",
                    "output": "输出",
                    "hint": "提示",
                    "timeLimit": 1000,
                    "memoryLimit": 256,
                    "examples": "<input>1\r\n2</input><output>3\n</output>",
                }
            },
        },
    )


def test_public_problem_import_uses_fixed_api_and_preserves_newlines() -> None:
    transport = FakeTransport(successful_response())

    problem = import_public_problem(
        "https://www.vesibay.cn/problem/AC743", transport=transport
    )

    assert problem.title == "数组中的行"
    assert problem.examples[0].input_data == "1\r\n2"
    assert problem.examples[0].expected_output == "3"
    assert transport.calls[0][1] == (
        "https://www.vesibay.cn/api/get-problem-detail?problemId=AC743"
    )


def test_training_problem_url_reuses_public_problem_api() -> None:
    transport = FakeTransport(successful_response())

    import_public_problem(
        "https://www.vesibay.cn/training/2/problem/T1031", transport=transport
    )

    assert transport.calls[0][1].endswith("problemId=T1031")


def test_percent_encoded_chinese_problem_id_is_decoded_once() -> None:
    response = successful_response()
    response.payload["data"]["problem"]["problemId"] = "GESP202603-1 一级"
    transport = FakeTransport(response)

    problem = import_public_problem(
        "https://www.vesibay.cn/training/48/problem/GESP202603-1%20%E4%B8%80%E7%BA%A7",
        transport=transport,
    )

    assert problem.external_problem_id == "GESP202603-1 一级"
    assert transport.calls[0][1].endswith(
        "problemId=GESP202603-1%20%E4%B8%80%E7%BA%A7"
    )


@pytest.mark.parametrize(
    "url,message",
    [
        ("http://www.vesibay.cn/problem/AC743", "仅支持"),
        ("https://evil.example/problem/AC743", "仅支持"),
        ("https://www.vesibay.cn/group/1019/problem/X", "小组权限"),
        ("https://www.vesibay.cn/other/AC743", "仅支持"),
    ],
)
def test_problem_import_rejects_unsupported_or_unsafe_urls(url, message) -> None:
    with pytest.raises(ProblemImportError, match=message):
        import_public_problem(url, transport=FakeTransport(successful_response()))


def test_problem_import_rejects_server_failure() -> None:
    with pytest.raises(ProblemImportError, match="未能获取"):
        import_public_problem(
            "https://www.vesibay.cn/problem/AC743",
            transport=FakeTransport(JsonHttpResponse(500, {"msg": "error"})),
        )
