from ui.components.testcase_details import (
    case_selection_key,
    detail_tab_labels,
    status_card_view,
)


def test_testcase_status_cards_use_required_labels_and_tones() -> None:
    assert status_card_view("AC") == ("AC", "success")
    assert status_card_view("WA") == ("WA", "error")
    assert status_card_view("RE") == ("RE", "error")
    assert status_card_view("TLE") == ("TLE", "error")


def test_checkbox_keys_are_stable_and_submission_specific() -> None:
    assert case_selection_key("48543", 0, "1") == "oj_case_selected_48543_0_1"
    assert case_selection_key("48544", 0, "1") != case_selection_key("48543", 0, "1")


def test_wa_details_only_show_reliable_oj_evidence() -> None:
    assert detail_tab_labels("WA") == ("输入数据", "标准输出")
    assert detail_tab_labels("WA", True) == (
        "输入数据",
        "标准输出",
        "学生实际输出",
    )


def test_re_details_include_error_input_and_expected_output() -> None:
    assert detail_tab_labels("RE") == ("运行错误", "输入数据", "标准输出")
    assert detail_tab_labels("RE", True) == (
        "运行错误",
        "输入数据",
        "标准输出",
        "本地运行",
    )
