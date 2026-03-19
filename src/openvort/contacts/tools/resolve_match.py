"""处理匹配建议工具 — 管理员接受或拒绝身份匹配建议"""

import json

from openvort.contacts.service import ContactService
from openvort.db.engine import get_session_factory
from openvort.plugin.base import BaseTool


class ResolveMatchTool(BaseTool):
    name = "contacts_resolve_match"
    description = "接受或拒绝通讯录匹配建议，需要管理员权限"
    required_permission = "contacts.match"

    def input_schema(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "suggestion_id": {
                    "type": "integer",
                    "description": "匹配建议 ID",
                },
                "action": {
                    "type": "string",
                    "description": "操作：accept（接受）或 reject（拒绝）",
                    "enum": ["accept", "reject"],
                },
            },
            "required": ["suggestion_id", "action"],
        }

    async def execute(self, params: dict) -> str:
        suggestion_id = params["suggestion_id"]
        action = params["action"]
        caller_id = params.get("_caller_id", "")

        service = ContactService(get_session_factory())

        if action == "accept":
            ok = await service.accept_suggestion(suggestion_id, resolved_by=caller_id)
        else:
            ok = await service.reject_suggestion(suggestion_id, resolved_by=caller_id)

        if ok:
            msg = f"已{'接受' if action == 'accept' else '拒绝'}匹配建议 #{suggestion_id}"
            return json.dumps({"ok": True, "message": msg}, ensure_ascii=False)
        else:
            return json.dumps(
                {"ok": False, "error": f"操作失败，建议 #{suggestion_id} 不存在或已处理"},
                ensure_ascii=False,
            )
