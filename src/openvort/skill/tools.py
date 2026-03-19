"""Skill use tool — let Agent query and load skills on demand."""

from __future__ import annotations

import json

from openvort.plugin.base import BaseTool
from openvort.utils.logging import get_logger

log = get_logger("skill.tools")


class SkillUseTool(BaseTool):
    name = "skill_use"
    description = (
        "查询和加载技能（Skill）内容。"
        "当用户要求使用某个技能、询问有哪些技能可用、或需要特定领域知识指导时调用此工具。"
        "支持两个动作：list（列出所有技能）、get（获取指定技能的完整内容）。"
    )

    def __init__(self):
        self._session_factory = None

    def _get_session_factory(self):
        if self._session_factory is None:
            from openvort.db.engine import get_session_factory
            self._session_factory = get_session_factory()
        return self._session_factory

    def input_schema(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "action": {
                    "type": "string",
                    "enum": ["list", "get"],
                    "description": "操作类型：list 列出所有可用技能，get 获取指定技能的完整内容",
                },
                "name": {
                    "type": "string",
                    "description": "技能名称（action 为 get 时必填）",
                },
            },
            "required": ["action"],
        }

    async def execute(self, params: dict) -> str:
        action = params.get("action", "")
        if action == "list":
            return await self._list_skills()
        elif action == "get":
            name = params.get("name", "")
            if not name:
                return json.dumps(
                    {"ok": False, "message": "请提供技能名称（name 参数）"},
                    ensure_ascii=False,
                )
            return await self._get_skill(name)
        else:
            return json.dumps(
                {"ok": False, "message": f"不支持的操作: {action}，可用操作: list, get"},
                ensure_ascii=False,
            )

    async def _list_skills(self) -> str:
        try:
            sf = self._get_session_factory()
        except Exception as e:
            log.error(f"获取数据库会话失败: {e}")
            return json.dumps({"ok": False, "message": "技能服务未就绪"}, ensure_ascii=False)

        from sqlalchemy import select
        from openvort.db.models import Skill as SkillModel

        try:
            async with sf() as db:
                result = await db.execute(
                    select(SkillModel).order_by(SkillModel.scope, SkillModel.sort_order)
                )
                rows = result.scalars().all()
        except Exception as e:
            log.error(f"查询技能列表失败: {e}")
            return json.dumps({"ok": False, "message": f"查询失败: {e}"}, ensure_ascii=False)

        skills = []
        for row in rows:
            skills.append({
                "name": row.name,
                "description": row.description,
                "scope": row.scope,
                "skill_type": getattr(row, "skill_type", ""),
                "enabled": row.enabled,
            })

        return json.dumps(
            {"ok": True, "count": len(skills), "skills": skills},
            ensure_ascii=False,
        )

    async def _get_skill(self, name: str) -> str:
        try:
            sf = self._get_session_factory()
        except Exception as e:
            log.error(f"获取数据库会话失败: {e}")
            return json.dumps({"ok": False, "message": "技能服务未就绪"}, ensure_ascii=False)

        from sqlalchemy import select, func
        from openvort.db.models import Skill as SkillModel

        try:
            async with sf() as db:
                result = await db.execute(
                    select(SkillModel).where(
                        func.lower(SkillModel.name) == name.lower()
                    )
                )
                row = result.scalars().first()

                if row:
                    return json.dumps(
                        {
                            "ok": True,
                            "skill": {
                                "name": row.name,
                                "description": row.description,
                                "content": row.content,
                                "scope": row.scope,
                                "skill_type": getattr(row, "skill_type", ""),
                                "enabled": row.enabled,
                            },
                        },
                        ensure_ascii=False,
                    )

                all_result = await db.execute(select(SkillModel.name))
                available = [r[0] for r in all_result.all()]

        except Exception as e:
            log.error(f"查询技能失败: {e}")
            return json.dumps({"ok": False, "message": f"查询失败: {e}"}, ensure_ascii=False)

        return json.dumps(
            {
                "ok": False,
                "message": f"未找到技能 '{name}'",
                "available": available,
            },
            ensure_ascii=False,
        )
