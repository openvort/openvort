"""
Jenkins build tools.
"""

from __future__ import annotations

from openvort.plugins.jenkins.tools.base import JenkinsToolBase


class TriggerBuildTool(JenkinsToolBase):
    name = "jenkins_trigger_build"
    description = (
        "触发 Jenkins 构建。"
        "支持无参构建和参数化构建，适用于发布、测试、部署流水线。"
    )
    required_permission = "jenkins.write"

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
                "parameters": {
                    "type": "object",
                    "description": "参数化构建参数（可选），例如 {\"branch\":\"main\",\"env\":\"prod\"}",
                    "default": {},
                },
            },
            "required": ["job_name"],
        }

    async def execute(self, params: dict) -> str:
        async def _handle(client):
            job_name = str(params.get("job_name", "") or "").strip()
            if not job_name:
                return {"ok": False, "message": "缺少 job_name"}
            raw_params = params.get("parameters") or {}
            if raw_params is None:
                raw_params = {}
            if not isinstance(raw_params, dict):
                return {"ok": False, "message": "parameters 必须是对象（key-value）"}

            payload = {str(k): "" if v is None else str(v) for k, v in raw_params.items()}
            result = await client.trigger_build(job_name, payload)
            return {
                "ok": True,
                "message": "构建已触发",
                "job_name": job_name,
                "parameters": payload,
                **result,
            }

        instance_id = str(params.get("instance_id", "") or "").strip()
        return await self._run(_handle, instance_id=instance_id)


class BuildStatusTool(JenkinsToolBase):
    name = "jenkins_build_status"
    description = (
        "查看 Jenkins 指定构建的状态。"
        "返回运行中/完成状态、结果、耗时、触发原因等信息。"
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
                    "description": "Job 名称",
                },
                "build_number": {
                    "type": "integer",
                    "description": "构建号，例如 128",
                },
            },
            "required": ["job_name", "build_number"],
        }

    async def execute(self, params: dict) -> str:
        async def _handle(client):
            job_name = str(params.get("job_name", "") or "").strip()
            if not job_name:
                return {"ok": False, "message": "缺少 job_name"}
            try:
                build_number = int(params.get("build_number", 0))
            except Exception:
                return {"ok": False, "message": "build_number 必须是整数"}
            if build_number <= 0:
                return {"ok": False, "message": "build_number 必须大于 0"}

            status = await client.get_build_status(job_name, build_number)
            return {"ok": True, "job_name": job_name, "build": status}

        instance_id = str(params.get("instance_id", "") or "").strip()
        return await self._run(_handle, instance_id=instance_id)


class BuildLogTool(JenkinsToolBase):
    name = "jenkins_build_log"
    description = (
        "获取 Jenkins 构建控制台日志。"
        "支持按尾部行数截取，便于快速定位失败原因。"
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
                    "description": "Job 名称",
                },
                "build_number": {
                    "type": "integer",
                    "description": "构建号",
                },
                "tail_lines": {
                    "type": "integer",
                    "description": "返回日志尾部行数，默认 200，最大 2000",
                    "default": 200,
                },
            },
            "required": ["job_name", "build_number"],
        }

    async def execute(self, params: dict) -> str:
        async def _handle(client):
            job_name = str(params.get("job_name", "") or "").strip()
            if not job_name:
                return {"ok": False, "message": "缺少 job_name"}
            try:
                build_number = int(params.get("build_number", 0))
            except Exception:
                return {"ok": False, "message": "build_number 必须是整数"}
            if build_number <= 0:
                return {"ok": False, "message": "build_number 必须大于 0"}

            try:
                tail_lines = int(params.get("tail_lines", 200) or 200)
            except Exception:
                tail_lines = 200
            tail_lines = max(1, min(tail_lines, 2000))

            data = await client.get_build_log(job_name, build_number, tail_lines=tail_lines)
            return {"ok": True, "job_name": job_name, "build_number": build_number, **data}

        instance_id = str(params.get("instance_id", "") or "").strip()
        return await self._run(_handle, instance_id=instance_id)
