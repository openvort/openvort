"""企业微信通道工具 — 让 AI 能主动发送企微消息"""

import json

from openvort.plugin.base import BaseTool
from openvort.utils.logging import get_logger

log = get_logger("channels.wecom.tools")


class SendWeComMessageTool(BaseTool):
    """通过企业微信发送消息给指定用户"""

    name = "wecom_send_message"
    description = (
        "通过企业微信给指定用户发送消息。"
        "需要提供用户的企微 user_id（可先用 contacts_search 搜索获取）和消息内容。"
    )
    required_permission = "wecom.send"

    def __init__(self, channel=None):
        self._channel = channel

    def set_channel(self, channel) -> None:
        self._channel = channel

    def input_schema(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "user_id": {
                    "type": "string",
                    "description": "企业微信用户 ID（可通过 contacts_search 工具搜索成员获取其企微身份的 user_id）",
                },
                "content": {
                    "type": "string",
                    "description": "要发送的消息内容",
                },
            },
            "required": ["user_id", "content"],
        }

    async def execute(self, params: dict) -> str:
        user_id = params.get("user_id", "").strip()
        content = params.get("content", "").strip()

        if not user_id:
            return json.dumps({"ok": False, "message": "缺少 user_id 参数"}, ensure_ascii=False)
        if not content:
            return json.dumps({"ok": False, "message": "缺少 content 参数"}, ensure_ascii=False)

        if not self._channel:
            return json.dumps({"ok": False, "message": "企微通道未初始化"}, ensure_ascii=False)
        if not self._channel.is_configured():
            return json.dumps({"ok": False, "message": "企微通道未配置"}, ensure_ascii=False)

        try:
            from openvort.plugin.base import Message
            await self._channel.send(user_id, Message(content=content, channel="wecom"))
            log.info(f"已发送企微消息: {user_id} <- {content[:50]}")
            return json.dumps({"ok": True, "message": f"已成功发送消息给 {user_id}"}, ensure_ascii=False)
        except Exception as e:
            log.error(f"发送企微消息失败: {e}")
            return json.dumps({"ok": False, "message": f"发送失败: {e}"}, ensure_ascii=False)
