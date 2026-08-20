import pytest

from services.output_compare import compare_output, normalize_output


def test_identical_output_matches() -> None:
    assert compare_output("1\n2\n3\n", "1\n2\n3\n")


def test_different_output_does_not_match() -> None:
    assert not compare_output("expected\n", "actual\n")


def test_crlf_and_lf_are_equivalent() -> None:
    assert compare_output("first\r\nsecond\r\n", "first\nsecond\n")


def test_trailing_spaces_and_tabs_are_ignored() -> None:
    assert compare_output("hello   \nworld\t\n", "hello\nworld\n")


def test_extra_blank_lines_are_ignored() -> None:
    assert compare_output("\n1\n2\n\n3\n", "1\n\n2\n3\n\n")


def test_content_order_remains_significant() -> None:
    assert not compare_output("1\n2\n3\n", "1\n3\n2\n")


@pytest.mark.parametrize(
    ("expected", "actual", "matches"),
    [
        ("", "", True),
        ("\n\n", "", True),
        ("", "content\n", False),
        ("content\n", "", False),
    ],
)
def test_empty_output_handling(expected: str, actual: str, matches: bool) -> None:
    assert compare_output(expected, actual) is matches


def test_chinese_output_matches() -> None:
    assert compare_output("答案：四十二  \r\n", "答案：四十二\n")


def test_leading_whitespace_is_not_removed() -> None:
    assert not compare_output("  indented\n", "indented\n")


def test_normalized_output_is_an_immutable_tuple() -> None:
    assert normalize_output("a\n\nb\n") == ("a", "b")
