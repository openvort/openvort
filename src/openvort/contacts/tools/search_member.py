"""搜索成员工具 — 按姓名/邮箱/手机搜索通讯录成员，支持中文称谓智能识别"""

import json

from openvort.contacts.service import ContactService
from openvort.db.engine import get_session_factory
from openvort.plugin.base import BaseTool

# Chinese honorific suffixes: 杨总 → 杨, 李老师 → 李
_HONORIFIC_SUFFIXES = ["老师", "老板", "同学", "总", "哥", "姐", "叔", "姨", "工", "爷"]
# Chinese honorific prefixes: 老杨 → 杨, 小李 → 李
_HONORIFIC_PREFIXES = ["老", "小", "阿"]


def _extract_names_from_nickname(keyword: str) -> list[str]:
    """Extract possible real name parts from Chinese nickname/honorific.

    Examples: "杨总" → ["杨"], "老杨" → ["杨"], "李老师" → ["李"]
    Returns empty list if no honorific pattern is detected.
    """
    names: list[str] = []

    for suffix in _HONORIFIC_SUFFIXES:
        if keyword.endswith(suffix) and len(keyword) > len(suffix):
            name = keyword[: -len(suffix)]
            if 1 <= len(name) <= 2:
                names.append(name)

    for prefix in _HONORIFIC_PREFIXES:
        if keyword.startswith(prefix) and len(keyword) > len(prefix):
            name = keyword[len(prefix) :]
            if 1 <= len(name) <= 2:
                names.append(name)

    return list(set(names))


class SearchMemberTool(BaseTool):
    name = "contacts_search"
    description = (
        "搜索通讯录成员，可按姓名、邮箱、手机号查找，返回成员信息及各平台身份映射。"
        "支持中文称谓/昵称搜索（如「杨总」「老王」「小李」「张工」「刘老师」等），"
        "会自动提取可能的姓名进行匹配，并列出候选人供确认。"
    )
    required_permission = "contacts.search"

    def input_schema(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "keyword": {
                    "type": "string",
                    "description": "搜索关键词（姓名/邮箱/手机号/中文称谓如'杨总''老王'）",
                },
            },
            "required": ["keyword"],
        }

    async def execute(self, params: dict) -> str:
        keyword = params["keyword"]
        service = ContactService(get_session_factory())
        members = await service.search_members(keyword)
        nickname_hint = ""

        if not members:
            possible_names = _extract_names_from_nickname(keyword)
            if possible_names:
                for name in possible_names:
                    members = await service.search_members_by_name_prefix(name)
                    if members:
                        nickname_hint = (
                            f"未找到完全匹配'{keyword}'的成员，"
                            f"已按姓名'{name}'进行模糊匹配，请根据姓名和职位确认目标人选"
                        )
                        break

        if not members:
            msg = f"未找到匹配 '{keyword}' 的成员"
            possible_names = _extract_names_from_nickname(keyword)
            if possible_names:
                msg += f"（已尝试按姓名'{'/'.join(possible_names)}'搜索，仍无匹配）"
            return json.dumps(
                {"ok": True, "count": 0, "members": [], "message": msg},
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
                "position": m.position or "",
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

        resp: dict = {"ok": True, "count": len(results), "members": results}
        if nickname_hint:
            resp["nickname_hint"] = nickname_hint
        return json.dumps(resp, ensure_ascii=False)
