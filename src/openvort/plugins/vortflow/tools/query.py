"""
查询工具 — vortflow_query

查询项目、需求、任务、缺陷的状态和列表。
"""

import json

from sqlalchemy import func, select

from openvort.plugin.base import BaseTool
from openvort.utils.logging import get_logger

log = get_logger("plugins.vortflow.tools.query")


class QueryTool(BaseTool):
    name = "vortflow_query"
    description = (
        "查询 VortFlow 中的项目、需求、任务、缺陷信息。"
        "支持按项目列表、需求列表、任务列表、缺陷列表、项目成员查询，可按状态和负责人过滤。"
        "也可查询单个实体的详情。"
    )
    required_permission = "vortflow.story"

    def input_schema(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "query_type": {
                    "type": "string",
                    "description": "查询类型",
                    "enum": ["projects", "stories", "tasks", "bugs", "detail", "project_members"],
                },
                "project_id": {"type": "string", "description": "按项目过滤（可选）", "default": ""},
                "story_id": {"type": "string", "description": "按需求过滤任务/缺陷（可选）", "default": ""},
                "state": {"type": "string", "description": "按状态过滤（可选）", "default": ""},
                "assignee_id": {"type": "string", "description": "按负责人过滤（可选）", "default": ""},
                "entity_type": {"type": "string", "description": "detail 模式下的实体类型", "default": ""},
                "entity_id": {"type": "string", "description": "detail 模式下的实体 ID", "default": ""},
            },
            "required": ["query_type"],
        }

    async def execute(self, params: dict) -> str:
        from openvort.db.engine import get_session_factory
        from openvort.contacts.models import Member
        from openvort.plugins.vortflow.models import FlowBug, FlowProject, FlowProjectMember, FlowStory, FlowTask

        query_type = params["query_type"]
        sf = get_session_factory()  # QueryTool 无状态，直接获取

        async with sf() as session:
            if query_type == "projects":
                result = await session.execute(select(FlowProject).order_by(FlowProject.created_at.desc()).limit(50))
                rows = result.scalars().all()
                data = [{"id": r.id, "name": r.name, "product": r.product, "iteration": r.iteration,
                          "start_date": r.start_date.isoformat() if r.start_date else None,
                          "end_date": r.end_date.isoformat() if r.end_date else None} for r in rows]
                return json.dumps({"ok": True, "count": len(data), "projects": data}, ensure_ascii=False)

            elif query_type == "stories":
                stmt = select(FlowStory).order_by(FlowStory.created_at.desc()).limit(50)
                if params.get("project_id"):
                    stmt = stmt.where(FlowStory.project_id == params["project_id"])
                if params.get("state"):
                    stmt = stmt.where(FlowStory.state == params["state"])
                result = await session.execute(stmt)
                rows = result.scalars().all()
                data = [{"id": r.id, "title": r.title, "state": r.state, "priority": r.priority,
                          "pm_id": r.pm_id, "deadline": r.deadline.isoformat() if r.deadline else None} for r in rows]
                return json.dumps({"ok": True, "count": len(data), "stories": data}, ensure_ascii=False)

            elif query_type == "tasks":
                stmt = select(FlowTask).order_by(FlowTask.created_at.desc()).limit(50)
                if params.get("story_id"):
                    stmt = stmt.where(FlowTask.story_id == params["story_id"])
                if params.get("state"):
                    stmt = stmt.where(FlowTask.state == params["state"])
                if params.get("assignee_id"):
                    stmt = stmt.where(FlowTask.assignee_id == params["assignee_id"])
                result = await session.execute(stmt)
                rows = result.scalars().all()
                data = [{"id": r.id, "title": r.title, "state": r.state, "task_type": r.task_type,
                          "assignee_id": r.assignee_id, "estimate_hours": r.estimate_hours} for r in rows]
                return json.dumps({"ok": True, "count": len(data), "tasks": data}, ensure_ascii=False)

            elif query_type == "bugs":
                stmt = select(FlowBug).order_by(FlowBug.created_at.desc()).limit(50)
                if params.get("story_id"):
                    stmt = stmt.where(FlowBug.story_id == params["story_id"])
                if params.get("state"):
                    stmt = stmt.where(FlowBug.state == params["state"])
                if params.get("assignee_id"):
                    stmt = stmt.where(FlowBug.assignee_id == params["assignee_id"])
                result = await session.execute(stmt)
                rows = result.scalars().all()
                data = [{"id": r.id, "title": r.title, "state": r.state, "severity": r.severity,
                          "assignee_id": r.assignee_id} for r in rows]
                return json.dumps({"ok": True, "count": len(data), "bugs": data}, ensure_ascii=False)

            elif query_type == "project_members":
                project_id = params.get("project_id", "")
                if not project_id:
                    return json.dumps({"ok": False, "message": "project_members 需要 project_id"})
                stmt = (
                    select(FlowProjectMember, Member)
                    .join(Member, FlowProjectMember.member_id == Member.id)
                    .where(FlowProjectMember.project_id == project_id)
                )
                result = await session.execute(stmt)
                rows = result.all()
                data = [{"member_id": pm.member_id, "name": m.name, "email": m.email,
                          "role": pm.role, "joined_at": pm.joined_at.isoformat() if pm.joined_at else None}
                         for pm, m in rows]
                return json.dumps({"ok": True, "count": len(data), "members": data}, ensure_ascii=False)

            elif query_type == "detail":
                entity_type = params.get("entity_type", "")
                entity_id = params.get("entity_id", "")
                if not entity_type or not entity_id:
                    return json.dumps({"ok": False, "message": "detail 模式需要 entity_type 和 entity_id"})

                model_map = {"story": FlowStory, "task": FlowTask, "bug": FlowBug, "project": FlowProject}
                model = model_map.get(entity_type)
                if not model:
                    return json.dumps({"ok": False, "message": f"不支持的实体类型: {entity_type}"})

                result = await session.execute(select(model).where(model.id == entity_id))
                entity = result.scalar_one_or_none()
                if not entity:
                    return json.dumps({"ok": False, "message": f"{entity_type} 不存在: {entity_id}"})

                # 序列化所有非内部字段
                data = {}
                for col in model.__table__.columns:
                    val = getattr(entity, col.name)
                    if hasattr(val, "isoformat"):
                        val = val.isoformat()
                    data[col.name] = val
                return json.dumps({"ok": True, entity_type: data}, ensure_ascii=False)

            else:
                return json.dumps({"ok": False, "message": f"不支持的查询类型: {query_type}"})
