"""
迭代管理工具 -- vortflow_manage_iteration

创建、修改、删除迭代（Sprint）。
"""

import json

from sqlalchemy import delete as sa_delete, select

from openvort.plugin.base import BaseTool
from openvort.utils.logging import get_logger

log = get_logger("plugins.vortflow.tools.manage_iteration")


class ManageIterationTool(BaseTool):
    name = "vortflow_manage_iteration"
    description = (
        "管理 VortFlow 迭代（Sprint）。"
        "action=create 创建迭代，需提供项目 ID 和名称。"
        "action=update 修改迭代信息。"
        "action=delete 删除迭代（会清除关联关系，需用户确认「确认删除」）。"
    )
    required_permission = "vortflow.admin"

    def __init__(self, get_session_factory):
        self._get_sf = get_session_factory

    def input_schema(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "action": {
                    "type": "string",
                    "enum": ["create", "update", "delete"],
                    "description": "操作类型",
                },
                "iteration_id": {"type": "string", "description": "迭代 ID（update/delete 时必填）"},
                "project_id": {"type": "string", "description": "项目 ID（create 时必填）"},
                "name": {"type": "string", "description": "迭代名称（如 Sprint 1）"},
                "goal": {"type": "string", "description": "迭代目标", "default": ""},
                "start_date": {"type": "string", "description": "开始日期 YYYY-MM-DD"},
                "end_date": {"type": "string", "description": "结束日期 YYYY-MM-DD"},
                "status": {
                    "type": "string",
                    "enum": ["planning", "active", "completed"],
                    "description": "迭代状态",
                },
                "confirm_text": {"type": "string", "description": "删除确认文本"},
            },
            "required": ["action"],
        }

    async def execute(self, params: dict) -> str:
        from datetime import datetime

        from openvort.plugins.vortflow.models import (
            FlowEvent,
            FlowIteration,
            FlowIterationBug,
            FlowIterationStory,
            FlowIterationTask,
        )

        action = params["action"]
        member_id = params.get("_member_id", "")

        def _parse_dt(s):
            if not s:
                return None
            try:
                return datetime.strptime(s, "%Y-%m-%d")
            except ValueError:
                return None

        sf = self._get_sf()

        if action == "create":
            project_id = params.get("project_id", "")
            name = params.get("name", "")
            if not project_id or not name:
                return json.dumps({"ok": False, "message": "创建迭代需要提供 project_id 和 name"})

            async with sf() as session:
                it = FlowIteration(
                    project_id=project_id,
                    name=name,
                    goal=params.get("goal", ""),
                    start_date=_parse_dt(params.get("start_date", "")),
                    end_date=_parse_dt(params.get("end_date", "")),
                    status=params.get("status", "planning"),
                )
                session.add(it)
                await session.flush()
                event = FlowEvent(
                    entity_type="iteration", entity_id=it.id, action="created",
                    actor_id=member_id or None,
                    detail=json.dumps({"name": name}, ensure_ascii=False),
                )
                session.add(event)
                await session.commit()
                iteration_id = it.id

            return json.dumps({
                "ok": True,
                "message": f"迭代「{name}」已创建",
                "iteration_id": iteration_id,
            }, ensure_ascii=False)

        elif action == "update":
            iteration_id = params.get("iteration_id", "")
            if not iteration_id:
                return json.dumps({"ok": False, "message": "update 需要提供 iteration_id"})

            async with sf() as session:
                it = await session.get(FlowIteration, iteration_id)
                if not it:
                    return json.dumps({"ok": False, "message": "迭代不存在"})

                changes = {}
                for field in ("name", "goal", "status"):
                    if field in params and params[field] is not None:
                        setattr(it, field, params[field])
                        changes[field] = params[field]
                for df in ("start_date", "end_date"):
                    if df in params and params[df]:
                        setattr(it, df, _parse_dt(params[df]))
                        changes[df] = params[df]

                if not changes:
                    return json.dumps({"ok": False, "message": "未提供任何要修改的字段"})

                event = FlowEvent(
                    entity_type="iteration", entity_id=iteration_id, action="updated",
                    actor_id=member_id or None,
                    detail=json.dumps(changes, ensure_ascii=False),
                )
                session.add(event)
                await session.commit()

            return json.dumps({
                "ok": True,
                "message": f"迭代「{it.name}」已更新，修改字段: {'、'.join(changes.keys())}",
            }, ensure_ascii=False)

        elif action == "delete":
            iteration_id = params.get("iteration_id", "")
            confirm = params.get("confirm_text", "")
            if not iteration_id:
                return json.dumps({"ok": False, "message": "delete 需要提供 iteration_id"})
            if confirm != "确认删除":
                return json.dumps({
                    "ok": False,
                    "message": "删除迭代需要用户确认。请让用户回复「确认删除」后再调用。",
                }, ensure_ascii=False)

            async with sf() as session:
                it = await session.get(FlowIteration, iteration_id)
                if not it:
                    return json.dumps({"ok": False, "message": "迭代不存在"})
                name = it.name
                await session.execute(sa_delete(FlowIterationStory).where(FlowIterationStory.iteration_id == iteration_id))
                await session.execute(sa_delete(FlowIterationTask).where(FlowIterationTask.iteration_id == iteration_id))
                await session.execute(sa_delete(FlowIterationBug).where(FlowIterationBug.iteration_id == iteration_id))
                await session.delete(it)
                event = FlowEvent(
                    entity_type="iteration", entity_id=iteration_id, action="deleted",
                    actor_id=member_id or None,
                    detail=json.dumps({"name": name}, ensure_ascii=False),
                )
                session.add(event)
                await session.commit()

            return json.dumps({"ok": True, "message": f"迭代「{name}」已删除"}, ensure_ascii=False)

        return json.dumps({"ok": False, "message": f"未知操作: {action}"})
