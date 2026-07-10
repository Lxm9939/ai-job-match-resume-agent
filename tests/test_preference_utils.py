from __future__ import annotations

from src.utils.preference_utils import resolve_target_role, target_role_error_message


def test_custom_target_role_has_priority_over_dropdown() -> None:
    assert resolve_target_role("AI 产品经理", "算法产品经理") == "算法产品经理"


def test_dropdown_target_role_is_used_when_custom_is_empty() -> None:
    assert resolve_target_role("数据分析师", "  ") == "数据分析师"


def test_other_without_custom_target_role_has_clear_message() -> None:
    assert resolve_target_role("其他", "") == ""

    message = target_role_error_message("其他", "")

    assert "自定义目标岗位方向" in message
