"""
System channel config tool — system_channel_config

List, inspect, and update channel configurations via AI conversation.
"""

import json

from openvort.plugin.base import BaseTool
from openvort.utils.logging import get_logger

log = get_logger("plugins.system.tools.channel_config")


class SystemChannelConfigTool(BaseTool):
    name = "system_channel_config"
    description = (
        "管理 IM 通道配置：列出所有通道及状态、查看通道配置详情和引导说明、更新通道配置字段。"
        "适用于帮助管理员配置企业微信/钉钉/飞书/OpenClaw 等 IM 通道的接入。"
    )
    required_permission = "admin"

    def input_schema(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "action": {
                    "type": "string",
                    "description": "操作类型: list(列出所有通道), get(查看指定通道详情), update(更新通道配置)",
                    "enum": ["list", "get", "update"],
                },
                "channel_name": {
                    "type": "string",
                    "description": "通道标识 (get/update 时必填，如 wecom/dingtalk/feishu/openclaw)",
                },
                "config": {
                    "type": "object",
                    "description": "要更新的配置键值对 (update 时必填，如 {\"corp_id\": \"ww123\", \"app_secret\": \"xxx\"})",
                },
            },
            "required": ["action"],
        }

    async def execute(self, params: dict) -> str:
        from openvort.plugin.registry import PluginRegistry
        from openvort.web.deps import get_registry, get_db_session_factory

        action = params["action"]
        registry: PluginRegistry = get_registry()

        if action == "list":
            return await self._list_channels(registry)
        elif action == "get":
            channel_name = params.get("channel_name", "")
            if not channel_name:
                return "错误：get 操作需要指定 channel_name"
            return await self._get_channel(registry, channel_name)
        elif action == "update":
            channel_name = params.get("channel_name", "")
            config = params.get("config", {})
            if not channel_name:
                return "错误：update 操作需要指定 channel_name"
            if not config:
                return "错误：update 操作需要提供 config 参数"
            return await self._update_channel(registry, get_db_session_factory(), channel_name, config)
        else:
            return f"错误：未知操作 '{action}'"

    async def _list_channels(self, registry) -> str:
        from openvort.db.models import ChannelConfig
        from openvort.web.deps import get_db_session_factory
        from sqlalchemy import select

        channels = registry.list_channels()
        if not channels:
            return "当前没有已注册的通道"

        session_factory = get_db_session_factory()
        lines = ["当前已注册的 IM 通道：\n"]
        for ch in channels:
            async with session_factory() as session:
                result = await session.execute(
                    select(ChannelConfig).where(ChannelConfig.channel_name == ch.name)
                )
                db_config = result.scalar_one_or_none()
            enabled = db_config.enabled if db_config else True
            configured = ch.is_configured()
            status = "已连接" if configured else "未连接"
            enabled_text = "已启用" if enabled else "已禁用"
            lines.append(
                f"- **{ch.display_name}** ({ch.name}): {ch.description}\n"
                f"  状态: {status} | {enabled_text}"
            )
        return "\n".join(lines)

    async def _get_channel(self, registry, channel_name: str) -> str:
        ch = registry.get_channel(channel_name)
        if not ch:
            available = [c.name for c in registry.list_channels()]
            return f"错误：通道 '{channel_name}' 不存在。可用通道: {', '.join(available)}"

        schema = ch.get_config_schema()
        current = ch.get_current_config()
        guide = ch.get_setup_guide()

        lines = [f"## {ch.display_name} ({ch.name})\n", ch.description, ""]

        if guide:
            lines.append(guide)

        lines.append("### 当前配置\n")
        for field in schema:
            key = field["key"]
            label = field.get("label", key)
            required = "必填" if field.get("required") else "可选"
            value = current.get(key, "")
            desc = field.get("description", "")
            value_display = value if value else "(未设置)"
            lines.append(f"- **{label}** (`{key}`, {required}): {value_display}")
            if desc:
                lines.append(f"  说明: {desc}")

        return "\n".join(lines)

    async def _update_channel(self, registry, session_factory, channel_name: str, config: dict) -> str:
        from openvort.db.models import ChannelConfig
        from sqlalchemy import select

        ch = registry.get_channel(channel_name)
        if not ch:
            return f"错误：通道 '{channel_name}' 不存在"

        schema = ch.get_config_schema()
        secret_keys = {f["key"] for f in schema if f.get("secret")}
        valid_keys = {f["key"] for f in schema}

        invalid_keys = set(config.keys()) - valid_keys
        if invalid_keys:
            return f"错误：无效的配置键 {invalid_keys}。有效键: {valid_keys}"

        # Read existing raw config from DB
        async with session_factory() as session:
            result = await session.execute(
                select(ChannelConfig).where(ChannelConfig.channel_name == channel_name)
            )
            db_row = result.scalar_one_or_none()
        existing_raw = json.loads(db_row.config_data) if db_row and db_row.config_data else {}

        # Merge: keep existing secret values if new value is masked
        merged = {}
        for key, value in config.items():
            if key in secret_keys and isinstance(value, str) and value.startswith("****"):
                if key in existing_raw:
                    merged[key] = existing_raw[key]
            else:
                merged[key] = value

        # Apply to runtime
        ch.apply_config(merged)

        # Persist to DB
        full_config = {**existing_raw, **merged}
        async with session_factory() as session:
            result = await session.execute(
                select(ChannelConfig).where(ChannelConfig.channel_name == channel_name)
            )
            config_row = result.scalar_one_or_none()
            if config_row is None:
                config_row = ChannelConfig(
                    channel_name=channel_name,
                    config_data=json.dumps(full_config),
                    enabled=True,
                )
                session.add(config_row)
            else:
                config_row.config_data = json.dumps(full_config)
            await session.commit()

        updated_fields = list(config.keys())
        return f"通道 '{ch.display_name}' 配置已更新。已修改字段: {', '.join(updated_fields)}。建议执行诊断（system_diagnose）测试连通性。"
