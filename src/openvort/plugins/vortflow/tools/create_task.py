"""
创建任务工具 -- vortflow_create_task
"""

import json

from sqlalchemy import select

from openvort.plugin.base import BaseTool
from openvort.plugins.vortflow.notifier import schedule_notification
from openvort.utils.logging import get_logger

log = get_logger("plugins.vortflow.tools.create_task")


class CreateTaskTool(BaseTool):
    name = "vortflow_create_task"
    description = (
        "在 VortFlow 中创建新任务。"
        "任务可挂在需求下（story_id），也可独立存在。"
        "支持指定项目、负责人、任务类型、预估工时、截止时间等。"
        "创建后任务进入 todo 状态。"
    )
    required_permission = "vortflow.task"

    def __init__(self, get_session_factory, notifier=None):
        self._get_sf = get_session_factory
        self._notifier = notifier

    def input_schema(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "title": {"type": "string", "description": "任务标题"},
                "description": {"type": "string", "description": "任务描述", "default": ""},
                "project_id": {
                    "type": "string",
                    "description": "所属项目 ID（如提供 story_id 可自动继承）",
                    "default": "",
                },
                "story_id": {
                    "type": "string",
                    "description": "所属需求 ID（可选）",
                    "default": "",
                },
                "task_type": {
                    "type": "string",
                    "description": "任务类型",
                    "enum": ["frontend", "backend", "fullstack", "test"],
                    "default": "fullstack",
                },
                "assignee_name": {
                    "type": "string",
                    "description": "负责人姓名（用于匹配成员）",
                    "default": "",
                },
                "estimate_hours": {
                    "type": "number",
                    "description": "预估工时（小时）",
                },
                "deadline": {
                    "type": "string",
                    "description": "截止时间 (YYYY-MM-DD)",
                    "default": "",
                },
            },
            "required": ["title"],
        }

    async def execute(self, params: dict) -> str:
        from datetime import datetime

        from openvort.contacts.models import Member
        from openvort.plugins.vortflow.models import FlowEvent, FlowStory, FlowTask

        title = params["title"]
        description = params.get("description", "")
        project_id = params.get("project_id", "") or None
        story_id = params.get("story_id", "") or None
        task_type = params.get("task_type", "fullstack")
        assignee_name = params.get("assignee_name", "")
        estimate_hours = params.get("estimate_hours")
        deadline_str = params.get("deadline", "")
        member_id = params.get("_member_id", "")

        deadline = None
        if deadline_str:
            try:
                deadline = datetime.strptime(deadline_str, "%Y-%m-%d")
            except ValueError:
                return json.dumps({"ok": False, "message": f"日期格式错误: {deadline_str}，请用 YYYY-MM-DD"})

        sf = self._get_sf()
        async with sf() as session:
            if story_id:
                story = await session.get(FlowStory, story_id)
                if not story:
                    return json.dumps({"ok": False, "message": f"需求不存在: {story_id}"})
                if not project_id:
                    project_id = story.project_id

            assignee_id = None
            if assignee_name:
                result = await session.execute(
                    select(Member).where(Member.name == assignee_name)
                )
                m = result.scalar_one_or_none()
                if m:
                    assignee_id = m.id

            t = FlowTask(
                project_id=project_id,
                story_id=story_id,
                title=title,
                description=description,
                task_type=task_type,
                assignee_id=assignee_id,
                creator_id=member_id or None,
                estimate_hours=estimate_hours,
                deadline=deadline,
            )
            session.add(t)
            await session.flush()

            event = FlowEvent(
                entity_type="task",
                entity_id=t.id,
                action="created",
                actor_id=member_id or None,
                detail=json.dumps({"title": title, "story_id": story_id}, ensure_ascii=False),
            )
            session.add(event)
            await session.commit()
            await session.refresh(t)
            task_id = t.id

        if self._notifier:
            schedule_notification(self._notifier.notify_item_created(
                "task", task_id, title, project_id or "", member_id,
                assignee_id=assignee_id,
            ))

        parts = [f"任务「{title}」已创建"]
        if assignee_name and assignee_id:
            parts.append(f"负责人: {assignee_name}")
        if story_id:
            parts.append(f"关联需求: {story_id}")

        return json.dumps({
            "ok": True,
            "message": "，".join(parts),
            "task_id": task_id,
            "project_id": project_id,
        }, ensure_ascii=False)
