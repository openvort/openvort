"""
项目管理工具 -- vortflow_manage_project

修改和删除项目（创建项目使用 vortflow_create_project）。
"""

import json

from sqlalchemy import delete as sa_delete, select

from openvort.plugin.base import BaseTool
from openvort.utils.logging import get_logger

log = get_logger("plugins.vortflow.tools.manage_project")


class ManageProjectTool(BaseTool):
    name = "vortflow_manage_project"
    description = (
        "管理 VortFlow 项目：修改项目信息或删除项目。"
        "action=update 可修改名称、描述、起止时间等。"
        "action=delete 删除项目（会清除项目成员关系，需用户确认「确认删除」）。"
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
                    "enum": ["update", "delete"],
                    "description": "操作类型",
                },
                "project_id": {"type": "string", "description": "项目 ID"},
                "name": {"type": "string", "description": "新名称（update 时）"},
                "description": {"type": "string", "description": "新描述（update 时）"},
                "start_date": {"type": "string", "description": "开始日期 YYYY-MM-DD（update 时）"},
                "end_date": {"type": "string", "description": "结束日期 YYYY-MM-DD（update 时）"},
                "confirm_text": {"type": "string", "description": "删除确认，必须为「确认删除」"},
            },
            "required": ["action", "project_id"],
        }

    async def execute(self, params: dict) -> str:
        from datetime import datetime

        from openvort.plugins.vortflow.models import FlowEvent, FlowProject, FlowProjectMember

        action = params["action"]
        project_id = params["project_id"]
        member_id = params.get("_member_id", "")

        sf = self._get_sf()

        if action == "update":
            async with sf() as session:
                p = await session.get(FlowProject, project_id)
                if not p:
                    return json.dumps({"ok": False, "message": "项目不存在"})

                changes = {}
                for field in ("name", "description"):
                    if field in params and params[field] is not None:
                        old = getattr(p, field)
                        setattr(p, field, params[field])
                        changes[field] = {"from": str(old)[:50], "to": str(params[field])[:50]}

                for date_field in ("start_date", "end_date"):
                    if date_field in params and params[date_field]:
                        try:
                            dt = datetime.strptime(params[date_field], "%Y-%m-%d")
                        except ValueError:
                            return json.dumps({"ok": False, "message": f"日期格式错误: {params[date_field]}"})
                        setattr(p, date_field, dt)
                        changes[date_field] = params[date_field]

                if not changes:
                    return json.dumps({"ok": False, "message": "未提供任何要修改的字段"})

                event = FlowEvent(
                    entity_type="project", entity_id=project_id, action="updated",
                    actor_id=member_id or None,
                    detail=json.dumps(changes, ensure_ascii=False),
                )
                session.add(event)
                await session.commit()

                return json.dumps({
                    "ok": True,
                    "message": f"项目「{p.name}」已更新，修改字段: {'、'.join(changes.keys())}",
                }, ensure_ascii=False)

        elif action == "delete":
            confirm = params.get("confirm_text", "")
            if confirm != "确认删除":
                return json.dumps({
                    "ok": False,
                    "message": "删除项目需要用户确认。请让用户回复「确认删除」后再调用。",
                }, ensure_ascii=False)

            async with sf() as session:
                p = await session.get(FlowProject, project_id)
                if not p:
                    return json.dumps({"ok": False, "message": "项目不存在"})
                name = p.name
                await session.execute(
                    sa_delete(FlowProjectMember).where(FlowProjectMember.project_id == project_id)
                )
                await session.delete(p)
                event = FlowEvent(
                    entity_type="project", entity_id=project_id, action="deleted",
                    actor_id=member_id or None,
                    detail=json.dumps({"name": name}, ensure_ascii=False),
                )
                session.add(event)
                await session.commit()

            return json.dumps({"ok": True, "message": f"项目「{name}」已删除"}, ensure_ascii=False)

        return json.dumps({"ok": False, "message": f"未知操作: {action}"})
