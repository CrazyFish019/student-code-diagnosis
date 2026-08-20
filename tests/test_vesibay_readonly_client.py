import io
import zipfile

from services.binary_http_client import BinaryHttpResponse
from services.json_http_client import JsonHttpResponse
from services.vesibay_readonly_client import (
    VesibayAccessError,
    VesibayCredentials,
    VesibayReadOnlyClient,
    parse_submission_url,
)


class FakeTransport:
    def __init__(self, responses: dict[tuple[str, str], JsonHttpResponse]) -> None:
        self.responses = responses
        self.calls: list[tuple[str, str, dict[str, str], dict | None]] = []

    def request_json(
        self,
        method,
        url,
        *,
        headers=None,
        payload=None,
        timeout_seconds=30,
    ):
        self.calls.append((method, url, headers or {}, payload))
        return self.responses[(method, url)]


class FakeBinaryTransport:
    def __init__(self, response: BinaryHttpResponse) -> None:
        self.response = response
        self.calls: list[tuple[str, str, dict[str, str]]] = []

    def request(self, method, url, *, headers=None, timeout_seconds=60):
        self.calls.append((method, url, headers or {}))
        return self.response


def _testcase_zip(files: dict[str, bytes]) -> bytes:
    stream = io.BytesIO()
    with zipfile.ZipFile(stream, "w", zipfile.ZIP_DEFLATED) as archive:
        for name, content in files.items():
            archive.writestr(name, content)
    return stream.getvalue()


def _problem_response() -> JsonHttpResponse:
    return JsonHttpResponse(
        200,
        {
            "status": 200,
            "data": {
                "problem": {
                    "problemId": "P1000",
                    "title": "A+B",
                    "description": "求和",
                    "input": "两个整数",
                    "output": "它们的和",
                    "hint": "",
                    "timeLimit": 1000,
                    "memoryLimit": 128,
                    "examples": "<input>1 2</input><output>3</output>",
                }
            },
        },
    )


def _transport() -> FakeTransport:
    base = "https://www.vesibay.cn"
    return FakeTransport(
        {
            ("POST", base + "/api/admin/login"): JsonHttpResponse(
                200, {"status": 200, "data": {}}, {"Authorization": "token"}
            ),
            ("GET", base + "/api/get-user-auth-info"): JsonHttpResponse(
                200, {"status": 200, "data": {"roles": ["root"]}}
            ),
            (
                "GET",
                base + "/api/get-submission-detail?submitId=48543",
            ): JsonHttpResponse(
                200,
                {
                    "status": 200,
                    "data": {
                        "submission": {
                            "submitId": 48543,
                            "displayPid": "P1000",
                            "status": 8,
                            "score": 50,
                            "code": "int main() { return 0; }",
                            "username": "must-not-leak",
                            "ip": "127.0.0.1",
                        }
                    },
                },
            ),
            (
                "GET",
                base + "/api/get-all-case-result?submitId=48543",
            ): JsonHttpResponse(
                200,
                {
                    "status": 200,
                    "data": {
                        "judgeCaseList": [
                            {
                                "caseId": 1,
                                "status": 0,
                                "time": 3,
                                "memory": 1024,
                                "inputData": "1 2",
                                "outputData": "3",
                                "userOutput": "3",
                            },
                            {
                                "caseId": 2,
                                "status": -1,
                                "time": 4,
                                "memory": 1024,
                                "inputData": "2 3",
                                "outputData": "5",
                                "userOutput": "4",
                            },
                        ],
                        "subTaskJudgeCaseVoList": [],
                    },
                },
            ),
            (
                "GET",
                base + "/api/get-problem-detail?problemId=P1000",
            ): _problem_response(),
        }
    )


def test_parse_submission_url_accepts_all_same_site_submission_routes() -> None:
    assert parse_submission_url(
        "https://www.vesibay.cn/submission-detail/48543"
    ) == "48543"
    assert parse_submission_url(
        "https://www.vesibay.cn/group/1019/submission-detail/48304"
    ) == "48304"
    assert parse_submission_url(
        "https://www.vesibay.cn/contest/1534/problem/002/submission-detail/45762"
    ) == "45762"
    assert parse_submission_url(
        "https://www.vesibay.cn/training/48/problem/P1000/submission-detail/45763?from=list"
    ) == "45763"

    for invalid in (
        "",
        "http://www.vesibay.cn/submission-detail/48543",
        "https://evil.example/submission-detail/48543",
        "https://www.vesibay.cn/submission-detail/not-a-number",
        "https://www.vesibay.cn/problem/P1000",
    ):
        try:
            parse_submission_url(invalid)
        except VesibayAccessError:
            pass
        else:
            raise AssertionError(f"accepted invalid URL: {invalid}")


def test_wrong_host_uses_teacher_facing_domain_message() -> None:
    try:
        parse_submission_url("https://other-oj.example/submission-detail/48543")
    except VesibayAccessError as exc:
        assert str(exc) == "网址必须是指定题目网站的提交详情页面。"
    else:
        raise AssertionError("wrong host was not rejected")


def test_same_site_non_submission_url_does_not_use_wrong_site_message() -> None:
    try:
        parse_submission_url("https://www.vesibay.cn/problem/P1000")
    except VesibayAccessError as exc:
        assert "没有可识别的提交编号" in str(exc)
        assert str(exc) != "网址必须是指定题目网站的提交详情页面。"
    else:
        raise AssertionError("non-submission URL was not rejected")


