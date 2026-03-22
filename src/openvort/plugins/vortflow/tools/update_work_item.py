"""
通用字段更新工具 -- vortflow_update_work_item

修改需求、任务、缺陷的基本字段（标题、描述、优先级、截止时间、计划时间、预估工时、迭代、版本等）。
"""

import json
from datetime import datetime

from sqlalchemy import select, delete as sa_delete

from openvort.plugin.base import BaseTool
from openvort.utils.logging import get_logger

log = get_logger("plugins.vortflow.tools.update_work_item")


class UpdateWorkItemTool(BaseTool):
    name = "vortflow_update_work_item"
    description = (
        "修改 VortFlow 中需求/任务/缺陷的字段。"
        "支持修改：标题、描述、优先级、截止时间、计划开始/结束时间、预估工时(任务/缺陷)、关联迭代、关联版本(需求)。"
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
                "start_at": {
                    "type": "string",
                    "description": "计划开始时间 (YYYY-MM-DD)，传空字符串清除",
                },
                "end_at": {
                    "type": "string",
                    "description": "计划结束时间 (YYYY-MM-DD)，传空字符串清除",
                },
                "estimate_hours": {
                    "type": "number",
                    "description": "预估工时（小时），仅任务和缺陷支持。传 0 清除",
                },
                "iteration_id": {
                    "type": "string",
                    "description": "关联迭代 ID，将工作项加入该迭代。传空字符串取消关联",
                },
                "version_id": {
                    "type": "string",
                    "description": "关联版本 ID（仅需求支持），将需求加入该版本。传空字符串取消关联",
                },
            },
            "required": ["entity_type", "entity_id"],
        }

    async def execute(self, params: dict) -> str:
        from openvort.plugins.vortflow.models import (
            FlowBug, FlowEvent, FlowStory, FlowTask,
            FlowIteration, FlowIterationStory, FlowIterationTask, FlowIterationBug,
            FlowVersion, FlowVersionStory, FlowVersionBug,
        )

        entity_type = params["entity_type"]
        entity_id = params["entity_id"]

        model_map = {"story": FlowStory, "task": FlowTask, "bug": FlowBug}
        if entity_type not in model_map:
            return json.dumps({"ok": False, "message": f"不支持的实体类型: {entity_type}"})

        model = model_map[entity_type]
        type_labels = {"story": "需求", "task": "任务", "bug": "缺陷"}
        label = type_labels[entity_type]

        updatable = (
            "title", "description", "priority", "deadline",
            "start_at", "end_at", "estimate_hours",
            "iteration_id", "version_id",
        )
        has_update = any(k in params for k in updatable)
        if not has_update:
            return json.dumps({"ok": False, "message": "未提供任何要修改的字段"})

        def _parse_date(s):
            if not s:
                return None
            try:
                return datetime.strptime(s, "%Y-%m-%d")
            except ValueError:
                return None

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

            for date_field in ("deadline", "start_at", "end_at"):
                if date_field in params:
                    old_val = str(getattr(entity, date_field)) if getattr(entity, date_field) else ""
                    if params[date_field] == "":
                        setattr(entity, date_field, None)
                    else:
                        dt = _parse_date(params[date_field])
                        if dt is None:
                            return json.dumps({"ok": False, "message": f"日期格式错误: {params[date_field]}，请用 YYYY-MM-DD"})
                        setattr(entity, date_field, dt)
                    changes[date_field] = {"from": old_val, "to": params[date_field]}

            if "estimate_hours" in params:
                if entity_type == "story":
                    return json.dumps({"ok": False, "message": "需求不支持预估工时，请在拆分的任务上设置"})
                old_val = getattr(entity, "estimate_hours", None)
                new_val = float(params["estimate_hours"]) if params["estimate_hours"] else None
                if new_val == 0:
                    new_val = None
                entity.estimate_hours = new_val
                changes["estimate_hours"] = {"from": old_val, "to": new_val}

            # Iteration linking
            if "iteration_id" in params:
                iteration_link_model = {
                    "story": FlowIterationStory,
                    "task": FlowIterationTask,
                    "bug": FlowIterationBug,
                }[entity_type]
                fk_field = {"story": "story_id", "task": "task_id", "bug": "bug_id"}[entity_type]
                fk_col = getattr(iteration_link_model, fk_field)

                await session.execute(
                    sa_delete(iteration_link_model).where(fk_col == entity_id)
                )

                new_iter_id = (params["iteration_id"] or "").strip()
                if new_iter_id:
                    it = await session.get(FlowIteration, new_iter_id)
                    if not it:
                        return json.dumps({"ok": False, "message": f"迭代不存在: {new_iter_id}"})
                    link = iteration_link_model(**{"iteration_id": new_iter_id, fk_field: entity_id})
                    session.add(link)
                    changes["iteration"] = {"to": it.name}
                else:
                    changes["iteration"] = {"to": ""}

            # Version linking (story and bug only)
            if "version_id" in params:
                if entity_type == "task":
                    return json.dumps({"ok": False, "message": "任务不支持直接关联版本，请在所属需求上设置"})
                version_link_model = {"story": FlowVersionStory, "bug": FlowVersionBug}[entity_type]
                fk_field = {"story": "story_id", "bug": "bug_id"}[entity_type]
                fk_col = getattr(version_link_model, fk_field)

                await session.execute(
                    sa_delete(version_link_model).where(fk_col == entity_id)
                )

                new_ver_id = (params["version_id"] or "").strip()
                if new_ver_id:
                    ver = await session.get(FlowVersion, new_ver_id)
                    if not ver:
                        return json.dumps({"ok": False, "message": f"版本不存在: {new_ver_id}"})
                    link = version_link_model(**{"version_id": new_ver_id, fk_field: entity_id})
                    session.add(link)
                    changes["version"] = {"to": ver.name}
                else:
                    changes["version"] = {"to": ""}

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
