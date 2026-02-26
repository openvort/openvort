"""搜索成员工具 — 按姓名/邮箱/手机搜索通讯录成员，返回平台身份映射"""

import json

from openvort.contacts.service import ContactService
from openvort.db.engine import get_session_factory
from openvort.plugin.base import BaseTool


class SearchMemberTool(BaseTool):
    name = "contacts_search"
    description = "搜索通讯录成员，可按姓名、邮箱、手机号查找，返回成员信息及各平台身份映射"
    required_permission = "contacts.search"

    def input_schema(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "keyword": {
                    "type": "string",
                    "description": "搜索关键词（姓名/邮箱/手机号）",
                },
            },
            "required": ["keyword"],
        }

    async def execute(self, params: dict) -> str:
        keyword = params["keyword"]
        service = ContactService(get_session_factory())
        members = await service.search_members(keyword)

        if not members:
            return json.dumps(
                {"ok": True, "count": 0, "members": [], "message": f"未找到匹配 '{keyword}' 的成员"},
                ensure_ascii=False,
            )

        results = []
        for m in members:
            identities = await service.get_member_identities(m.id)
            results.append({
                "id": m.id,
                "name": m.name,
                "email": m.email,
                "phone": m.phone,
                "status": m.status,
                "identities": [
                    {
                        "platform": i.platform,
                        "user_id": i.platform_user_id,
                        "username": i.platform_username,
                        "display_name": i.platform_display_name,
                        "position": i.platform_position,
                        "department": i.platform_department,
                    }
                    for i in identities
                ],
            })

        return json.dumps({"ok": True, "count": len(results), "members": results}, ensure_ascii=False)
