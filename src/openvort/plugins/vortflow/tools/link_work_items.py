"""
关联工作项工具 -- vortflow_link_work_items

建立需求/任务/缺陷之间的关联关系。
"""

import json

from sqlalchemy import or_, select

from openvort.plugin.base import BaseTool
from openvort.utils.logging import get_logger

log = get_logger("plugins.vortflow.tools.link_work_items")


class LinkWorkItemsTool(BaseTool):
    name = "vortflow_link_work_items"
    description = (
        "在 VortFlow 中建立工作项之间的关联关系。"
        "例如：需求关联任务、任务关联缺陷、需求关联缺陷等。"
        "关联是双向的，不会重复创建。"
    )
    required_permission = "vortflow.story"

    def __init__(self, get_session_factory):
        self._get_sf = get_session_factory

    def input_schema(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "source_type": {
                    "type": "string",
                    "enum": ["story", "task", "bug"],
                    "description": "源工作项类型",
                },
                "source_id": {"type": "string", "description": "源工作项 ID"},
                "target_type": {
                    "type": "string",
                    "enum": ["story", "task", "bug"],
                    "description": "目标工作项类型",
                },
                "target_id": {"type": "string", "description": "目标工作项 ID"},
            },
            "required": ["source_type", "source_id", "target_type", "target_id"],
        }

    async def execute(self, params: dict) -> str:
        from openvort.plugins.vortflow.models import (
            FlowBug,
            FlowEvent,
            FlowStory,
            FlowTask,
            FlowWorkItemLink,
        )

        source_type = params["source_type"]
        source_id = params["source_id"]
        target_type = params["target_type"]
        target_id = params["target_id"]
        member_id = params.get("_member_id", "")

        model_map = {"story": FlowStory, "task": FlowTask, "bug": FlowBug}
        type_labels = {"story": "需求", "task": "任务", "bug": "缺陷"}

        if source_type == target_type and source_id == target_id:
            return json.dumps({"ok": False, "message": "不能关联自身"})

        sf = self._get_sf()
        async with sf() as session:
            src = await session.get(model_map[source_type], source_id)
            if not src:
                return json.dumps({"ok": False, "message": f"源{type_labels[source_type]}不存在: {source_id}"})
            tgt = await session.get(model_map[target_type], target_id)
            if not tgt:
                return json.dumps({"ok": False, "message": f"目标{type_labels[target_type]}不存在: {target_id}"})

            existing = await session.execute(
                select(FlowWorkItemLink).where(
                    or_(
                        (FlowWorkItemLink.source_type == source_type)
                        & (FlowWorkItemLink.source_id == source_id)
                        & (FlowWorkItemLink.target_type == target_type)
                        & (FlowWorkItemLink.target_id == target_id),
                        (FlowWorkItemLink.source_type == target_type)
                        & (FlowWorkItemLink.source_id == target_id)
                        & (FlowWorkItemLink.target_type == source_type)
                        & (FlowWorkItemLink.target_id == source_id),
                    )
                )
            )
            if existing.scalar_one_or_none():
                return json.dumps({"ok": False, "message": "关联已存在"})

            link = FlowWorkItemLink(
                source_type=source_type,
                source_id=source_id,
                target_type=target_type,
                target_id=target_id,
                created_by=member_id or None,
            )
            session.add(link)

            event = FlowEvent(
                entity_type=source_type,
                entity_id=source_id,
                action="link_added",
                actor_id=member_id or None,
                detail=json.dumps({"target_type": target_type, "target_id": target_id}, ensure_ascii=False),
            )
            session.add(event)
            await session.commit()

            src_title = src.title
            tgt_title = tgt.title

        return json.dumps({
            "ok": True,
            "message": f"已关联 {type_labels[source_type]}「{src_title}」与 {type_labels[target_type]}「{tgt_title}」",
        }, ensure_ascii=False)
