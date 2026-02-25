"""
插件注册中心

管理所有已加载的 Channel 和 Tool 实例。
"""

from openvort.plugin.base import BaseChannel, BaseTool
from openvort.utils.logging import get_logger

log = get_logger("plugin.registry")


class PluginRegistry:
    """插件注册中心"""

    def __init__(self):
        self._channels: dict[str, BaseChannel] = {}
        self._tools: dict[str, BaseTool] = {}

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

    def to_claude_tools(self) -> list[dict]:
        """将所有 Tool 转换为 Claude tool use 格式"""
        return [tool.to_claude_tool() for tool in self._tools.values()]
