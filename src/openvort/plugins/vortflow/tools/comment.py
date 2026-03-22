"""
评论工具 -- vortflow_comment

为需求、任务、缺陷添加评论。
"""

import json

from sqlalchemy import select

from openvort.plugin.base import BaseTool
from openvort.utils.logging import get_logger

log = get_logger("plugins.vortflow.tools.comment")


class CommentTool(BaseTool):
    name = "vortflow_comment"
    description = (
        "为 VortFlow 中的需求/任务/缺陷添加评论。"
        "支持 @mention 成员（传入成员姓名列表）。"
    )
    required_permission = "vortflow.story"

    def __init__(self, get_session_factory):
        self._get_sf = get_session_factory

    def input_schema(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "entity_type": {
                    "type": "string",
                    "enum": ["story", "task", "bug"],
                    "description": "实体类型",
                },
                "entity_id": {"type": "string", "description": "需求/任务/缺陷 ID"},
                "content": {"type": "string", "description": "评论内容"},
                "mention_names": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "@提及的成员姓名列表",
                    "default": [],
                },
            },
            "required": ["entity_type", "entity_id", "content"],
        }

    async def execute(self, params: dict) -> str:
        from openvort.contacts.models import Member
        from openvort.plugins.vortflow.models import FlowBug, FlowComment, FlowEvent, FlowStory, FlowTask

        entity_type = params["entity_type"]
        entity_id = params["entity_id"]
        content = params["content"]
        mention_names = params.get("mention_names", [])
        member_id = params.get("_member_id", "")

        model_map = {"story": FlowStory, "task": FlowTask, "bug": FlowBug}
        type_labels = {"story": "需求", "task": "任务", "bug": "缺陷"}

        if entity_type not in model_map:
            return json.dumps({"ok": False, "message": f"不支持的实体类型: {entity_type}"})

        sf = self._get_sf()
        async with sf() as session:
            entity = await session.get(model_map[entity_type], entity_id)
            if not entity:
                return json.dumps({"ok": False, "message": f"{type_labels[entity_type]}不存在: {entity_id}"})

            mention_ids = []
            if mention_names:
                for name in mention_names:
                    result = await session.execute(select(Member).where(Member.name == name))
                    m = result.scalar_one_or_none()
                    if m:
                        mention_ids.append(m.id)

            comment = FlowComment(
                entity_type=entity_type,
                entity_id=entity_id,
                author_id=member_id,
                content=content,
                mentions_json=json.dumps(mention_ids, ensure_ascii=False),
            )
            session.add(comment)

            event = FlowEvent(
                entity_type=entity_type,
                entity_id=entity_id,
                action="comment_added",
                actor_id=member_id or None,
                detail=json.dumps({"preview": content[:100]}, ensure_ascii=False),
            )
            session.add(event)
            await session.commit()

            title = entity.title

        return json.dumps({
            "ok": True,
            "message": f"已为{type_labels[entity_type]}「{title}」添加评论",
        }, ensure_ascii=False)
