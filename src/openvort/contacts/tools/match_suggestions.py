"""查看匹配建议工具 — 管理员查看待确认的身份匹配建议"""

import json

from openvort.contacts.service import ContactService
from openvort.db.engine import get_session_factory
from openvort.plugin.base import BaseTool


class MatchSuggestionsTool(BaseTool):
    name = "contacts_match_suggestions"
    description = "查看待确认的通讯录匹配建议列表，需要管理员权限"
    required_permission = "contacts.match"

    def input_schema(self) -> dict:
        return {
            "type": "object",
            "properties": {},
        }

    async def execute(self, params: dict) -> str:
        service = ContactService(get_session_factory())
        suggestions = await service.list_pending_suggestions()

        if not suggestions:
            return json.dumps(
                {"ok": True, "count": 0, "suggestions": [], "message": "没有待确认的匹配建议"},
                ensure_ascii=False,
            )

        results = []
        for s in suggestions:
            results.append({
                "id": s.id,
                "source_identity_id": s.source_identity_id,
                "target_member_id": s.target_member_id,
                "match_type": s.match_type,
                "confidence": s.confidence,
            })

        return json.dumps({"ok": True, "count": len(results), "suggestions": results}, ensure_ascii=False)
