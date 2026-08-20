from services.runtime_error_explainer import runtime_error_causes


def test_segmentation_fault_maps_to_memory_and_boundary_causes() -> None:
    causes = runtime_error_causes(
        "The program return exit status code: 11 (Segmentation fault)"
    )

    assert any("无效内存" in item for item in causes)
    assert any("数组越界" in item for item in causes)


def test_common_runtime_messages_have_specific_chinese_causes() -> None:
    assert any("除零" in item for item in runtime_error_causes("Floating point exception"))
    assert any("内存" in item for item in runtime_error_causes("std::bad_alloc"))
    assert any("递归" in item for item in runtime_error_causes("stack overflow"))


def test_unknown_runtime_error_has_safe_fallback() -> None:
    causes = runtime_error_causes("exit code: 42")

    assert len(causes) == 1
    assert "数组边界" in causes[0]
