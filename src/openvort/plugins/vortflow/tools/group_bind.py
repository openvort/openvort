"""
群聊项目绑定工具 — group_bind_project

在群聊中将当前群与 VortFlow 项目关联/解绑/更新群名。
"""

import json

from openvort.plugin.base import BaseTool
from openvort.utils.logging import get_logger

log = get_logger("plugins.vortflow.tools.group_bind")


class GroupBindTool(BaseTool):
    name = "group_bind_project"
    description = (
        "管理当前群聊与 VortFlow 项目的关联关系。"
        "支持三种操作：bind（绑定项目）、unbind（解绑）、update_name（设置群名）。"
        "只能在群聊中使用。绑定后，该群的所有对话将自动关联到对应项目。"
    )

    def input_schema(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "action": {
                    "type": "string",
                    "enum": ["bind", "unbind", "update_name"],
                    "description": "操作类型：bind=绑定项目, unbind=解绑, update_name=设置群名",
                },
                "project_id": {
                    "type": "string",
                    "description": "VortFlow 项目 ID（bind 时必填）",
                },
                "group_name": {
                    "type": "string",
                    "description": "群名称（update_name 时必填，bind 时可选——同时更新群名记录）",
                },
            },
            "required": ["action"],
        }

    async def execute(self, params: dict) -> str:
        from openvort.core.messaging.group_context import group_context_manager as gcm

        caller_id = params.get("_caller_id", "")
        member_id = params.get("_member_id", "")

        if not caller_id.startswith("group:"):
            return json.dumps({"ok": False, "message": "此工具只能在群聊中使用"}, ensure_ascii=False)

        chat_id = caller_id[len("group:"):]
        action = params.get("action", "")

        if action == "bind":
            project_id = params.get("project_id", "")
            if not project_id:
                return json.dumps({"ok": False, "message": "bind 操作需要提供 project_id"}, ensure_ascii=False)

            result = await gcm.bind_project(chat_id, project_id, member_id)

            group_name = params.get("group_name", "")
            if group_name and result.get("ok"):
                await gcm.update_name(chat_id, group_name)

            return json.dumps(result, ensure_ascii=False)

        elif action == "unbind":
            result = await gcm.unbind_project(chat_id)
            return json.dumps(result, ensure_ascii=False)

        elif action == "update_name":
            group_name = params.get("group_name", "")
            if not group_name:
                return json.dumps({"ok": False, "message": "update_name 操作需要提供 group_name"}, ensure_ascii=False)

            result = await gcm.update_name(chat_id, group_name)
            return json.dumps(result, ensure_ascii=False)

        else:
            return json.dumps({"ok": False, "message": f"未知操作: {action}"}, ensure_ascii=False)
