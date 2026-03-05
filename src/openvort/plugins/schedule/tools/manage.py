"""
Schedule manage tool — schedule_manage

Create, update, delete, toggle, and run scheduled tasks.
"""

import json

from openvort.plugin.base import BaseTool
from openvort.utils.logging import get_logger

log = get_logger("plugins.schedule.tools.manage")


class ScheduleManageTool(BaseTool):
    name = "schedule_manage"
    description = (
        "管理定时任务：创建、更新、删除、启用/禁用、立即执行。"
        "定时任务到期后会自动让 AI 执行指定的 prompt 内容。"
        "支持 cron 表达式（分 时 日 月 周）、固定间隔（秒）、一次性定时（ISO 时间）三种调度方式。"
    )

    def __init__(self, get_session_factory):
        self._get_sf = get_session_factory

    def input_schema(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "action": {
                    "type": "string",
                    "description": "操作类型",
                    "enum": ["create", "update", "delete", "toggle", "run"],
                },
                "job_id": {
                    "type": "string",
                    "description": "任务 ID（update/delete/toggle/run 时必填）",
                },
                "name": {
                    "type": "string",
                    "description": "任务名称（create 时必填）",
                },
                "description": {
                    "type": "string",
                    "description": "任务描述",
                },
                "schedule_type": {
                    "type": "string",
                    "description": "调度类型：cron（定时）、interval（间隔）、once（一次性）",
                    "enum": ["cron", "interval", "once"],
                },
                "schedule": {
                    "type": "string",
                    "description": "调度规则。cron: '分 时 日 月 周'（如 '0 9 * * 1-5'）；interval: 秒数表示重复间隔（如 '3600' 每小时）；once: 秒数表示延迟（如 '10' 10秒后）或 ISO 时间（如 '2025-06-01T09:00:00'）。注意：'X秒后做某事'用 once，'每X秒做一次'用 interval",
                },
                "prompt": {
                    "type": "string",
                    "description": "AI 执行的 prompt 内容（create/update 时使用，定时触发后 AI 会执行这段 prompt）",
                },
                "timezone": {
                    "type": "string",
                    "description": "时区，默认 Asia/Shanghai",
                    "default": "Asia/Shanghai",
                },
                "enabled": {
                    "type": "boolean",
                    "description": "是否启用",
                    "default": True,
                },
            },
            "required": ["action"],
        }

    async def execute(self, params: dict) -> str:
        from openvort.core.schedule_service import ScheduleService
        from openvort.core.scheduler import Scheduler

        action = params["action"]
        # _member_id 是当前发起请求的成员 ID
        # _target_member_id 是当前对话的 AI 员工成员 ID（如果是与 AI 员工聊天）
        # _caller_member_id 是实际发起请求的真实成员 ID
        member_id = params.get("_caller_member_id") or params.get("_member_id", "")
        target_member_id = params.get("_target_member_id", "")  # AI 员工 ID
        if not member_id:
            return json.dumps({"ok": False, "message": "无法识别当前用户"}, ensure_ascii=False)

        service = self._get_schedule_service()

        if action == "create":
            return await self._create(service, params, member_id)
        elif action == "update":
            return await self._update(service, params, member_id)
        elif action == "delete":
            return await self._delete(service, params, member_id)
        elif action == "toggle":
            return await self._toggle(service, params, member_id)
        elif action == "run":
            return await self._run(service, params, member_id)
        else:
            return json.dumps({"ok": False, "message": f"不支持的操作: {action}"}, ensure_ascii=False)

    async def _create(self, service, params: dict, member_id: str) -> str:
        name = params.get("name")
        if not name:
            return json.dumps({"ok": False, "message": "创建任务需要 name"}, ensure_ascii=False)

        schedule_type = params.get("schedule_type")
        schedule = params.get("schedule")
        if not schedule_type or not schedule:
            return json.dumps({"ok": False, "message": "创建任务需要 schedule_type 和 schedule"}, ensure_ascii=False)

        prompt = params.get("prompt", "")
        if not prompt:
            return json.dumps({"ok": False, "message": "创建任务需要 prompt（AI 执行内容）"}, ensure_ascii=False)

        action_config = {"prompt": prompt}

        # 获取执行人（AI 员工）- 如果当前在与 AI 员工聊天，使用 AI 员工作为执行人
        target_member_id = params.get("_target_member_id", "")

        try:
            job = await service.create_job(
                owner_id=member_id,  # 任务拥有者是发起请求的真实用户
                name=name,
                description=params.get("description", ""),
                schedule_type=schedule_type,
                schedule=schedule,
                timezone=params.get("timezone", "Asia/Shanghai"),
                action_config=action_config,
                enabled=params.get("enabled", True),
                target_member_id=target_member_id,  # 执行人
            )
            return json.dumps({"ok": True, "message": f"定时任务「{name}」创建成功", "job": job}, ensure_ascii=False)
        except Exception as e:
            log.error(f"创建定时任务失败: {e}")
            return json.dumps({"ok": False, "message": f"创建失败: {e}"}, ensure_ascii=False)

    async def _update(self, service, params: dict, member_id: str) -> str:
        job_id = params.get("job_id")
        if not job_id:
            return json.dumps({"ok": False, "message": "更新任务需要 job_id"}, ensure_ascii=False)

        fields = {}
        for key in ("name", "description", "schedule_type", "schedule", "timezone", "enabled"):
            if key in params and params[key] is not None:
                fields[key] = params[key]
        if "prompt" in params and params["prompt"]:
            fields["action_config"] = {"prompt": params["prompt"]}

        if not fields:
            return json.dumps({"ok": False, "message": "没有需要更新的字段"}, ensure_ascii=False)

        try:
            job = await service.update_job(job_id, owner_id=member_id, **fields)
            if not job:
                return json.dumps({"ok": False, "message": "任务不存在或无权限"}, ensure_ascii=False)
            return json.dumps({"ok": True, "message": "任务已更新", "job": job}, ensure_ascii=False)
        except Exception as e:
            log.error(f"更新定时任务失败: {e}")
            return json.dumps({"ok": False, "message": f"更新失败: {e}"}, ensure_ascii=False)

    async def _delete(self, service, params: dict, member_id: str) -> str:
        job_id = params.get("job_id")
        if not job_id:
            return json.dumps({"ok": False, "message": "删除任务需要 job_id"}, ensure_ascii=False)

        try:
            ok = await service.delete_job(job_id, owner_id=member_id)
            if not ok:
                return json.dumps({"ok": False, "message": "任务不存在或无权限"}, ensure_ascii=False)
            return json.dumps({"ok": True, "message": "任务已删除"}, ensure_ascii=False)
        except Exception as e:
            log.error(f"删除定时任务失败: {e}")
            return json.dumps({"ok": False, "message": f"删除失败: {e}"}, ensure_ascii=False)

    async def _toggle(self, service, params: dict, member_id: str) -> str:
        job_id = params.get("job_id")
        if not job_id:
            return json.dumps({"ok": False, "message": "启停任务需要 job_id"}, ensure_ascii=False)

        try:
            job = await service.toggle_job(job_id, owner_id=member_id)
            if not job:
                return json.dumps({"ok": False, "message": "任务不存在或无权限"}, ensure_ascii=False)
            status = "启用" if job["enabled"] else "禁用"
            return json.dumps({"ok": True, "message": f"任务已{status}", "job": job}, ensure_ascii=False)
        except Exception as e:
            log.error(f"切换定时任务状态失败: {e}")
            return json.dumps({"ok": False, "message": f"操作失败: {e}"}, ensure_ascii=False)

    async def _run(self, service, params: dict, member_id: str) -> str:
        job_id = params.get("job_id")
        if not job_id:
            return json.dumps({"ok": False, "message": "立即执行需要 job_id"}, ensure_ascii=False)

        # Verify ownership before running
        job = await service.get_job(job_id)
        if not job or job["owner_id"] != member_id:
            return json.dumps({"ok": False, "message": "任务不存在或无权限"}, ensure_ascii=False)

        try:
            result = await service.run_now(job_id)
            return json.dumps({"ok": result["success"], "message": "任务已执行", "result": result}, ensure_ascii=False)
        except Exception as e:
            log.error(f"立即执行定时任务失败: {e}")
            return json.dumps({"ok": False, "message": f"执行失败: {e}"}, ensure_ascii=False)

    def _get_schedule_service(self):
        """Get or create the ScheduleService singleton."""
        from openvort.web.routers.schedules import _get_service
        return _get_service()
