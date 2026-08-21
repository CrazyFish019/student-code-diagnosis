from models.code_language import CodeLanguage


def test_supported_language_metadata_is_explicit() -> None:
    assert CodeLanguage.CPP.value == "cpp"
    assert CodeLanguage.CPP.display_name == "C++"
    assert CodeLanguage.CPP.syntax_name == "cpp"
    assert CodeLanguage.PYTHON.value == "python"
    assert CodeLanguage.PYTHON.display_name == "Python 3"
    assert CodeLanguage.PYTHON.syntax_name == "python"
