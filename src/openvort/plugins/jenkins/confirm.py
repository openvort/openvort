"""
Jenkins 操作确认状态管理。

用于管理需要二次确认的写操作（create/update/delete/trigger_build）。
用户必须明确输入"确认"才能执行，输入其他内容无效。
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any

from openvort.utils.logging import get_logger

log = get_logger("plugins.jenkins.confirm")

# 超时时间（秒）
CONFIRM_TIMEOUT = 300  # 5 分钟


@dataclass
class PendingAction:
    """待确认的操作"""
    action: str  # 操作类型: create/update/delete/trigger_build
    tool: str  # 工具名
    params: dict[str, Any]  # 操作参数
    created_at: float = field(default_factory=time.time)
    instance_name: str = ""  # 用于显示给用户


class ConfirmManager:
    """确认状态管理器"""

    def __init__(self):
        self._pending: dict[str, PendingAction] = {}  # key: caller_id

    def _make_key(self, caller_id: str) -> str:
        """生成存储 key"""
        return caller_id

    def set_pending(
        self,
        caller_id: str,
        action: str,
        tool: str,
        params: dict[str, Any],
        instance_name: str = "",
    ) -> None:
        """设置待确认操作"""
        key = self._make_key(caller_id)
        self._pending[key] = PendingAction(
            action=action,
            tool=tool,
            params=params,
            instance_name=instance_name,
        )
        log.info(f"[Jenkins确认] 用户 {caller_id} 待确认操作: {action} ({tool})")

    def check_confirm(self, caller_id: str, user_input: str) -> tuple[bool, PendingAction | None]:
        """检查用户输入是否为"确认"
        
        Returns:
            (是否确认成功, 待确认操作信息)
        """
        key = self._make_key(caller_id)
        pending = self._pending.get(key)
        
        if not pending:
            return False, None
        
        # 检查是否超时
        if time.time() - pending.created_at > CONFIRM_TIMEOUT:
            log.info(f"[Jenkins确认] 用户 {caller_id} 的待确认操作已超时")
            self.clear_pending(caller_id)
            return False, None
        
        # 检查用户输入
        user_input = user_input.strip()
        if user_input == "确认":
            log.info(f"[Jenkins确认] 用户 {caller_id} 确认了操作: {pending.action}")
            self.clear_pending(caller_id)
            return True, pending
        
        return False, pending

    def get_pending(self, caller_id: str) -> PendingAction | None:
        """获取待确认操作"""
        key = self._make_key(caller_id)
        pending = self._pending.get(key)
        
        if pending and time.time() - pending.created_at > CONFIRM_TIMEOUT:
            self.clear_pending(caller_id)
            return None
        
        return pending

    def clear_pending(self, caller_id: str) -> None:
        """清除待确认操作"""
        key = self._make_key(caller_id)
        self._pending.pop(key, None)

    def has_pending(self, caller_id: str) -> bool:
        """检查是否有待确认操作"""
        return self.get_pending(caller_id) is not None


# 全局单例
_confirm_manager: ConfirmManager | None = None


def get_confirm_manager() -> ConfirmManager:
    """获取确认管理器单例"""
    global _confirm_manager
    if _confirm_manager is None:
        _confirm_manager = ConfirmManager()
    return _confirm_manager
