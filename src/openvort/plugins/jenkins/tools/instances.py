"""Jenkins instance management tool."""

from __future__ import annotations

import json
import uuid

from sqlalchemy import func, select, update

from openvort.db.engine import get_session_factory
from openvort.plugins.jenkins.models import JenkinsInstance
from openvort.plugins.jenkins.tools.base import JenkinsToolBase
from openvort.plugins.vortgit.crypto import encrypt_token


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


class JenkinsManageInstanceTool(JenkinsToolBase):
    name = "jenkins_manage_instance"
    description = (
        "管理 Jenkins 实例配置。"
        "支持 list/create/update/delete/verify 操作，适用于企业内多 Jenkins 环境。"
    )
    required_permission = "jenkins.write"

    def input_schema(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "action": {
                    "type": "string",
                    "enum": ["list", "create", "update", "delete", "verify"],
                    "description": "操作类型",
                },
                "instance_id": {
                    "type": "string",
                    "description": "实例 ID（update/delete/verify 推荐传）",
                    "default": "",
                },
                "name": {
                    "type": "string",
                    "description": "实例名称（create 必填，update 可选）",
                    "default": "",
                },
                "url": {
                    "type": "string",
                    "description": "Jenkins 地址，例如 http://jenkins.company.local:8080",
                    "default": "",
                },
                "username": {
                    "type": "string",
                    "description": "Jenkins 用户名",
                    "default": "",
                },
                "api_token": {
                    "type": "string",
                    "description": "Jenkins API Token（create 必填，update 可选，不传表示不修改）",
                    "default": "",
                },
                "verify_ssl": {
                    "type": "boolean",
                    "description": "是否验证 SSL 证书，默认 true",
                    "default": True,
                },
                "is_default": {
                    "type": "boolean",
                    "description": "是否设置为默认实例，默认 false",
                    "default": False,
                },
            },
            "required": ["action"],
        }

    async def execute(self, params: dict) -> str:
        action = str(params.get("action", "") or "").strip().lower()
        if action == "list":
            return await self._list()
        if action == "create":
            return await self._create(params)
        if action == "update":
            return await self._update(params)
        if action == "delete":
            return await self._delete(params)
        if action == "verify":
            return await self._verify(params)
        return json.dumps({"ok": False, "message": f"未知操作: {action}"}, ensure_ascii=False)

    async def _list(self) -> str:
        sf = get_session_factory()
        async with sf() as session:
            result = await session.execute(
                select(JenkinsInstance).order_by(JenkinsInstance.created_at.desc())
            )
            instances = result.scalars().all()

        data = [
            {
                "id": it.id,
                "name": it.name,
                "url": it.url,
                "username": it.username,
                "has_token": bool(it.api_token),
                "verify_ssl": bool(it.verify_ssl),
                "is_default": bool(it.is_default),
            }
            for it in instances
        ]
        return json.dumps(
            {
                "ok": True,
                "count": len(data),
                "instances": data,
                "hint": "使用 create 添加实例；使用 verify 测试连通性。",
            },
            ensure_ascii=False,
        )

    async def _create(self, params: dict) -> str:
        name = str(params.get("name", "") or "").strip()
        url = str(params.get("url", "") or "").strip()
        username = str(params.get("username", "") or "").strip()
        api_token = str(params.get("api_token", "") or "").strip()
        verify_ssl = _parse_bool(params.get("verify_ssl"), True)
        is_default = _parse_bool(params.get("is_default"), False)

        if not name:
            return json.dumps({"ok": False, "message": "create 缺少 name"}, ensure_ascii=False)
        if not url:
            return json.dumps({"ok": False, "message": "create 缺少 url"}, ensure_ascii=False)
        if not username:
            return json.dumps({"ok": False, "message": "create 缺少 username"}, ensure_ascii=False)
        if not api_token:
            return json.dumps({"ok": False, "message": "create 缺少 api_token"}, ensure_ascii=False)

        sf = get_session_factory()
        async with sf() as session:
            exists = await session.scalar(
                select(JenkinsInstance).where(JenkinsInstance.name == name).limit(1)
            )
            if exists:
                return json.dumps(
                    {"ok": False, "message": f"实例名称已存在: {name}，请使用其他名称"},
                    ensure_ascii=False,
                )

            count = await session.scalar(select(func.count()).select_from(JenkinsInstance))
            if not count:
                is_default = True

            if is_default:
                await session.execute(update(JenkinsInstance).values(is_default=False))

            instance = JenkinsInstance(
                id=uuid.uuid4().hex,
                name=name,
                url=url.rstrip("/"),
                username=username,
                api_token=encrypt_token(api_token),
                verify_ssl=verify_ssl,
                is_default=is_default,
            )
            session.add(instance)
            await session.commit()
            await session.refresh(instance)

        return json.dumps(
            {
                "ok": True,
                "message": f"已创建 Jenkins 实例: {name}",
                "instance": {
                    "id": instance.id,
                    "name": instance.name,
                    "url": instance.url,
                    "username": instance.username,
                    "verify_ssl": bool(instance.verify_ssl),
                    "is_default": bool(instance.is_default),
                },
            },
            ensure_ascii=False,
        )

    async def _update(self, params: dict) -> str:
        instance_id = str(params.get("instance_id", "") or "").strip()
        if not instance_id:
            return json.dumps({"ok": False, "message": "update 缺少 instance_id"}, ensure_ascii=False)

        sf = get_session_factory()
        async with sf() as session:
            instance = await session.get(JenkinsInstance, instance_id)
            if not instance:
                return json.dumps({"ok": False, "message": "实例不存在"}, ensure_ascii=False)

            if "name" in params:
                name = str(params.get("name", "") or "").strip()
                if not name:
                    return json.dumps({"ok": False, "message": "name 不能为空"}, ensure_ascii=False)
                if name != instance.name:
                    conflict = await session.scalar(
                        select(JenkinsInstance).where(JenkinsInstance.name == name).limit(1)
                    )
                    if conflict:
                        return json.dumps(
                            {"ok": False, "message": f"实例名称已存在: {name}"},
                            ensure_ascii=False,
                        )
                instance.name = name

            if "url" in params:
                url = str(params.get("url", "") or "").strip()
                if not url:
                    return json.dumps({"ok": False, "message": "url 不能为空"}, ensure_ascii=False)
                instance.url = url.rstrip("/")

            if "username" in params:
                username = str(params.get("username", "") or "").strip()
                if not username:
                    return json.dumps({"ok": False, "message": "username 不能为空"}, ensure_ascii=False)
                instance.username = username

            raw_token = params.get("api_token", None)
            if raw_token is not None:
                token = str(raw_token or "").strip()
                if token:
                    instance.api_token = encrypt_token(token)

            if "verify_ssl" in params:
                instance.verify_ssl = _parse_bool(params.get("verify_ssl"), bool(instance.verify_ssl))

            if "is_default" in params:
                target_default = _parse_bool(params.get("is_default"), bool(instance.is_default))
                if target_default:
                    await session.execute(update(JenkinsInstance).values(is_default=False))
                    instance.is_default = True
                else:
                    instance.is_default = False

            await session.commit()
            await session.refresh(instance)

            if not instance.is_default:
                defaults = await session.scalar(
                    select(JenkinsInstance).where(JenkinsInstance.is_default.is_(True)).limit(1)
                )
                if not defaults:
                    # Ensure at least one default when instances exist.
                    instance.is_default = True
                    await session.commit()
                    await session.refresh(instance)

        return json.dumps(
            {
                "ok": True,
                "message": f"已更新 Jenkins 实例: {instance.name}",
                "instance": {
                    "id": instance.id,
                    "name": instance.name,
                    "url": instance.url,
                    "username": instance.username,
                    "verify_ssl": bool(instance.verify_ssl),
                    "is_default": bool(instance.is_default),
                },
            },
            ensure_ascii=False,
        )

    async def _delete(self, params: dict) -> str:
        instance_id = str(params.get("instance_id", "") or "").strip()
        if not instance_id:
            return json.dumps({"ok": False, "message": "delete 缺少 instance_id"}, ensure_ascii=False)

        sf = get_session_factory()
        async with sf() as session:
            instance = await session.get(JenkinsInstance, instance_id)
            if not instance:
                return json.dumps({"ok": False, "message": "实例不存在"}, ensure_ascii=False)
            deleted_name = instance.name
            was_default = bool(instance.is_default)

            await session.delete(instance)
            await session.commit()

            if was_default:
                next_default = await session.scalar(
                    select(JenkinsInstance).order_by(JenkinsInstance.created_at.asc()).limit(1)
                )
                if next_default:
                    next_default.is_default = True
                    await session.commit()

        return json.dumps(
            {"ok": True, "message": f"已删除 Jenkins 实例: {deleted_name}"},
            ensure_ascii=False,
        )

    async def _verify(self, params: dict) -> str:
        instance_id = str(params.get("instance_id", "") or "").strip()

        async def _handle(client):
            data = await client.get_system_info()
            return {"ok": True, "message": "Jenkins 实例连接成功", "system": data}

        return await self._run(_handle, instance_id=instance_id)