def test_verify_credentials_uses_authorization_header() -> None:
    transport = _transport()
    client = VesibayReadOnlyClient(transport=transport)

    client.verify_credentials(VesibayCredentials("admin", "password"))

    assert transport.calls[0][3] == {"username": "admin", "password": "password"}
    assert transport.calls[1][2]["Authorization"] == "token"


def test_import_submission_returns_sanitized_problem_source_and_cases() -> None:
    transport = _transport()

    result = VesibayReadOnlyClient(transport=transport).import_submission(
        "https://www.vesibay.cn/submission-detail/48543",
        VesibayCredentials("admin", "password"),
    )

    assert result.submission_id == "48543"
    assert result.problem.external_problem_id == "P1000"
    assert result.source_code == "int main() { return 0; }"
    assert result.final_status == "PARTIAL_ACCEPTED"
    assert result.score == 50
    assert [item.status for item in result.cases] == ["AC", "WA"]
    assert result.cases[1].input_data == "2 3"
    assert not hasattr(result, "username")
    assert not hasattr(result, "ip")


def test_uploaded_testcase_filenames_are_replaced_with_archive_contents() -> None:
    transport = _transport()
    submission = transport.responses[
        ("GET", "https://www.vesibay.cn/api/get-submission-detail?submitId=48543")
    ].payload["data"]["submission"]
    submission["pid"] = 3255
    cases = transport.responses[
        ("GET", "https://www.vesibay.cn/api/get-all-case-result?submitId=48543")
    ].payload["data"]["judgeCaseList"]
    cases[0]["inputData"] = "1.in"
    cases[0]["outputData"] = "1.out"
    cases[1]["inputData"] = "nested/2.in"
    cases[1]["outputData"] = "nested/2.out"
    binary = FakeBinaryTransport(
        BinaryHttpResponse(
            200,
            {"Content-Type": "application/x-download"},
            _testcase_zip(
                {
                    "archive/1.in": b"1 2\n",
                    "archive/1.out": b"3\n",
                    "archive/2.in": "中文输入\n".encode(),
                    "archive/2.out": b"5\n",
                }
            ),
        )
    )

    result = VesibayReadOnlyClient(
        transport=transport, binary_transport=binary
    ).import_submission(
        "https://www.vesibay.cn/submission-detail/48543",
        VesibayCredentials("admin", "password"),
    )

    assert result.cases[0].input_data == "1 2\n"
    assert result.cases[0].expected_output == "3\n"
    assert result.cases[1].input_data == "中文输入\n"
    assert result.cases[1].expected_output == "5\n"
    assert binary.calls[0][1].endswith("download-testcase?pid=3255")
    assert binary.calls[0][2]["Authorization"] == "token"


def test_runtime_error_uses_oj_user_output_as_error_message() -> None:
    transport = _transport()
    cases = transport.responses[
        ("GET", "https://www.vesibay.cn/api/get-all-case-result?submitId=48543")
    ].payload["data"]["judgeCaseList"]
    cases[1]["status"] = 3
    cases[1]["userOutput"] = (
        "The program return exit status code: 11 (Segmentation fault)"
    )

    result = VesibayReadOnlyClient(transport=transport).import_submission(
        "https://www.vesibay.cn/submission-detail/48543",
        VesibayCredentials("admin", "password"),
    )

    assert result.cases[1].status == "RE"
    assert "Segmentation fault" in result.cases[1].error_message


def test_login_failure_is_teacher_facing_result() -> None:
    transport = _transport()
    transport.responses[("POST", "https://www.vesibay.cn/api/admin/login")] = (
        JsonHttpResponse(401, {"status": 401, "msg": "bad login"})
    )

    try:
        VesibayReadOnlyClient(transport=transport).verify_credentials(
            VesibayCredentials("admin", "wrong")
        )
    except VesibayAccessError as exc:
        assert "无效" in str(exc)
    else:
        raise AssertionError("login failure was not rejected")


def test_submission_permission_failure_is_teacher_facing_result() -> None:
    transport = _transport()
    transport.responses[
        ("GET", "https://www.vesibay.cn/api/get-submission-detail?submitId=48543")
    ] = JsonHttpResponse(403, {"status": 403, "msg": "forbidden"})

    try:
        VesibayReadOnlyClient(transport=transport).import_submission(
            "https://www.vesibay.cn/group/1019/submission-detail/48543",
            VesibayCredentials("admin", "password"),
        )
    except VesibayAccessError as exc:
        assert "无权" in str(exc)
    else:
        raise AssertionError("permission failure was not rejected")


def test_payload_permission_and_missing_submission_are_distinguished() -> None:
    credentials = VesibayCredentials("admin", "password")
    for status, message in ((403, "无权"), (404, "没有找到")):
        transport = _transport()
        transport.responses[
            ("GET", "https://www.vesibay.cn/api/get-submission-detail?submitId=48543")
        ] = JsonHttpResponse(200, {"status": status, "msg": "site message"})

        try:
            VesibayReadOnlyClient(transport=transport).import_submission(
                "https://www.vesibay.cn/contest/1534/problem/002/submission-detail/48543",
                credentials,
            )
        except VesibayAccessError as exc:
            assert message in str(exc)
        else:
            raise AssertionError(f"payload status {status} was not rejected")
