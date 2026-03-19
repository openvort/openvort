"""
Jenkins build tools.
"""

from __future__ import annotations

import json

from openvort.plugins.jenkins.confirm import get_confirm_manager
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
        # 获取调用者 ID
        caller_id = params.get("_caller_id", "")
        job_name = str(params.get("job_name", "") or "").strip()
        
        # 先检查必要参数是否提供
        if not job_name:
            return json.dumps({
                "ok": False,
                "error": "missing_params",
                "message": "触发构建需要提供 job_name（Job 名称），请提供后再操作。",
                "missing_params": ["job_name"],
            }, ensure_ascii=False)
        
        # 检查是否有待确认操作需要处理
        if caller_id:
            confirm_mgr = get_confirm_manager()
            pending = confirm_mgr.get_pending(caller_id)
            
            if pending and pending.tool == self.name:
                # 用户之前发起过触发构建，检查是否确认
                user_input = params.get("_user_input", "")
                is_confirmed, _ = confirm_mgr.check_confirm(caller_id, user_input)
                
                if is_confirmed:
                    # 用户确认了，执行实际操作
                    return await self._do_trigger_build(pending.params)
                
                # 用户没确认，返回待确认提示
                return json.dumps({
                    "ok": False,
                    "error": "pending_confirm",
                    "message": f"请回复「确认」以执行触发构建操作（其他内容无效）。",
                    "pending_action": "trigger_build",
                    "job_name": pending.params.get("job_name", ""),
                }, ensure_ascii=False)
        
        # 没有 caller_id 或没有待确认操作，正常流程
        return await self._confirm_and_execute(caller_id, job_name, params)

    async def _confirm_and_execute(self, caller_id: str, job_name: str, params: dict) -> str:
        """处理需要确认的触发构建操作"""
        # 如果没有 caller_id（无会话上下文），直接执行
        if not caller_id:
            return await self._do_trigger_build(params)
        
        # 检查是否已获取过参数定义
        # 如果 parameters 未传入，先返回提示让用户确认参数
        provided_params = params.get("parameters")
        if provided_params is None:
            # 返回特殊错误，让 AI 先获取 Job 参数定义
            return json.dumps({
                "ok": False,
                "error": "need_job_info",
                "message": f"在触发构建「{job_name}」之前，需要先获取该 Job 的参数定义。请调用 jenkins_job_info 获取参数后再次尝试。",
                "pending_action": "trigger_build",
                "job_name": job_name,
            }, ensure_ascii=False)
        
        # 设置待确认状态
        confirm_mgr = get_confirm_manager()
        confirm_mgr.set_pending(
            caller_id=caller_id,
            action="trigger_build",
            tool=self.name,
            params=params,
            instance_name=job_name,
        )
        
        return json.dumps({
            "ok": False,
            "error": "pending_confirm",
            "message": f"即将触发 Jenkins 构建「{job_name}」，请回复「确认」以执行（其他内容无效）。",
            "pending_action": "trigger_build",
            "job_name": job_name,
            "parameters": provided_params,
        }, ensure_ascii=False)

    async def _do_trigger_build(self, params: dict) -> str:
        """实际执行触发构建"""
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
