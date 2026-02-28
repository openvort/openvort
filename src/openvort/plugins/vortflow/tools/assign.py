"""
角色分配工具 — vortflow_assign

分配产品经理、设计师、开发人员、测试人员等角色到需求或任务。
"""

import json

from sqlalchemy import select

from openvort.plugin.base import BaseTool
from openvort.utils.logging import get_logger

log = get_logger("plugins.vortflow.tools.assign")


class AssignTool(BaseTool):
    name = "vortflow_assign"
    description = (
        "为 VortFlow 中的需求或任务分配负责人。"
        "可分配的角色包括：产品经理(pm)、设计师(designer)、评审人(reviewer)、开发(assignee)。"
        "分配后会通知被分配人。"
    )
    required_permission = "vortflow.assign"

    def __init__(self, get_session_factory, notifier):
        self._get_sf = get_session_factory
        self._notifier = notifier

    def input_schema(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "entity_type": {
                    "type": "string",
                    "description": "实体类型",
                    "enum": ["story", "task", "bug"],
                },
                "entity_id": {"type": "string", "description": "需求/任务/缺陷 ID"},
                "role": {
                    "type": "string",
                    "description": "分配的角色: pm(产品经理), designer(设计师), reviewer(评审人), assignee(负责人/开发), developer(开发人员), reporter(报告人)",
                    "enum": ["pm", "designer", "reviewer", "assignee", "developer", "reporter"],
                },
                "member_id": {"type": "string", "description": "被分配成员的 ID"},
            },
            "required": ["entity_type", "entity_id", "role", "member_id"],
        }

    async def execute(self, params: dict) -> str:
        from openvort.plugins.vortflow.models import FlowBug, FlowEvent, FlowStory, FlowTask

        entity_type = params["entity_type"]
        entity_id = params["entity_id"]
        role = params["role"]
        member_id = params["member_id"]

        role_field_map = {
            "story": {"pm": "pm_id", "designer": "designer_id", "reviewer": "reviewer_id", "assignee": "submitter_id"},
            "task": {"assignee": "assignee_id"},
            "bug": {"assignee": "assignee_id", "developer": "developer_id", "reporter": "reporter_id"},
        }

        model_map = {"story": FlowStory, "task": FlowTask, "bug": FlowBug}

        if entity_type not in model_map:
            return json.dumps({"ok": False, "message": f"不支持的实体类型: {entity_type}"})

        fields = role_field_map.get(entity_type, {})
        field_name = fields.get(role)
        if not field_name:
            return json.dumps({"ok": False, "message": f"{entity_type} 不支持分配角色: {role}"})

        model = model_map[entity_type]
        sf = self._get_sf()

        async with sf() as session:
            result = await session.execute(select(model).where(model.id == entity_id))
            entity = result.scalar_one_or_none()
            if not entity:
                return json.dumps({"ok": False, "message": f"{entity_type} 不存在: {entity_id}"})

            setattr(entity, field_name, member_id)

            # Extract caller identity injected by AgentRuntime
            actor_id = params.get("_member_id", "")

            # 记录事件（含操作人）
            event = FlowEvent(
                entity_type=entity_type,
                entity_id=entity_id,
                action="assigned",
                actor_id=actor_id or None,
                detail=json.dumps({"role": role, "member_id": member_id}, ensure_ascii=False),
            )
            session.add(event)
            await session.commit()

            title = entity.title

        # 发送通知
        role_names = {
            "pm": "产品经理", "designer": "设计师", "reviewer": "评审人",
            "assignee": "负责人", "developer": "开发人员", "reporter": "报告人",
        }
        if self._notifier:
            await self._notifier.notify_assignment(entity_type, entity_id, title, member_id, role_names.get(role, role))

        return json.dumps({
            "ok": True,
            "message": f"已将 {entity_type} 「{title}」的{role_names.get(role, role)}分配给 {member_id}",
        }, ensure_ascii=False)
