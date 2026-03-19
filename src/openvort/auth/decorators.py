"""
权限检查工具

提供 Tool 执行前的权限校验辅助函数。
"""

import json


def permission_denied(permission: str) -> str:
    """返回权限不足的标准 JSON 响应"""
    return json.dumps(
        {"ok": False, "error": f"权限不足，需要 {permission} 权限，请联系管理员"},
        ensure_ascii=False,
    )
