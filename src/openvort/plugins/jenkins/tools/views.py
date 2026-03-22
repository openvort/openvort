"""Jenkins view management tool."""

from __future__ import annotations

import json

from openvort.plugins.jenkins.tools.base import JenkinsToolBase


class ManageViewTool(JenkinsToolBase):
    name = "jenkins_manage_view"
    description = (
        "管理 Jenkins 视图（View）。"
        "支持 list/create/delete 操作，用于组织和筛选 Job 列表。"
    )
    required_permission = "jenkins.write"

    def input_schema(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "action": {
                    "type": "string",
                    "enum": ["list", "create", "delete"],
                    "description": "操作类型：list 列出视图，create 创建视图，delete 删除视图",
                },
                "instance_id": {
                    "type": "string",
                    "description": "Jenkins 实例 ID（多实例时需指定）",
                    "default": "",
                },
                "name": {
                    "type": "string",
                    "description": "视图名称（create/delete 必填）",
                    "default": "",
                },
                "include_regex": {
                    "type": "string",
                    "description": "Job 名称正则过滤（create 时可选，匹配的 Job 会自动包含在视图中）",
                    "default": "",
                },
            },
            "required": ["action"],
        }

    async def execute(self, params: dict) -> str:
        action = str(params.get("action", "") or "").strip().lower()
        instance_id = str(params.get("instance_id", "") or "").strip()

        if action == "list":
            return await self._list_views(instance_id)
        if action == "create":
            return await self._create_view(params, instance_id)
        if action == "delete":
            return await self._delete_view(params, instance_id)

        return json.dumps({"ok": False, "message": f"未知操作: {action}"}, ensure_ascii=False)

    async def _list_views(self, instance_id: str) -> str:
        async def _handle(client):
            data = await client.get_system_info()
            views = data.get("views", [])
            view_names = [v.get("name", "") for v in views if isinstance(v, dict)]
            return {
                "ok": True,
                "count": len(view_names),
                "views": view_names,
                "hint": "使用 create 创建新视图，使用 delete 删除视图。All 视图不可删除。",
            }

        return await self._run(_handle, instance_id=instance_id)

    async def _create_view(self, params: dict, instance_id: str) -> str:
        name = str(params.get("name", "") or "").strip()
        if not name:
            return json.dumps(
                {"ok": False, "message": "create 需要 name 参数（视图名称）"},
                ensure_ascii=False,
            )

        include_regex = str(params.get("include_regex", "") or "").strip()

        async def _handle(client):
            result = await client.create_view(name, include_regex=include_regex)
            msg = f"视图「{name}」创建成功"
            if include_regex:
                msg += f"，Job 过滤正则: {include_regex}"
            return {"ok": True, "message": msg, **result}

        return await self._run(_handle, instance_id=instance_id)

    async def _delete_view(self, params: dict, instance_id: str) -> str:
        name = str(params.get("name", "") or "").strip()
        if not name:
            return json.dumps(
                {"ok": False, "message": "delete 需要 name 参数（视图名称）"},
                ensure_ascii=False,
            )

        async def _handle(client):
            result = await client.delete_view(name)
            return {"ok": True, "message": f"视图「{name}」已删除", **result}

        return await self._run(_handle, instance_id=instance_id)
