"""
Jenkins system tools.
"""

from __future__ import annotations

from openvort.plugins.jenkins.config import JenkinsSettings
from openvort.plugins.jenkins.tools.base import JenkinsToolBase


class SystemInfoTool(JenkinsToolBase):
    name = "jenkins_system_info"
    description = (
        "查看 Jenkins 系统信息。"
        "包括运行模式、执行器数量、视图列表以及可选的队列摘要。"
    )
    required_permission = "jenkins.read"

    def __init__(self, settings: JenkinsSettings):
        super().__init__(settings)

    def input_schema(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "include_queue": {
                    "type": "boolean",
                    "description": "是否附带队列信息",
                    "default": True,
                },
                "include_jobs_summary": {
                    "type": "boolean",
                    "description": "是否附带 Job 统计摘要（总量与状态计数）",
                    "default": True,
                },
                "jobs_limit": {
                    "type": "integer",
                    "description": "统计时读取的 Job 最大数量，默认 200，最大 500",
                    "default": 200,
                },
            },
            "required": [],
        }

    async def execute(self, params: dict) -> str:
        async def _handle(client):
            include_queue = bool(params.get("include_queue", True))
            include_jobs_summary = bool(params.get("include_jobs_summary", True))
            try:
                jobs_limit = int(params.get("jobs_limit", 200) or 200)
            except Exception:
                jobs_limit = 200
            jobs_limit = max(1, min(jobs_limit, 500))

            system_info = await client.get_system_info()
            result = {"ok": True, "system": system_info}

            if include_queue:
                queue = await client.get_queue_info()
                result["queue"] = queue
                result["queue_count"] = len(queue.get("items", [])) if isinstance(queue, dict) else 0

            if include_jobs_summary:
                jobs = await client.list_jobs(limit=jobs_limit)
                color_counter: dict[str, int] = {}
                for job in jobs:
                    color = str(job.get("color", "") or "unknown")
                    color_counter[color] = color_counter.get(color, 0) + 1
                result["jobs_summary"] = {
                    "total": len(jobs),
                    "by_color": color_counter,
                }

            return result

        return await self._run(_handle)
