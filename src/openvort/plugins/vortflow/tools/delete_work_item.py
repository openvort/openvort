"""
删除工具 -- vortflow_delete_work_item

删除需求、任务、缺陷，需要用户文字确认。
"""

import json

from sqlalchemy import delete as sa_delete, select

from openvort.plugin.base import BaseTool
from openvort.utils.logging import get_logger

log = get_logger("plugins.vortflow.tools.delete_work_item")


class DeleteWorkItemTool(BaseTool):
    name = "vortflow_delete_work_item"
    description = (
        "删除 VortFlow 中的需求/任务/缺陷。"
        "这是危险操作，删除需求会级联删除其下所有子需求、任务和缺陷。"
        "调用此工具前必须先让用户回复「确认删除」四个字，然后将用户的确认文本传入 confirm_text 参数。"
        "如果 confirm_text 不是「确认删除」，操作将被拒绝。"
    )
    required_permission = "vortflow.admin"

    def __init__(self, get_session_factory):
        self._get_sf = get_session_factory

    def input_schema(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "entity_type": {
                    "type": "string",
                    "description": "实体类型",
                    "enum": ["story", "task", "bug"],
                },
                "entity_id": {
                    "type": "string",
                    "description": "需求/任务/缺陷 ID",
                },
                "confirm_text": {
                    "type": "string",
                    "description": "用户确认文本，必须为「确认删除」才能执行",
                },
            },
            "required": ["entity_type", "entity_id", "confirm_text"],
        }

    async def execute(self, params: dict) -> str:
        from openvort.plugins.vortflow.models import FlowBug, FlowEvent, FlowStory, FlowTask

        entity_type = params["entity_type"]
        entity_id = params["entity_id"]
        confirm_text = params.get("confirm_text", "")

        if confirm_text != "确认删除":
            return json.dumps({
                "ok": False,
                "message": "删除操作需要用户确认。请让用户回复「确认删除」后再调用此工具。",
            }, ensure_ascii=False)

        model_map = {"story": FlowStory, "task": FlowTask, "bug": FlowBug}
        if entity_type not in model_map:
            return json.dumps({"ok": False, "message": f"不支持的实体类型: {entity_type}"})

        model = model_map[entity_type]
        type_labels = {"story": "需求", "task": "任务", "bug": "缺陷"}
        label = type_labels[entity_type]

        sf = self._get_sf()
        async with sf() as session:
            result = await session.execute(select(model).where(model.id == entity_id))
            entity = result.scalar_one_or_none()
            if not entity:
                return json.dumps({"ok": False, "message": f"{label}不存在: {entity_id}"})

            title = entity.title
            deleted_children = 0
            member_id = params.get("_member_id", "")

            if entity_type == "story":
                descendant_ids = await self._collect_descendants(session, FlowStory, [entity_id])
                target_story_ids = [entity_id, *descendant_ids]
                await session.execute(sa_delete(FlowTask).where(FlowTask.story_id.in_(target_story_ids)))
                await session.execute(sa_delete(FlowBug).where(FlowBug.story_id.in_(target_story_ids)))
                if descendant_ids:
                    await session.execute(sa_delete(FlowStory).where(FlowStory.id.in_(descendant_ids)))
                deleted_children = len(descendant_ids)
                await session.delete(entity)

            elif entity_type == "task":
                child_ids = (
                    await session.execute(select(FlowTask.id).where(FlowTask.parent_id == entity_id))
                ).scalars().all()
                if child_ids:
                    await session.execute(sa_delete(FlowTask).where(FlowTask.parent_id == entity_id))
                deleted_children = len(child_ids)
                await session.delete(entity)

            elif entity_type == "bug":
                await session.delete(entity)

            event = FlowEvent(
                entity_type=entity_type,
                entity_id=entity_id,
                action="deleted",
                actor_id=member_id or None,
                detail=json.dumps({"title": title, "deleted_children": deleted_children}, ensure_ascii=False),
            )
            session.add(event)
            await session.commit()

        suffix = f"（含 {deleted_children} 个子项）" if deleted_children > 0 else ""
        return json.dumps({
            "ok": True,
            "message": f"{label}「{title}」已删除{suffix}",
        }, ensure_ascii=False)

    @staticmethod
    async def _collect_descendants(session, model, parent_ids: list[str]) -> list[str]:
        pending = [pid for pid in parent_ids if pid]
        descendants: list[str] = []
        seen: set[str] = set(pending)
        while pending:
            child_rows = (
                await session.execute(select(model.id).where(model.parent_id.in_(pending)))
            ).scalars().all()
            next_ids = [cid for cid in child_rows if cid not in seen]
            if not next_ids:
                break
            descendants.extend(next_ids)
            seen.update(next_ids)
            pending = next_ids
        return descendants
