"""
项目管理工具 — vortflow_create_project

通过 AI 对话创建 VortFlow 项目，自动将创建者加入项目成员（owner 角色）。
"""

import json

from openvort.plugin.base import BaseTool
from openvort.utils.logging import get_logger

log = get_logger("plugins.vortflow.tools.project")


class CreateProjectTool(BaseTool):
    name = "vortflow_create_project"
    description = (
        "在 VortFlow 中创建一个新项目。"
        "需要提供项目名称，可选描述、产品线、迭代、版本、起止时间。"
        "创建后当前用户自动成为项目 owner。"
    )
    required_permission = "vortflow.admin"

    def __init__(self, get_session_factory):
        self._get_sf = get_session_factory

    def input_schema(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "name": {"type": "string", "description": "项目名称"},
                "description": {"type": "string", "description": "项目描述", "default": ""},
                "product": {"type": "string", "description": "产品线名称", "default": ""},
                "iteration": {"type": "string", "description": "迭代名称（如 Sprint 1）", "default": ""},
                "version": {"type": "string", "description": "版本号（如 v1.0）", "default": ""},
                "start_date": {"type": "string", "description": "开始时间 (YYYY-MM-DD)，可选", "default": ""},
                "end_date": {"type": "string", "description": "结束时间 (YYYY-MM-DD)，可选", "default": ""},
            },
            "required": ["name"],
        }

    async def execute(self, params: dict) -> str:
        from datetime import datetime

        from openvort.plugins.vortflow.models import FlowEvent, FlowProject, FlowProjectMember

        name = params["name"]
        member_id = params.get("_member_id", "")

        # Parse dates
        start_date = self._parse_date(params.get("start_date", ""))
        end_date = self._parse_date(params.get("end_date", ""))
        if start_date is False or end_date is False:
            return json.dumps({"ok": False, "message": "日期格式错误，应为 YYYY-MM-DD"})

        sf = self._get_sf()
        async with sf() as session:
            # Pre-generate ID so it's available for related records
            import uuid
            project_id = uuid.uuid4().hex

            project = FlowProject(
                id=project_id,
                name=name,
                description=params.get("description", ""),
                product=params.get("product", ""),
                iteration=params.get("iteration", ""),
                version=params.get("version", ""),
                owner_id=member_id or None,
                start_date=start_date,
                end_date=end_date,
            )
            session.add(project)

            # Auto-add creator as project owner
            if member_id:
                pm = FlowProjectMember(
                    project_id=project_id,
                    member_id=member_id,
                    role="owner",
                )
                session.add(pm)

            # Audit event
            event = FlowEvent(
                entity_type="project",
                entity_id=project_id,
                action="created",
                actor_id=member_id or None,
                detail=json.dumps({"name": name}, ensure_ascii=False),
            )
            session.add(event)
            await session.commit()

        return json.dumps({
            "ok": True,
            "message": f"项目「{name}」已创建",
            "project_id": project_id,
        }, ensure_ascii=False)

    @staticmethod
    def _parse_date(date_str: str):
        """Parse YYYY-MM-DD string, return datetime or None or False on error."""
        if not date_str:
            return None
        try:
            from datetime import datetime
            return datetime.strptime(date_str, "%Y-%m-%d")
        except ValueError:
            return False
