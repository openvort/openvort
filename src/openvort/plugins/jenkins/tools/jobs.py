"""
Jenkins job tools.
"""

from __future__ import annotations

from openvort.plugins.jenkins.tools.base import JenkinsToolBase


def _parse_bool(value, default: bool) -> bool:
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        v = value.strip().lower()
        if v in {"1", "true", "yes", "y", "on"}:
            return True
        if v in {"0", "false", "no", "n", "off"}:
            return False
    return bool(value)


class ListJobsTool(JenkinsToolBase):
    name = "jenkins_list_jobs"
    description = (
        "列出 Jenkins Job。"
        "支持按 view（视图）或 folder（目录）查询，并可递归列出文件夹内子 Job。"
    )
    required_permission = "jenkins.read"

    def input_schema(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "instance_id": {
                    "type": "string",
                    "description": "Jenkins 实例 ID（可选，不传则使用默认实例）",
                    "default": "",
                },
                "view": {
                    "type": "string",
                    "description": "Jenkins 视图名称（可选），例如 backend-ci",
                    "default": "",
                },
                "folder": {
                    "type": "string",
                    "description": "Jenkins 文件夹路径（可选），例如 vortmall-测试环境（与 view 二选一）",
                    "default": "",
                },
                "keyword": {
                    "type": "string",
                    "description": "按 Job 名称关键词过滤（可选）",
                    "default": "",
                },
                "recursive": {
                    "type": "boolean",
                    "description": "是否递归列出文件夹下的子 Job，默认 true",
                    "default": True,
                },
                "include_folders": {
                    "type": "boolean",
                    "description": "结果中是否包含文件夹节点，默认 false（仅返回可执行 Job）",
                    "default": False,
                },
                "limit": {
                    "type": "integer",
                    "description": "返回数量上限，默认 50，最大 200",
                    "default": 50,
                },
            },
            "required": [],
        }

    async def execute(self, params: dict) -> str:
        async def _handle(client):
            view = str(params.get("view", "") or "").strip()
            folder = str(params.get("folder", "") or "").strip()
            keyword = str(params.get("keyword", "") or "").strip()
            recursive = _parse_bool(params.get("recursive"), True)
            include_folders = _parse_bool(params.get("include_folders"), False)
            limit = int(params.get("limit", 50) or 50)
            limit = max(1, min(limit, 200))
            if view and folder:
                return {"ok": False, "message": "view 和 folder 不能同时传入"}

            jobs = await client.list_jobs(
                view=view,
                folder=folder,
                keyword=keyword,
                recursive=recursive,
                include_folders=include_folders,
                limit=limit,
            )
            return {
                "ok": True,
                "count": len(jobs),
                "query": {
                    "view": view,
                    "folder": folder,
                    "keyword": keyword,
                    "recursive": recursive,
                    "include_folders": include_folders,
                    "limit": limit,
                },
                "jobs": jobs,
            }

        instance_id = str(params.get("instance_id", "") or "").strip()
        return await self._run(_handle, instance_id=instance_id)


class JobInfoTool(JenkinsToolBase):
    name = "jenkins_job_info"
    description = (
        "查看 Jenkins Job 的详细信息。"
        "返回 Job 基本属性、最近构建状态，以及参数化构建参数定义。"
    )
    required_permission = "jenkins.read"

    def input_schema(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "instance_id": {
                    "type": "string",
                    "description": "Jenkins 实例 ID（可选，不传则使用默认实例）",
                    "default": "",
                },
                "job_name": {
                    "type": "string",
                    "description": "Job 名称（支持多级目录，如 folder/project-ci）",
                },
                "include_queue": {
                    "type": "boolean",
                    "description": "是否包含当前队列中与该 Job 相关的任务",
                    "default": True,
                },
            },
            "required": ["job_name"],
        }

    async def execute(self, params: dict) -> str:
        async def _handle(client):
            job_name = str(params.get("job_name", "") or "").strip()
            if not job_name:
                return {"ok": False, "message": "缺少 job_name"}

            info = await client.get_job_info(job_name)
            properties = info.get("property") if isinstance(info, dict) else []
            parameter_defs = []
            if isinstance(properties, list):
                for item in properties:
                    defs = item.get("parameterDefinitions") if isinstance(item, dict) else None
                    if isinstance(defs, list):
                        for d in defs:
                            parameter_defs.append(
                                {
                                    "name": d.get("name", ""),
                                    "type": d.get("type", ""),
                                    "description": d.get("description", ""),
                                    "default": ((d.get("defaultParameterValue") or {}).get("value", "")),
                                }
                            )

            result = {
                "ok": True,
                "job": {
                    "name": info.get("name", ""),
                    "full_name": info.get("fullName", ""),
                    "display_name": info.get("displayName", ""),
                    "description": info.get("description", ""),
                    "url": info.get("url", ""),
                    "buildable": info.get("buildable", True),
                    "in_queue": info.get("inQueue", False),
                    "next_build_number": info.get("nextBuildNumber"),
                    "color": info.get("color", ""),
                    "last_build": info.get("lastBuild") or None,
                    "last_completed_build": info.get("lastCompletedBuild") or None,
                    "parameters": parameter_defs,
                },
            }

            if bool(params.get("include_queue", True)):
                queue = await client.get_queue_info()
                queue_items = queue.get("items", []) if isinstance(queue, dict) else []
                related = []
                for item in queue_items:
                    task = item.get("task", {}) if isinstance(item, dict) else {}
                    task_name = (task.get("name", "") or "").strip()
                    if task_name == info.get("name", "") or task_name == info.get("fullName", ""):
                        related.append(item)
                result["queue_items"] = related

            return result

        instance_id = str(params.get("instance_id", "") or "").strip()
        return await self._run(_handle, instance_id=instance_id)
