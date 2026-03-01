"""
Schedule query tool — schedule_query

List and inspect scheduled tasks.
"""

import json

from openvort.plugin.base import BaseTool
from openvort.utils.logging import get_logger

log = get_logger("plugins.schedule.tools.query")


class ScheduleQueryTool(BaseTool):
    name = "schedule_query"
    description = (
        "查询定时任务列表或详情。"
        "可列出当前用户的个人任务，也可查看某个任务的详细信息（含最近执行结果）。"
    )

    def input_schema(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "query_type": {
                    "type": "string",
                    "description": "查询类型：list 列出任务列表，detail 查看单个任务详情",
                    "enum": ["list", "detail"],
                },
                "job_id": {
                    "type": "string",
                    "description": "任务 ID（detail 模式必填）",
                },
                "scope": {
                    "type": "string",
                    "description": "范围过滤：personal 个人任务，team 团队任务，不填返回全部",
                    "enum": ["personal", "team"],
                },
            },
            "required": ["query_type"],
        }

    async def execute(self, params: dict) -> str:
        query_type = params["query_type"]
        member_id = params.get("_member_id", "")
        if not member_id:
            return json.dumps({"ok": False, "message": "无法识别当前用户"}, ensure_ascii=False)

        from openvort.web.routers.schedules import _get_service
        service = _get_service()

        if query_type == "list":
            return await self._list(service, params, member_id)
        elif query_type == "detail":
            return await self._detail(service, params, member_id)
        else:
            return json.dumps({"ok": False, "message": f"不支持的查询类型: {query_type}"}, ensure_ascii=False)

    async def _list(self, service, params: dict, member_id: str) -> str:
        scope = params.get("scope")
        try:
            jobs = await service.list_jobs(owner_id=member_id, scope=scope)
            # Also include visible team tasks
            if not scope or scope == "personal":
                team_jobs = await service.list_jobs(scope="team")
                visible_team = [j for j in team_jobs if j["visible"] and j["owner_id"] != member_id]
                if visible_team:
                    jobs = jobs + visible_team

            summary = []
            for j in jobs:
                summary.append({
                    "job_id": j["job_id"],
                    "name": j["name"],
                    "description": j["description"],
                    "schedule_type": j["schedule_type"],
                    "schedule": j["schedule"],
                    "enabled": j["enabled"],
                    "scope": j["scope"],
                    "last_status": j["last_status"],
                    "last_run_at": j["last_run_at"],
                })
            return json.dumps({"ok": True, "count": len(summary), "jobs": summary}, ensure_ascii=False)
        except Exception as e:
            log.error(f"查询定时任务列表失败: {e}")
            return json.dumps({"ok": False, "message": f"查询失败: {e}"}, ensure_ascii=False)

    async def _detail(self, service, params: dict, member_id: str) -> str:
        job_id = params.get("job_id")
        if not job_id:
            return json.dumps({"ok": False, "message": "detail 模式需要 job_id"}, ensure_ascii=False)

        try:
            job = await service.get_job(job_id)
            if not job:
                return json.dumps({"ok": False, "message": "任务不存在"}, ensure_ascii=False)
            # Personal tasks: only owner can see; team tasks: visible ones are public
            if job["owner_id"] != member_id and not (job["scope"] == "team" and job["visible"]):
                return json.dumps({"ok": False, "message": "无权限查看该任务"}, ensure_ascii=False)
            return json.dumps({"ok": True, "job": job}, ensure_ascii=False)
        except Exception as e:
            log.error(f"查询定时任务详情失败: {e}")
            return json.dumps({"ok": False, "message": f"查询失败: {e}"}, ensure_ascii=False)
