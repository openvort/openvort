"""
插件注册中心

管理所有已加载的 Channel、Tool 和 Plugin Prompt 实例。
"""

from openvort.plugin.base import BaseChannel, BaseTool
from openvort.utils.logging import get_logger

log = get_logger("plugin.registry")


class PluginRegistry:
    """插件注册中心"""

    def __init__(self):
        self._channels: dict[str, BaseChannel] = {}
        self._tools: dict[str, BaseTool] = {}
        self._prompts: list[str] = []
        self._plugins: dict[str, "BasePlugin"] = {}

    # ---- Plugin 管理 ----

    def register_plugin(self, plugin: "BasePlugin") -> None:
        """注册一个 Plugin 实例"""
        from openvort.plugin.base import BasePlugin
        if not isinstance(plugin, BasePlugin):
            return
        self._plugins[plugin.name] = plugin
        log.info(f"已注册 Plugin: {plugin.name}")

    def get_plugin(self, name: str) -> "BasePlugin | None":
        """获取指定 Plugin"""
        return self._plugins.get(name)

    def list_plugins(self) -> list["BasePlugin"]:
        """列出所有已注册的 Plugin"""
        return list(self._plugins.values())

    def unregister_plugin(self, name: str) -> None:
        """注销一个 Plugin 及其 Tools 和 Prompts"""
        plugin = self._plugins.pop(name, None)
        if not plugin:
            return
        # 移除该插件的所有 Tool
        tool_names = [t.name for t in plugin.get_tools()]
        for tn in tool_names:
            self._tools.pop(tn, None)
        # 移除该插件的 Prompts
        plugin_prompts = set(plugin.get_prompts())
        self._prompts = [p for p in self._prompts if p not in plugin_prompts]
        log.info(f"已注销 Plugin: {name}（移除 {len(tool_names)} 个 Tool）")

    # ---- Channel 管理 ----

    def register_channel(self, channel: BaseChannel) -> None:
        """注册一个 Channel"""
        if channel.name in self._channels:
            log.warning(f"Channel '{channel.name}' 已存在，将被覆盖")
        self._channels[channel.name] = channel
        log.info(f"已注册 Channel: {channel.name} ({channel.display_name})")

    def get_channel(self, name: str) -> BaseChannel | None:
        """获取指定 Channel"""
        return self._channels.get(name)

    def list_channels(self) -> list[BaseChannel]:
        """列出所有已注册的 Channel"""
        return list(self._channels.values())

    # ---- Tool 管理 ----

    def register_tool(self, tool: BaseTool) -> None:
        """注册一个 Tool"""
        if tool.name in self._tools:
            log.warning(f"Tool '{tool.name}' 已存在，将被覆盖")
        self._tools[tool.name] = tool
        log.info(f"已注册 Tool: {tool.name}")

    def get_tool(self, name: str) -> BaseTool | None:
        """获取指定 Tool"""
        return self._tools.get(name)

    def list_tools(self) -> list[BaseTool]:
        """列出所有已注册的 Tool"""
        return list(self._tools.values())

    async def execute_tool(self, name: str, params: dict) -> str:
        """执行指定工具"""
        tool = self._tools.get(name)
        if not tool:
            return f"错误：未找到工具 '{name}'"
        try:
            return await tool.execute(params)
        except Exception as e:
            log.error(f"工具 '{name}' 执行失败: {e}")
            return f"工具执行失败: {e}"

    def to_claude_tools(
        self,
        permissions: set[str] | None = None,
        allowed_tools: list[str] | None = None,
    ) -> list[dict]:
        """将 Tool 转换为 Claude tool use 格式，支持按权限和渠道过滤

        Args:
            permissions: 用户权限集合，None 表示不过滤
            allowed_tools: 渠道允许的 Tool 名称列表，None 表示不限制
        """
        result = []
        for tool in self._tools.values():
            # 渠道过滤
            if allowed_tools is not None and tool.name not in allowed_tools:
                continue
            # 权限过滤
            if permissions is not None and tool.required_permission:
                if "*" not in permissions and tool.required_permission not in permissions:
                    continue
            result.append(tool.to_claude_tool())
        return result

    # ---- Prompt 管理（插件领域知识）----

    def register_prompt(self, prompt: str) -> None:
        """注册一条插件领域知识 prompt"""
        self._prompts.append(prompt)

    def get_system_prompt_extension(self) -> str:
        """拼接所有插件的领域知识，用于追加到 Agent system prompt"""
        if not self._prompts:
            return ""
        return "\n\n".join(self._prompts)
