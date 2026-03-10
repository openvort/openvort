"""
需求录入工具 — vortflow_intake_story
"""

import json

from sqlalchemy import select

from openvort.plugin.base import BaseTool
from openvort.utils.logging import get_logger

log = get_logger("plugins.vortflow.tools.intake")


class IntakeStoryTool(BaseTool):
    name = "vortflow_intake_story"
    description = (
        "录入一个新需求到 VortFlow 敏捷流程系统。"
        "需要提供需求标题、描述、所属项目，可选优先级和截止时间。"
        "录入后需求进入 intake 状态，等待评审。"
    )
    required_permission = "vortflow.story"

    def __init__(self, get_session_factory, notifier, engine):
        self._get_sf = get_session_factory
        self._notifier = notifier
        self._engine = engine

    def input_schema(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "title": {"type": "string", "description": "需求标题"},
                "description": {"type": "string", "description": "需求详细描述", "default": ""},
                "project_id": {"type": "string", "description": "所属项目 ID（可通过 vortflow_query 查询）"},
                "parent_id": {"type": "string", "description": "父需求 ID（创建子需求时使用）", "default": ""},
                "priority": {
                    "type": "integer",
                    "description": "优先级: 1=紧急 2=高 3=中 4=低",
                    "default": 3,
                    "enum": [1, 2, 3, 4],
                },
                "deadline": {"type": "string", "description": "截止时间 (YYYY-MM-DD)，可选", "default": ""},
                "submitter_name": {"type": "string", "description": "提需求的人的名字（用于记录）", "default": ""},
                "image_urls": {"type": "array", "items": {"type": "string"},
                               "description": "截图 URL 列表（用户发送的图片地址，从 _image_urls 获取）"},
                "children": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "title": {"type": "string"},
                            "description": {"type": "string", "default": ""},
                        },
                        "required": ["title"],
                    },
                    "description": "子需求列表。当一个需求包含多个独立功能点时，拆分为子需求",
                    "default": [],
                },
            },
            "required": ["title", "project_id"],
        }

    async def execute(self, params: dict) -> str:
        from datetime import datetime
        import uuid

        from openvort.plugins.vortflow.models import FlowEvent, FlowProject, FlowStory

        title = params["title"]
        project_id = params["project_id"]
        parent_id = (params.get("parent_id", "") or "").strip() or None
        description = params.get("description", "")
        priority = params.get("priority", 3)
        deadline_str = params.get("deadline", "")
        children = params.get("children", []) or []

        image_urls = params.get("image_urls", []) or []
        injected_urls = params.get("_image_urls", []) or []
        for url in injected_urls:
            if url and url not in image_urls:
                image_urls.append(url)
        if image_urls:
            img_md = "\n".join(f"![截图]({url})" for url in image_urls)
            description = f"{description}\n\n{img_md}" if description else img_md

        # Extract caller identity injected by AgentRuntime
        member_id = params.get("_member_id", "")

        deadline = None
        if deadline_str:
            try:
                deadline = datetime.strptime(deadline_str, "%Y-%m-%d")
            except ValueError:
                return json.dumps({"ok": False, "message": f"截止时间格式错误，应为 YYYY-MM-DD: {deadline_str}"})

        sf = self._get_sf()
        async with sf() as session:
            result = await session.execute(select(FlowProject).where(FlowProject.id == project_id))
            project = result.scalar_one_or_none()
            if not project:
                return json.dumps({"ok": False, "message": f"项目不存在: {project_id}"})

            if parent_id:
                parent_story = await session.get(FlowStory, parent_id)
                if not parent_story:
                    return json.dumps({"ok": False, "message": f"父需求不存在: {parent_id}"}, ensure_ascii=False)
                if parent_story.project_id != project_id:
                    return json.dumps({"ok": False, "message": "父需求必须与当前项目一致"}, ensure_ascii=False)

            # 创建需求（自动记录提交人）
            story_id = uuid.uuid4().hex

            story = FlowStory(
                id=story_id,
                project_id=project_id,
                title=title,
                description=description,
                state="intake",
                priority=priority,
                parent_id=parent_id,
                deadline=deadline,
                submitter_id=member_id or None,
            )
            session.add(story)

            # 记录事件（含操作人）
            event = FlowEvent(
                entity_type="story",
                entity_id=story_id,
                action="created",
                actor_id=member_id or None,
                detail=json.dumps({"title": title, "project": project.name}, ensure_ascii=False),
            )
            session.add(event)

            child_story_ids: list[str] = []
            child_story_titles: list[str] = []
            for child in children:
                child_title = str(child.get("title", "")).strip()
                if not child_title:
                    continue
                child_id = uuid.uuid4().hex
                child_story = FlowStory(
                    id=child_id,
                    project_id=project_id,
                    parent_id=story_id,
                    title=child_title,
                    description=str(child.get("description", "") or ""),
                    state="intake",
                    priority=priority,
                    submitter_id=member_id or None,
                )
                session.add(child_story)
                session.add(
                    FlowEvent(
                        entity_type="story",
                        entity_id=child_id,
                        action="created",
                        actor_id=member_id or None,
                        detail=json.dumps(
                            {"title": child_title, "project": project.name, "parent_id": story_id},
                            ensure_ascii=False,
                        ),
                    )
                )
                child_story_ids.append(child_id)
                child_story_titles.append(child_title)
            await session.commit()

        return json.dumps({
            "ok": True,
            "message": f"需求「{title}」已录入，当前状态: intake（待评审）",
            "story_id": story_id,
            "parent_id": parent_id,
            "children": [{"id": child_id, "title": child_title} for child_id, child_title in zip(child_story_ids, child_story_titles)],
            "project": project.name,
        }, ensure_ascii=False)
