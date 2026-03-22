"""同步通讯录工具 — 管理员通过聊天触发平台通讯录同步"""

import json

from openvort.config.settings import get_settings
from openvort.contacts.service import ContactService
from openvort.contacts.sync import ContactSyncProvider
from openvort.db.engine import get_session_factory
from openvort.plugin.base import BaseTool
from openvort.utils.logging import get_logger

log = get_logger("contacts.tools.sync")


class SyncContactsTool(BaseTool):
    name = "contacts_sync"
    description = "从外部平台同步通讯录成员（企微/禅道等），需要管理员权限"
    required_permission = "contacts.sync"

    def __init__(self):
        self._providers: list[ContactSyncProvider] = []
        self._auth_service = None

    def set_providers(self, providers: list[ContactSyncProvider]) -> None:
        """注入可用的同步提供者（由 ContactsPlugin 调用）"""
        self._providers = providers

    def set_auth_service(self, auth_service) -> None:
        """注入 AuthService（由 ContactsPlugin 调用）"""
        self._auth_service = auth_service

    def input_schema(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "platform": {
                    "type": "string",
                    "description": "要同步的平台（wecom/zentao/...），不指定则同步全部",
                },
            },
        }

    async def execute(self, params: dict) -> str:
        platform = params.get("platform")
        providers = self._providers
        if platform:
            providers = [p for p in providers if p.platform == platform]

        if not providers:
            return json.dumps(
                {"ok": False, "error": f"未找到可用的同步源{f' ({platform})' if platform else ''}"},
                ensure_ascii=False,
            )

        settings = get_settings()
        service = ContactService(
            get_session_factory(),
            settings.contacts.auto_match_threshold,
            auth_service=self._auth_service,
        )
        results = {}
        for provider in providers:
            try:
                stats = await service.sync_from_provider(provider)
                results[provider.platform] = stats
            except Exception as e:
                log.error(f"同步 {provider.platform} 失败: {e}")
                results[provider.platform] = {"error": str(e)}

        return json.dumps({"ok": True, "results": results}, ensure_ascii=False)
