"""Skill use tool — let Agent query, load and manage skills on demand."""

from __future__ import annotations

import json
import uuid

from openvort.plugin.base import BaseTool
from openvort.utils.logging import get_logger

log = get_logger("skill.tools")


class SkillUseTool(BaseTool):
    name = "skill_use"
    description = (
        "管理和使用技能（Skill）。"
        "支持以下操作：\n"
        "- list：列出所有可用技能\n"
        "- get：获取指定技能的完整内容\n"
        "- create：创建新技能（公共或个人）\n"
        "- update：更新已有技能的名称、描述或内容\n"
        "- delete：删除技能（仅公共和个人可删除）\n"
        "- toggle：启用或禁用技能\n"
        "当用户要求查看、创建、编辑、删除技能时调用此工具。"
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
                    "enum": ["list", "get", "create", "update", "delete", "toggle"],
                    "description": (
                        "操作类型：list 列出技能，get 获取内容，"
                        "create 创建技能，update 更新技能，delete 删除技能，toggle 启用/禁用"
                    ),
                },
                "name": {
                    "type": "string",
                    "description": "技能名称（get/create/update/delete 时使用）",
                },
                "skill_id": {
                    "type": "string",
                    "description": "技能 ID（update/delete/toggle 时可用，与 name 二选一）",
                },
                "description": {
                    "type": "string",
                    "description": "技能描述（create/update 时使用）",
                },
                "content": {
                    "type": "string",
                    "description": "技能内容，Markdown 格式（create/update 时使用）",
                },
                "scope": {
                    "type": "string",
                    "enum": ["public", "personal"],
                    "description": "技能范围：public 公共（所有人可用），personal 个人（仅创建者可用）。默认 public",
                },
                "tags": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "标签列表（create/update 时使用）",
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
        elif action == "create":
            return await self._create_skill(params)
        elif action == "update":
            return await self._update_skill(params)
        elif action == "delete":
            return await self._delete_skill(params)
        elif action == "toggle":
            return await self._toggle_skill(params)
        else:
            return json.dumps(
                {"ok": False, "message": f"不支持的操作: {action}，可用操作: list, get, create, update, delete, toggle"},
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
                                "id": row.id,
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

    async def _create_skill(self, params: dict) -> str:
        name = (params.get("name") or "").strip()
        if not name:
            return json.dumps({"ok": False, "message": "请提供技能名称（name 参数）"}, ensure_ascii=False)

        description = params.get("description", "")
        content = params.get("content", "")
        scope = params.get("scope", "public")
        tags = params.get("tags", [])
        caller_id = params.get("_caller_member_id", "") or params.get("_member_id", "")

        if scope not in ("public", "personal"):
            return json.dumps({"ok": False, "message": "scope 仅支持 public 或 personal"}, ensure_ascii=False)

        try:
            sf = self._get_session_factory()
        except Exception as e:
            log.error(f"获取数据库会话失败: {e}")
            return json.dumps({"ok": False, "message": "技能服务未就绪"}, ensure_ascii=False)

        from sqlalchemy import select, func
        from openvort.db.models import Skill as SkillModel

        try:
            async with sf() as db:
                existing = await db.execute(
                    select(SkillModel).where(
                        func.lower(SkillModel.name) == name.lower(),
                        SkillModel.scope.in_(["builtin", "public", "personal"]),
                    )
                )
                if existing.scalars().first():
                    return json.dumps({"ok": False, "message": f"技能 '{name}' 已存在"}, ensure_ascii=False)

                skill_id = uuid.uuid4().hex
                skill = SkillModel(
                    id=skill_id,
                    name=name,
                    description=description,
                    content=content,
                    scope=scope,
                    skill_type="workflow",
                    tags=json.dumps(tags, ensure_ascii=False) if tags else "",
                    owner_id=caller_id if scope == "personal" else "",
                    created_by=caller_id,
                )
                db.add(skill)
                await db.commit()

            log.info(f"通过 chat 创建技能: name={name}, scope={scope}, creator={caller_id}")
            return json.dumps({
                "ok": True,
                "message": f"技能 '{name}' 创建成功",
                "skill": {"id": skill_id, "name": name, "scope": scope},
            }, ensure_ascii=False)

        except Exception as e:
            log.error(f"创建技能失败: {e}")
            return json.dumps({"ok": False, "message": f"创建失败: {e}"}, ensure_ascii=False)

    async def _update_skill(self, params: dict) -> str:
        try:
            sf = self._get_session_factory()
        except Exception as e:
            log.error(f"获取数据库会话失败: {e}")
            return json.dumps({"ok": False, "message": "技能服务未就绪"}, ensure_ascii=False)

        from sqlalchemy import select, func
        from openvort.db.models import Skill as SkillModel

        skill_id = params.get("skill_id", "")
        name = (params.get("name") or "").strip()
        if not skill_id and not name:
            return json.dumps({"ok": False, "message": "请提供 skill_id 或 name 来定位要更新的技能"}, ensure_ascii=False)

        try:
            async with sf() as db:
                if skill_id:
                    row = await db.get(SkillModel, skill_id)
                else:
                    result = await db.execute(
                        select(SkillModel).where(func.lower(SkillModel.name) == name.lower())
                    )
                    row = result.scalars().first()

                if not row:
                    label = skill_id or name
                    return json.dumps({"ok": False, "message": f"未找到技能 '{label}'"}, ensure_ascii=False)

                if row.scope == "builtin":
                    return json.dumps({"ok": False, "message": "内置技能不可编辑"}, ensure_ascii=False)

                new_desc = params.get("description")
                if new_desc is not None:
                    row.description = new_desc
                new_content = params.get("content")
                if new_content is not None:
                    row.content = new_content
                tags = params.get("tags")
                if tags is not None:
                    row.tags = json.dumps(tags, ensure_ascii=False)

                await db.commit()

            log.info(f"通过 chat 更新技能: id={row.id}, name={row.name}")
            return json.dumps({
                "ok": True,
                "message": f"技能 '{row.name}' 更新成功",
                "skill": {"id": row.id, "name": row.name, "scope": row.scope},
            }, ensure_ascii=False)

        except Exception as e:
            log.error(f"更新技能失败: {e}")
            return json.dumps({"ok": False, "message": f"更新失败: {e}"}, ensure_ascii=False)

    async def _delete_skill(self, params: dict) -> str:
        try:
            sf = self._get_session_factory()
        except Exception as e:
            log.error(f"获取数据库会话失败: {e}")
            return json.dumps({"ok": False, "message": "技能服务未就绪"}, ensure_ascii=False)

        from sqlalchemy import select, func, delete
        from openvort.db.models import Skill as SkillModel, MemberSkill, PostSkill

        skill_id = params.get("skill_id", "")
        name = (params.get("name") or "").strip()
        if not skill_id and not name:
            return json.dumps({"ok": False, "message": "请提供 skill_id 或 name 来定位要删除的技能"}, ensure_ascii=False)

        try:
            async with sf() as db:
                if skill_id:
                    row = await db.get(SkillModel, skill_id)
                else:
                    result = await db.execute(
                        select(SkillModel).where(func.lower(SkillModel.name) == name.lower())
                    )
                    row = result.scalars().first()

                if not row:
                    label = skill_id or name
                    return json.dumps({"ok": False, "message": f"未找到技能 '{label}'"}, ensure_ascii=False)

                if row.scope == "builtin":
                    return json.dumps({"ok": False, "message": "内置技能不可删除"}, ensure_ascii=False)

                deleted_name = row.name
                deleted_id = row.id
                await db.execute(delete(MemberSkill).where(MemberSkill.skill_id == row.id))
                await db.execute(delete(PostSkill).where(PostSkill.skill_id == row.id))
                await db.delete(row)
                await db.commit()

            log.info(f"通过 chat 删除技能: id={deleted_id}, name={deleted_name}")
            return json.dumps({
                "ok": True,
                "message": f"技能 '{deleted_name}' 已删除",
            }, ensure_ascii=False)

        except Exception as e:
            log.error(f"删除技能失败: {e}")
            return json.dumps({"ok": False, "message": f"删除失败: {e}"}, ensure_ascii=False)

    async def _toggle_skill(self, params: dict) -> str:
        try:
            sf = self._get_session_factory()
        except Exception as e:
            log.error(f"获取数据库会话失败: {e}")
            return json.dumps({"ok": False, "message": "技能服务未就绪"}, ensure_ascii=False)

        from sqlalchemy import select, func
        from openvort.db.models import Skill as SkillModel

        skill_id = params.get("skill_id", "")
        name = (params.get("name") or "").strip()
        if not skill_id and not name:
            return json.dumps({"ok": False, "message": "请提供 skill_id 或 name"}, ensure_ascii=False)

        try:
            async with sf() as db:
                if skill_id:
                    row = await db.get(SkillModel, skill_id)
                else:
                    result = await db.execute(
                        select(SkillModel).where(func.lower(SkillModel.name) == name.lower())
                    )
                    row = result.scalars().first()

                if not row:
                    label = skill_id or name
                    return json.dumps({"ok": False, "message": f"未找到技能 '{label}'"}, ensure_ascii=False)

                row.enabled = not row.enabled
                new_state = row.enabled
                skill_name = row.name
                await db.commit()

            state_text = "启用" if new_state else "禁用"
            log.info(f"通过 chat 切换技能状态: name={skill_name}, enabled={new_state}")
            return json.dumps({
                "ok": True,
                "message": f"技能 '{skill_name}' 已{state_text}",
                "enabled": new_state,
            }, ensure_ascii=False)

        except Exception as e:
            log.error(f"切换技能状态失败: {e}")
            return json.dumps({"ok": False, "message": f"操作失败: {e}"}, ensure_ascii=False)
