"""
进度更新/状态推进工具 — vortflow_update_progress

推进需求、任务、缺陷的状态，遵循状态机合法转换规则。
"""

import json

from sqlalchemy import select

from openvort.plugin.base import BaseTool
from openvort.utils.logging import get_logger

log = get_logger("plugins.vortflow.tools.progress")


class UpdateProgressTool(BaseTool):
    name = "vortflow_update_progress"
    description = (
        "推进 VortFlow 中需求/任务/缺陷的状态。"
        "需求状态流: submitted → intake → review → pm_refine → design → design_done → breakdown → dev_assign → in_progress → testing → done。"
        "submitted 可直接到 rejected。review 可驳回到 rejected，rejected 可回到 submitted。testing 可进入 bugfix 循环。"
        "任务状态: todo → in_progress → done → closed。"
        "缺陷状态: open → confirmed → fixing → resolved → verified → closed。"
    )
    required_permission = "vortflow.story"

    def __init__(self, get_session_factory, engine, notifier):
        self._get_sf = get_session_factory
        self._engine = engine
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
                "target_state": {"type": "string", "description": "目标状态"},
                "comment": {"type": "string", "description": "备注说明", "default": ""},
            },
            "required": ["entity_type", "entity_id", "target_state"],
        }

    async def execute(self, params: dict) -> str:
        from openvort.plugins.vortflow.engine import BugState, StoryState, TaskState
        from openvort.plugins.vortflow.models import FlowBug, FlowEvent, FlowStory, FlowTask

        entity_type = params["entity_type"]
        entity_id = params["entity_id"]
        target_state_str = params["target_state"]
        comment = params.get("comment", "")

        model_map = {"story": FlowStory, "task": FlowTask, "bug": FlowBug}
        state_enum_map = {"story": StoryState, "task": TaskState, "bug": BugState}

        if entity_type not in model_map:
            return json.dumps({"ok": False, "message": f"不支持的实体类型: {entity_type}"})

        model = model_map[entity_type]
        state_enum = state_enum_map[entity_type]

        try:
            target_state = state_enum(target_state_str)
        except ValueError:
            valid = [s.value for s in state_enum]
            return json.dumps({"ok": False, "message": f"无效状态: {target_state_str}，可选: {valid}"})

        sf = self._get_sf()
        async with sf() as session:
            result = await session.execute(select(model).where(model.id == entity_id))
            entity = result.scalar_one_or_none()
            if not entity:
                return json.dumps({"ok": False, "message": f"{entity_type} 不存在: {entity_id}"})

            current_state = state_enum(entity.state)
            old_state = current_state.value

            # 通过状态机校验
            transition_fn = {
                "story": self._engine.transition_story,
                "task": self._engine.transition_task,
                "bug": self._engine.transition_bug,
            }[entity_type]

            ok = await transition_fn(entity_id, current_state, target_state, {"comment": comment})
            if not ok:
                from openvort.plugins.vortflow.engine import BUG_TRANSITIONS, STORY_TRANSITIONS, TASK_TRANSITIONS
                transitions_map = {"story": STORY_TRANSITIONS, "task": TASK_TRANSITIONS, "bug": BUG_TRANSITIONS}
                allowed = [s.value for s in transitions_map[entity_type].get(current_state, [])]
                return json.dumps({
                    "ok": False,
                    "message": f"不允许从 {old_state} 转换到 {target_state_str}，当前可转换到: {allowed}",
                })

            # Extract caller identity injected by AgentRuntime
            member_id = params.get("_member_id", "")

            # 更新状态
            entity.state = target_state.value

            # 记录事件（含操作人）
            event = FlowEvent(
                entity_type=entity_type,
                entity_id=entity_id,
                action="state_changed",
                actor_id=member_id or None,
                detail=json.dumps({
                    "from": old_state, "to": target_state.value, "comment": comment,
                }, ensure_ascii=False),
            )
            session.add(event)
            await session.commit()

            title = entity.title
            assignee_id = getattr(entity, "assignee_id", None) or getattr(entity, "pm_id", None)

        # 通知
        if self._notifier and assignee_id:
            await self._notifier.notify_state_change(
                entity_type, entity_id, title, old_state, target_state.value, assignee_id
            )

        return json.dumps({
            "ok": True,
            "message": f"{entity_type} 「{title}」状态已从 {old_state} 推进到 {target_state.value}",
        }, ensure_ascii=False)
