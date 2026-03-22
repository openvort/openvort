"""
通用字段更新工具 -- vortflow_update_work_item

修改需求、任务、缺陷的基本字段（标题、描述、优先级、截止时间等）。
"""

import json
from datetime import datetime

from sqlalchemy import select

from openvort.plugin.base import BaseTool
from openvort.utils.logging import get_logger

log = get_logger("plugins.vortflow.tools.update_work_item")


class UpdateWorkItemTool(BaseTool):
    name = "vortflow_update_work_item"
    description = (
        "修改 VortFlow 中需求/任务/缺陷的基本字段。"
        "可修改标题、描述、优先级/严重程度、截止时间等。"
        "状态变更请使用 vortflow_update_progress，角色分配请使用 vortflow_assign。"
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
                    "description": "实体类型",
                    "enum": ["story", "task", "bug"],
                },
                "entity_id": {
                    "type": "string",
                    "description": "需求/任务/缺陷 ID",
                },
                "title": {
                    "type": "string",
                    "description": "新标题（不传则不修改）",
                },
                "description": {
                    "type": "string",
                    "description": "新描述（不传则不修改）",
                },
                "priority": {
                    "type": "integer",
                    "description": "新优先级(story/task): 1=紧急 2=高 3=中 4=低；新严重程度(bug): 1=致命 2=严重 3=一般 4=轻微",
                    "enum": [1, 2, 3, 4],
                },
                "deadline": {
                    "type": "string",
                    "description": "截止时间 (YYYY-MM-DD)，传空字符串清除",
                },
            },
            "required": ["entity_type", "entity_id"],
        }

    async def execute(self, params: dict) -> str:
        from openvort.plugins.vortflow.models import FlowBug, FlowEvent, FlowStory, FlowTask

        entity_type = params["entity_type"]
        entity_id = params["entity_id"]

        model_map = {"story": FlowStory, "task": FlowTask, "bug": FlowBug}
        if entity_type not in model_map:
            return json.dumps({"ok": False, "message": f"不支持的实体类型: {entity_type}"})

        model = model_map[entity_type]
        type_labels = {"story": "需求", "task": "任务", "bug": "缺陷"}
        label = type_labels[entity_type]

        has_update = any(k in params for k in ("title", "description", "priority", "deadline"))
        if not has_update:
            return json.dumps({"ok": False, "message": "未提供任何要修改的字段"})

        sf = self._get_sf()
        async with sf() as session:
            result = await session.execute(select(model).where(model.id == entity_id))
            entity = result.scalar_one_or_none()
            if not entity:
                return json.dumps({"ok": False, "message": f"{label}不存在: {entity_id}"})

            changes = {}

            if "title" in params and params["title"]:
                old_title = entity.title
                entity.title = params["title"]
                changes["title"] = {"from": old_title, "to": params["title"]}

            if "description" in params:
                old_desc = entity.description
                entity.description = params["description"]
                changes["description"] = {"from": old_desc[:50], "to": params["description"][:50]}

            if "priority" in params:
                prio_field = "severity" if entity_type == "bug" else "priority"
                old_val = getattr(entity, prio_field)
                setattr(entity, prio_field, params["priority"])
                changes[prio_field] = {"from": old_val, "to": params["priority"]}

            if "deadline" in params:
                old_deadline = str(entity.deadline) if entity.deadline else ""
                if params["deadline"] == "":
                    entity.deadline = None
                else:
                    try:
                        entity.deadline = datetime.strptime(params["deadline"], "%Y-%m-%d")
                    except ValueError:
                        return json.dumps({"ok": False, "message": f"日期格式错误: {params['deadline']}，请用 YYYY-MM-DD"})
                changes["deadline"] = {"from": old_deadline, "to": params["deadline"]}

            if not changes:
                return json.dumps({"ok": False, "message": "字段值与当前相同，无需修改"})

            member_id = params.get("_member_id", "")
            event = FlowEvent(
                entity_type=entity_type,
                entity_id=entity_id,
                action="updated",
                actor_id=member_id or None,
                detail=json.dumps(changes, ensure_ascii=False),
            )
            session.add(event)
            await session.commit()

            changed_fields = "、".join(changes.keys())

        return json.dumps({
            "ok": True,
            "message": f"{label}「{entity.title}」已更新，修改字段: {changed_fields}",
        }, ensure_ascii=False)
