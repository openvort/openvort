"""
版本管理工具 -- vortflow_manage_version

创建、修改、删除版本。
"""

import json

from sqlalchemy import delete as sa_delete, select

from openvort.plugin.base import BaseTool
from openvort.utils.logging import get_logger

log = get_logger("plugins.vortflow.tools.manage_version")


class ManageVersionTool(BaseTool):
    name = "vortflow_manage_version"
    description = (
        "管理 VortFlow 版本。"
        "action=create 创建版本，需提供项目 ID 和版本号。"
        "action=update 修改版本信息（名称、描述、状态、计划发布日期等）。"
        "action=delete 删除版本（会清除版本-需求关联，需用户确认「确认删除」）。"
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
                "version_id": {"type": "string", "description": "版本 ID（update/delete 时必填）"},
                "project_id": {"type": "string", "description": "项目 ID（create 时必填）"},
                "name": {"type": "string", "description": "版本号（如 v1.0.0）"},
                "description": {"type": "string", "description": "版本描述", "default": ""},
                "status": {
                    "type": "string",
                    "enum": ["planning", "released", "archived"],
                    "description": "版本状态",
                },
                "planned_release_date": {"type": "string", "description": "计划发布日期 YYYY-MM-DD"},
                "progress": {"type": "integer", "description": "版本进度 0-100"},
                "confirm_text": {"type": "string", "description": "删除确认文本"},
            },
            "required": ["action"],
        }

    async def execute(self, params: dict) -> str:
        from datetime import datetime

        from openvort.plugins.vortflow.models import FlowEvent, FlowVersion, FlowVersionBug, FlowVersionStory

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
                return json.dumps({"ok": False, "message": "创建版本需要提供 project_id 和 name"})

            planned = _parse_dt(params.get("planned_release_date", ""))
            progress = max(0, min(100, int(params.get("progress", 0) or 0)))

            async with sf() as session:
                v = FlowVersion(
                    project_id=project_id,
                    name=name,
                    description=params.get("description", ""),
                    planned_release_at=planned,
                    release_date=planned,
                    progress=progress,
                    status=params.get("status", "planning"),
                )
                session.add(v)
                await session.flush()
                event = FlowEvent(
                    entity_type="version", entity_id=v.id, action="created",
                    actor_id=member_id or None,
                    detail=json.dumps({"name": name}, ensure_ascii=False),
                )
                session.add(event)
                await session.commit()
                version_id = v.id

            return json.dumps({
                "ok": True,
                "message": f"版本「{name}」已创建",
                "version_id": version_id,
            }, ensure_ascii=False)

        elif action == "update":
            version_id = params.get("version_id", "")
            if not version_id:
                return json.dumps({"ok": False, "message": "update 需要提供 version_id"})

            async with sf() as session:
                v = await session.get(FlowVersion, version_id)
                if not v:
                    return json.dumps({"ok": False, "message": "版本不存在"})

                changes = {}
                for field in ("name", "description", "status"):
                    if field in params and params[field] is not None:
                        setattr(v, field, params[field])
                        changes[field] = params[field]
                if "progress" in params and params["progress"] is not None:
                    val = max(0, min(100, int(params["progress"])))
                    v.progress = val
                    changes["progress"] = val
                if "planned_release_date" in params and params["planned_release_date"]:
                    dt = _parse_dt(params["planned_release_date"])
                    v.planned_release_at = dt
                    v.release_date = dt
                    changes["planned_release_date"] = params["planned_release_date"]

                if not changes:
                    return json.dumps({"ok": False, "message": "未提供任何要修改的字段"})

                event = FlowEvent(
                    entity_type="version", entity_id=version_id, action="updated",
                    actor_id=member_id or None,
                    detail=json.dumps(changes, ensure_ascii=False),
                )
                session.add(event)
                await session.commit()

            return json.dumps({
                "ok": True,
                "message": f"版本「{v.name}」已更新，修改字段: {'、'.join(changes.keys())}",
            }, ensure_ascii=False)

        elif action == "delete":
            version_id = params.get("version_id", "")
            confirm = params.get("confirm_text", "")
            if not version_id:
                return json.dumps({"ok": False, "message": "delete 需要提供 version_id"})
            if confirm != "确认删除":
                return json.dumps({
                    "ok": False,
                    "message": "删除版本需要用户确认。请让用户回复「确认删除」后再调用。",
                }, ensure_ascii=False)

            async with sf() as session:
                v = await session.get(FlowVersion, version_id)
                if not v:
                    return json.dumps({"ok": False, "message": "版本不存在"})
                name = v.name
                await session.execute(sa_delete(FlowVersionStory).where(FlowVersionStory.version_id == version_id))
                await session.execute(sa_delete(FlowVersionBug).where(FlowVersionBug.version_id == version_id))
                await session.delete(v)
                event = FlowEvent(
                    entity_type="version", entity_id=version_id, action="deleted",
                    actor_id=member_id or None,
                    detail=json.dumps({"name": name}, ensure_ascii=False),
                )
                session.add(event)
                await session.commit()

            return json.dumps({"ok": True, "message": f"版本「{name}」已删除"}, ensure_ascii=False)

        return json.dumps({"ok": False, "message": f"未知操作: {action}"})
