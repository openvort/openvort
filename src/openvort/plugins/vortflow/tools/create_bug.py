"""
创建缺陷工具 -- vortflow_create_bug
"""

import json

from sqlalchemy import select

from openvort.plugin.base import BaseTool
from openvort.utils.logging import get_logger

log = get_logger("plugins.vortflow.tools.create_bug")


class CreateBugTool(BaseTool):
    name = "vortflow_create_bug"
    description = (
        "在 VortFlow 中提交新缺陷(Bug)。"
        "可关联到需求或任务，指定严重程度和负责人。"
        "创建后缺陷进入 open 状态。"
    )
    required_permission = "vortflow.bug"

    def __init__(self, get_session_factory):
        self._get_sf = get_session_factory

    def input_schema(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "title": {"type": "string", "description": "缺陷标题"},
                "description": {"type": "string", "description": "缺陷描述（重现步骤、期望结果等）", "default": ""},
                "project_id": {
                    "type": "string",
                    "description": "所属项目 ID（如提供 story_id/task_id 可自动继承）",
                    "default": "",
                },
                "story_id": {
                    "type": "string",
                    "description": "关联需求 ID（可选）",
                    "default": "",
                },
                "task_id": {
                    "type": "string",
                    "description": "关联任务 ID（可选）",
                    "default": "",
                },
                "severity": {
                    "type": "integer",
                    "description": "严重程度: 1=致命 2=严重 3=一般 4=轻微",
                    "default": 3,
                    "enum": [1, 2, 3, 4],
                },
                "assignee_name": {
                    "type": "string",
                    "description": "负责修复人的姓名",
                    "default": "",
                },
            },
            "required": ["title"],
        }

    async def execute(self, params: dict) -> str:
        from openvort.contacts.models import Member
        from openvort.plugins.vortflow.models import FlowBug, FlowEvent, FlowStory, FlowTask

        title = params["title"]
        description = params.get("description", "")
        project_id = params.get("project_id", "") or None
        story_id = params.get("story_id", "") or None
        task_id = params.get("task_id", "") or None
        severity = params.get("severity", 3)
        assignee_name = params.get("assignee_name", "")
        member_id = params.get("_member_id", "")

        sf = self._get_sf()
        async with sf() as session:
            if story_id:
                story = await session.get(FlowStory, story_id)
                if story and not project_id:
                    project_id = story.project_id
            if task_id and not project_id:
                task = await session.get(FlowTask, task_id)
                if task and task.project_id:
                    project_id = task.project_id

            assignee_id = None
            if assignee_name:
                result = await session.execute(
                    select(Member).where(Member.name == assignee_name)
                )
                m = result.scalar_one_or_none()
                if m:
                    assignee_id = m.id

            b = FlowBug(
                project_id=project_id,
                story_id=story_id,
                task_id=task_id,
                title=title,
                description=description,
                severity=severity,
                assignee_id=assignee_id,
                reporter_id=member_id or None,
            )
            session.add(b)
            await session.flush()

            event = FlowEvent(
                entity_type="bug",
                entity_id=b.id,
                action="created",
                actor_id=member_id or None,
                detail=json.dumps({"title": title}, ensure_ascii=False),
            )
            session.add(event)
            await session.commit()
            await session.refresh(b)
            bug_id = b.id

        severity_labels = {1: "致命", 2: "严重", 3: "一般", 4: "轻微"}
        return json.dumps({
            "ok": True,
            "message": f"缺陷「{title}」已提交，严重程度: {severity_labels.get(severity, '未知')}",
            "bug_id": bug_id,
            "project_id": project_id,
        }, ensure_ascii=False)
