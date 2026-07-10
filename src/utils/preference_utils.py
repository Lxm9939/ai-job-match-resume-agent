"""Helpers for resolving user preference inputs."""

from __future__ import annotations


def resolve_target_role(selected_role: str, custom_role: str) -> str:
    """Resolve target role with custom input taking precedence."""

    custom = (custom_role or "").strip()
    if custom:
        return custom

    selected = (selected_role or "").strip()
    if selected == "其他":
        return ""
    return selected


def target_role_error_message(selected_role: str, custom_role: str) -> str:
    """Return a clear validation message for incomplete target-role input."""

    if resolve_target_role(selected_role, custom_role):
        return ""
    if (selected_role or "").strip() == "其他":
        return "下拉选择为“其他”时，请填写具体的自定义目标岗位方向。"
    return "请选择常用方向，或输入更具体的目标岗位方向。"
