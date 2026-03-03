"""
Common helpers for Jenkins tools.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, Awaitable, Callable

from sqlalchemy import select

from openvort.db.engine import get_session_factory
from openvort.plugin.base import BaseTool
from openvort.plugins.jenkins.client import JenkinsClient, JenkinsClientError, JenkinsConnection
from openvort.plugins.jenkins.models import JenkinsInstance
from openvort.plugins.vortgit.crypto import decrypt_token
from openvort.utils.logging import get_logger

log = get_logger("plugins.jenkins.tools.base")


@dataclass(slots=True)
class ResolvedJenkinsInstance:
    id: str
    name: str
    url: str
    username: str
    api_token: str
    verify_ssl: bool


class JenkinsToolBase(BaseTool):
    """Base class to share client creation and error handling."""

    async def _resolve_instance(self, instance_id: str = "") -> ResolvedJenkinsInstance:
        target_id = str(instance_id or "").strip()
        sf = get_session_factory()
        async with sf() as session:
            if target_id:
                instance = await session.get(JenkinsInstance, target_id)
                if not instance:
                    raise JenkinsClientError(f"Jenkins 实例不存在: {target_id}")
            else:
                result = await session.execute(
                    select(JenkinsInstance).order_by(JenkinsInstance.created_at.asc())
                )
                instances = result.scalars().all()
                if not instances:
                    raise JenkinsClientError(
                        "尚未配置 Jenkins 实例，请先调用 jenkins_manage_instance 创建实例"
                    )
                if len(instances) == 1:
                    instance = instances[0]
                else:
                    instance = next((it for it in instances if it.is_default), None)
                    if instance is None:
                        raise JenkinsClientError(
                            "存在多个 Jenkins 实例但未设置默认实例，请传入 instance_id"
                        )

            encrypted_token = str(instance.api_token or "").strip()
            if not encrypted_token:
                raise JenkinsClientError(f"Jenkins 实例 '{instance.name}' 缺少 API Token")
            try:
                token = decrypt_token(encrypted_token)
            except Exception:
                raise JenkinsClientError(f"Jenkins 实例 '{instance.name}' 的 API Token 解密失败")

            return ResolvedJenkinsInstance(
                id=instance.id,
                name=str(instance.name or ""),
                url=str(instance.url or ""),
                username=str(instance.username or ""),
                api_token=token,
                verify_ssl=bool(instance.verify_ssl),
            )

    async def _run(
        self,
        fn: Callable[[JenkinsClient], Awaitable[dict[str, Any]]],
        *,
        instance_id: str = "",
    ) -> str:
        client: JenkinsClient | None = None
        try:
            instance = await self._resolve_instance(instance_id)
            client = JenkinsClient(
                JenkinsConnection(
                    url=instance.url,
                    username=instance.username,
                    api_token=instance.api_token,
                    verify_ssl=instance.verify_ssl,
                )
            )
            if not client.is_configured():
                missing = ", ".join(client.missing_config_fields())
                return json.dumps(
                    {
                        "ok": False,
                        "message": (
                            f"Jenkins 实例 '{instance.name}' 配置不完整: {missing}，"
                            "请先用 jenkins_manage_instance 更新实例配置"
                        ),
                    },
                    ensure_ascii=False,
                )

            payload = await fn(client)
            if "ok" not in payload:
                payload["ok"] = True
            payload.setdefault(
                "instance",
                {
                    "id": instance.id,
                    "name": instance.name,
                    "url": instance.url,
                },
            )
            return json.dumps(payload, ensure_ascii=False, default=str)
        except JenkinsClientError as e:
            return json.dumps({"ok": False, "message": str(e)}, ensure_ascii=False)
        except Exception as e:
            log.exception(f"{self.name} 执行异常: {e}")
            return json.dumps({"ok": False, "message": f"工具执行失败: {e}"}, ensure_ascii=False)
        finally:
            if client:
                await client.close()
