"""VortFlow 通知层"""

import json

from openvort.utils.logging import get_logger

log = get_logger("plugins.vortflow.notifier")


class Notifier:
    """通知层 — 接 EventBus + WebSocket manager 推送消息"""

    def __init__(self):
        self._event_bus = None
        self._ws_manager = None

    def set_event_bus(self, event_bus) -> None:
        self._event_bus = event_bus

    def set_ws_manager(self, ws_manager) -> None:
        self._ws_manager = ws_manager

    async def notify_member(self, member_id: str, title: str, message: str, data: dict | None = None) -> None:
        """通知指定成员（WebSocket + EventBus）"""
        payload = {
            "type": "vortflow_notification",
            "title": title,
            "message": message,
            "data": data or {},
        }

        # WebSocket 实时推送
        if self._ws_manager:
            try:
                await self._ws_manager.send_to(member_id, payload)
            except Exception as e:
                log.warning(f"WebSocket 推送失败: {e}")

        # EventBus 广播（IM 通道可监听）
        if self._event_bus:
            try:
                await self._event_bus.emit(
                    "flow.notify",
                    member_id=member_id,
                    title=title,
                    message=message,
                    data=data or {},
                )
            except Exception as e:
                log.warning(f"EventBus 通知失败: {e}")

        log.info(f"通知 {member_id}: {title}")

    async def notify_state_change(self, entity_type: str, entity_id: str, title: str,
                                  old_state: str, new_state: str, assignee_id: str | None = None) -> None:
        """状态变更通知"""
        message = f"{entity_type} 「{title}」状态变更: {old_state} → {new_state}"
        if assignee_id:
            await self.notify_member(assignee_id, "状态变更", message, {
                "entity_type": entity_type,
                "entity_id": entity_id,
                "old_state": old_state,
                "new_state": new_state,
            })

    async def notify_assignment(self, entity_type: str, entity_id: str, title: str,
                                assignee_id: str, role: str) -> None:
        """分配通知"""
        message = f"你被分配为 {entity_type} 「{title}」的{role}"
        await self.notify_member(assignee_id, "任务分配", message, {
            "entity_type": entity_type,
            "entity_id": entity_id,
            "role": role,
        })
