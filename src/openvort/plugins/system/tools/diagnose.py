"""
System diagnose tool — system_diagnose

Diagnose channel connectivity and overall system health.
"""

from openvort.plugin.base import BaseTool
from openvort.utils.logging import get_logger

log = get_logger("plugins.system.tools.diagnose")


class SystemDiagnoseTool(BaseTool):
    name = "system_diagnose"
    description = (
        "诊断 OpenVort 系统状态：检测通道连通性、LLM 配置有效性、插件加载情况。"
        "可对指定通道进行连接测试，也可进行全局系统健康检查。"
    )
    required_permission = "admin"

    def input_schema(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "target": {
                    "type": "string",
                    "description": "诊断目标: channel(单个通道连通性), all_channels(所有通道), system(全局系统状态)",
                    "enum": ["channel", "all_channels", "system"],
                },
                "channel_name": {
                    "type": "string",
                    "description": "通道标识 (target=channel 时必填)",
                },
            },
            "required": ["target"],
        }

    async def execute(self, params: dict) -> str:
        from openvort.web.deps import get_registry

        target = params["target"]
        registry = get_registry()

        if target == "channel":
            channel_name = params.get("channel_name", "")
            if not channel_name:
                return "错误：target=channel 时需要指定 channel_name"
            return await self._diagnose_channel(registry, channel_name)
        elif target == "all_channels":
            return await self._diagnose_all_channels(registry)
        elif target == "system":
            return await self._diagnose_system(registry)
        else:
            return f"错误：未知目标 '{target}'"

    async def _diagnose_channel(self, registry, channel_name: str) -> str:
        ch = registry.get_channel(channel_name)
        if not ch:
            available = [c.name for c in registry.list_channels()]
            return f"错误：通道 '{channel_name}' 不存在。可用通道: {', '.join(available)}"

        lines = [f"## {ch.display_name} 诊断结果\n"]

        configured = ch.is_configured()
        lines.append(f"- 配置完整性: {'✓ 已配置' if configured else '✗ 未配置（缺少必填字段）'}")

        if not configured:
            schema = ch.get_config_schema()
            current = ch.get_current_config()
            missing = [f["label"] for f in schema if f.get("required") and not current.get(f["key"])]
            if missing:
                lines.append(f"- 缺少必填字段: {', '.join(missing)}")
            lines.append("\n请先完成配置再测试连通性。")
            return "\n".join(lines)

        result = await ch.test_connection()
        ok = result.get("ok", False)
        message = result.get("message", "")
        lines.append(f"- 连接测试: {'✓ 成功' if ok else '✗ 失败'}")
        lines.append(f"- 详情: {message}")

        conn = ch.get_connection_info()
        mode = conn.get("mode", "unknown")
        lines.append(f"- 连接模式: {mode}")

        return "\n".join(lines)

    async def _diagnose_all_channels(self, registry) -> str:
        channels = registry.list_channels()
        if not channels:
            return "当前没有已注册的通道"

        lines = ["## 全部通道诊断\n"]
        for ch in channels:
            configured = ch.is_configured()
            if configured:
                try:
                    result = await ch.test_connection()
                    ok = result.get("ok", False)
                    msg = result.get("message", "")
                    status = f"✓ 连接成功 — {msg}" if ok else f"✗ 连接失败 — {msg}"
                except Exception as e:
                    status = f"✗ 测试异常 — {e}"
            else:
                status = "○ 未配置"
            lines.append(f"- **{ch.display_name}** ({ch.name}): {status}")

        return "\n".join(lines)

    async def _diagnose_system(self, registry) -> str:
        lines = ["## OpenVort 系统诊断\n"]

        # Channels
        channels = registry.list_channels()
        configured_count = sum(1 for ch in channels if ch.is_configured())
        lines.append(f"### 通道 ({configured_count}/{len(channels)} 已配置)\n")
        for ch in channels:
            configured = ch.is_configured()
            lines.append(f"- {ch.display_name}: {'已配置' if configured else '未配置'}")

        # Plugins
        plugins = registry.list_plugins()
        lines.append(f"\n### 插件 ({len(plugins)} 个)\n")
        for p in plugins:
            disabled = p.name in registry._disabled
            status = "已禁用" if disabled else "已启用"
            lines.append(f"- {p.display_name} ({p.name}): {status}")

        # Tools
        tools = registry.list_tools()
        lines.append(f"\n### 工具 ({len(tools)} 个已注册)\n")

        # LLM config
        try:
            from openvort.config.settings import get_settings
            settings = get_settings()
            llm = settings.llm
            lines.append("\n### LLM 配置\n")
            lines.append(f"- Provider: {llm.provider}")
            lines.append(f"- Model: {llm.model}")
            lines.append(f"- API Key: {'已配置' if llm.api_key else '未配置'}")
            if llm.api_base:
                lines.append(f"- API Base: {llm.api_base}")
        except Exception:
            lines.append("\n### LLM 配置\n- 无法读取 LLM 配置")

        return "\n".join(lines)
