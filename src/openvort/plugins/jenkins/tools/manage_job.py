"""
Jenkins Job management tool (create / update / delete / copy / enable / disable).
"""

from __future__ import annotations

import json

from openvort.plugins.jenkins.confirm import get_confirm_manager
from openvort.plugins.jenkins.tools.base import JenkinsToolBase

CONFIRM_ACTIONS = {"create", "update_config", "delete"}


class ManageJobTool(JenkinsToolBase):
    name = "jenkins_manage_job"
    description = (
        "管理 Jenkins Job 配置。"
        "支持 get_config/create/update_config/delete/copy/enable/disable 操作。"
        "创建和更新需要提供 config_xml（Jenkins Job XML 配置）。"
    )
    required_permission = "jenkins.write"

    def input_schema(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "action": {
                    "type": "string",
                    "enum": [
                        "get_config",
                        "create",
                        "update_config",
                        "delete",
                        "copy",
                        "enable",
                        "disable",
                    ],
                    "description": "操作类型",
                },
                "instance_id": {
                    "type": "string",
                    "description": "Jenkins 实例 ID（可选，不传则使用默认实例）",
                    "default": "",
                },
                "job_name": {
                    "type": "string",
                    "description": "Job 名称（支持多级目录，如 folder/job-name）",
                    "default": "",
                },
                "folder": {
                    "type": "string",
                    "description": "目标文件夹路径（create/copy 时使用，为空则创建在根目录）",
                    "default": "",
                },
                "config_xml": {
                    "type": "string",
                    "description": "Job 的 XML 配置内容（create/update_config 必填）",
                    "default": "",
                },
                "src_job_name": {
                    "type": "string",
                    "description": "源 Job 名称（copy 操作时必填）",
                    "default": "",
                },
                "new_job_name": {
                    "type": "string",
                    "description": "新 Job 名称（copy 操作时必填）",
                    "default": "",
                },
            },
            "required": ["action"],
        }

    async def execute(self, params: dict) -> str:
        action = str(params.get("action", "") or "").strip().lower()
        caller_id = params.get("_caller_id", "")

        if caller_id and action in CONFIRM_ACTIONS:
            confirm_mgr = get_confirm_manager()
            pending = confirm_mgr.get_pending(caller_id)

            if pending and pending.tool == self.name and pending.action == action:
                user_input = params.get("_user_input", "")
                is_confirmed, _ = confirm_mgr.check_confirm(caller_id, user_input)

                if is_confirmed:
                    return await self._dispatch(action, pending.params)

                return json.dumps({
                    "ok": False,
                    "error": "pending_confirm",
                    "message": f"请回复「确认」以执行 {action} 操作（其他内容无效）。",
                    "pending_action": action,
                    "job_name": pending.params.get("job_name", ""),
                }, ensure_ascii=False)

        if action == "get_config":
            return await self._get_config(params)
        if action == "create":
            return await self._require_confirm_then_execute(caller_id, action, params, self._check_create)
        if action == "update_config":
            return await self._require_confirm_then_execute(caller_id, action, params, self._check_update)
        if action == "delete":
            return await self._require_confirm_then_execute(caller_id, action, params, self._check_delete)
        if action == "copy":
            return await self._copy(params)
        if action == "enable":
            return await self._enable(params)
        if action == "disable":
            return await self._disable(params)

        return json.dumps({"ok": False, "message": f"未知操作: {action}"}, ensure_ascii=False)

    # ------------------------------------------------------------------
    # Param validation helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _check_create(params: dict) -> list[str]:
        missing = []
        if not params.get("job_name"):
            missing.append("job_name（Job 名称）")
        if not params.get("config_xml"):
            missing.append("config_xml（XML 配置内容）")
        return missing

    @staticmethod
    def _check_update(params: dict) -> list[str]:
        missing = []
        if not params.get("job_name"):
            missing.append("job_name（Job 名称）")
        if not params.get("config_xml"):
            missing.append("config_xml（XML 配置内容）")
        return missing

    @staticmethod
    def _check_delete(params: dict) -> list[str]:
        missing = []
        if not params.get("job_name"):
            missing.append("job_name（Job 名称）")
        return missing

    # ------------------------------------------------------------------
    # Confirm-then-execute pattern
    # ------------------------------------------------------------------

    async def _require_confirm_then_execute(
        self,
        caller_id: str,
        action: str,
        params: dict,
        check_fn,
    ) -> str:
        missing = check_fn(params)
        if missing:
            return json.dumps({
                "ok": False,
                "error": "missing_params",
                "message": f"{action} 操作需要以下参数：{missing}，请提供后再操作。",
                "missing_params": missing,
            }, ensure_ascii=False)

        if not caller_id:
            return await self._dispatch(action, params)

        job_name = params.get("job_name", "")
        confirm_mgr = get_confirm_manager()
        confirm_mgr.set_pending(
            caller_id=caller_id,
            action=action,
            tool=self.name,
            params=params,
            instance_name=job_name,
        )

        action_desc = {
            "create": f"创建 Jenkins Job「{job_name}」",
            "update_config": f"更新 Jenkins Job「{job_name}」的配置",
            "delete": f"删除 Jenkins Job「{job_name}」",
        }

        return json.dumps({
            "ok": False,
            "error": "pending_confirm",
            "message": f"即将{action_desc[action]}，请回复「确认」以执行（其他内容无效）。",
            "pending_action": action,
            "job_name": job_name,
        }, ensure_ascii=False)

    async def _dispatch(self, action: str, params: dict) -> str:
        if action == "create":
            return await self._create(params)
        if action == "update_config":
            return await self._update_config(params)
        if action == "delete":
            return await self._delete(params)
        return json.dumps({"ok": False, "message": f"无法执行: {action}"}, ensure_ascii=False)

    # ------------------------------------------------------------------
    # Action implementations
    # ------------------------------------------------------------------

    async def _get_config(self, params: dict) -> str:
        job_name = str(params.get("job_name", "") or "").strip()
        if not job_name:
            return json.dumps({"ok": False, "message": "缺少 job_name"}, ensure_ascii=False)

        async def _handle(client):
            xml = await client.get_job_config(job_name)
            return {
                "ok": True,
                "job_name": job_name,
                "config_xml": xml,
            }

        instance_id = str(params.get("instance_id", "") or "").strip()
        return await self._run(_handle, instance_id=instance_id)

    async def _create(self, params: dict) -> str:
        job_name = str(params.get("job_name", "") or "").strip()
        config_xml = str(params.get("config_xml", "") or "").strip()
        folder = str(params.get("folder", "") or "").strip()

        async def _handle(client):
            result = await client.create_job(job_name, config_xml, folder=folder)
            return {
                "ok": True,
                "message": f"已创建 Jenkins Job: {job_name}" + (f"（在文件夹 {folder} 下）" if folder else ""),
                **result,
            }

        instance_id = str(params.get("instance_id", "") or "").strip()
        return await self._run(_handle, instance_id=instance_id)

    async def _update_config(self, params: dict) -> str:
        job_name = str(params.get("job_name", "") or "").strip()
        config_xml = str(params.get("config_xml", "") or "").strip()

        async def _handle(client):
            result = await client.update_job_config(job_name, config_xml)
            return {
                "ok": True,
                "message": f"已更新 Jenkins Job 配置: {job_name}",
                **result,
            }

        instance_id = str(params.get("instance_id", "") or "").strip()
        return await self._run(_handle, instance_id=instance_id)

    async def _delete(self, params: dict) -> str:
        job_name = str(params.get("job_name", "") or "").strip()

        async def _handle(client):
            result = await client.delete_job(job_name)
            return {
                "ok": True,
                "message": f"已删除 Jenkins Job: {job_name}",
                **result,
            }

        instance_id = str(params.get("instance_id", "") or "").strip()
        return await self._run(_handle, instance_id=instance_id)

    async def _copy(self, params: dict) -> str:
        src = str(params.get("src_job_name", "") or "").strip()
        new = str(params.get("new_job_name", "") or "").strip()
        folder = str(params.get("folder", "") or "").strip()

        if not src:
            return json.dumps({"ok": False, "message": "copy 缺少 src_job_name"}, ensure_ascii=False)
        if not new:
            return json.dumps({"ok": False, "message": "copy 缺少 new_job_name"}, ensure_ascii=False)

        async def _handle(client):
            result = await client.copy_job(src, new, folder=folder)
            return {
                "ok": True,
                "message": f"已复制 Job「{src}」为「{new}」" + (f"（在文件夹 {folder} 下）" if folder else ""),
                **result,
            }

        instance_id = str(params.get("instance_id", "") or "").strip()
        return await self._run(_handle, instance_id=instance_id)

    async def _enable(self, params: dict) -> str:
        job_name = str(params.get("job_name", "") or "").strip()
        if not job_name:
            return json.dumps({"ok": False, "message": "缺少 job_name"}, ensure_ascii=False)

        async def _handle(client):
            result = await client.enable_job(job_name)
            return {
                "ok": True,
                "message": f"已启用 Jenkins Job: {job_name}",
                **result,
            }

        instance_id = str(params.get("instance_id", "") or "").strip()
        return await self._run(_handle, instance_id=instance_id)

    async def _disable(self, params: dict) -> str:
        job_name = str(params.get("job_name", "") or "").strip()
        if not job_name:
            return json.dumps({"ok": False, "message": "缺少 job_name"}, ensure_ascii=False)

        async def _handle(client):
            result = await client.disable_job(job_name)
            return {
                "ok": True,
                "message": f"已禁用 Jenkins Job: {job_name}",
                **result,
            }

        instance_id = str(params.get("instance_id", "") or "").strip()
        return await self._run(_handle, instance_id=instance_id)
