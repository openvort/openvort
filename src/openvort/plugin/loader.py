"""
插件加载器

通过 Python entry_points 自动发现并加载 Plugin、Channel 和 Tool。
"""

from importlib.metadata import entry_points

from openvort.plugin.base import BaseChannel, BasePlugin, BaseTool
from openvort.plugin.registry import PluginRegistry
from openvort.utils.logging import get_logger

log = get_logger("plugin.loader")


class PluginLoader:
    """插件加载器"""

    def __init__(self, registry: PluginRegistry):
        self.registry = registry

    def load_all(self) -> None:
        """加载所有插件（entry_points）"""
        self._load_plugins()
        self._load_channels()
        self._load_tools()

    def _load_plugins(self) -> None:
        """从 entry_points 加载 Plugin（自动注册其 Tools 和 Prompts）"""
        eps = entry_points()
        plugin_eps = eps.select(group="openvort.plugins") if hasattr(eps, "select") else eps.get("openvort.plugins", [])

        for ep in plugin_eps:
            try:
                cls = ep.load()
                if not (isinstance(cls, type) and issubclass(cls, BasePlugin)):
                    log.warning(f"Plugin entry_point '{ep.name}' 不是 BasePlugin 子类，跳过")
                    continue

                plugin = cls()

                if not plugin.validate_credentials():
                    log.warning(f"Plugin '{plugin.name}' 凭证校验失败，跳过（请检查配置）")
                    continue

                # 注册 Plugin 的所有 Tools
                tools = plugin.get_tools()
                for tool in tools:
                    self.registry.register_tool(tool)

                # 注册 Plugin 的领域知识 Prompts
                prompts = plugin.get_prompts()
                for prompt in prompts:
                    self.registry.register_prompt(prompt)

                log.info(
                    f"已加载 Plugin: {plugin.name} ({plugin.display_name}) "
                    f"— {len(tools)} 个 Tool, {len(prompts)} 条 Prompt"
                )
            except Exception as e:
                log.error(f"加载 Plugin '{ep.name}' 失败: {e}")

    def _load_channels(self) -> None:
        """从 entry_points 加载 Channel 插件"""
        eps = entry_points()
        channel_eps = eps.select(group="openvort.channels") if hasattr(eps, "select") else eps.get("openvort.channels", [])

        for ep in channel_eps:
            try:
                cls = ep.load()
                if isinstance(cls, type) and issubclass(cls, BaseChannel):
                    instance = cls()
                    self.registry.register_channel(instance)
                else:
                    log.warning(f"Channel entry_point '{ep.name}' 不是 BaseChannel 子类，跳过")
            except Exception as e:
                log.error(f"加载 Channel '{ep.name}' 失败: {e}")

    def _load_tools(self) -> None:
        """从 entry_points 加载独立 Tool 插件（非 Plugin 管理的散装 Tool）"""
        eps = entry_points()
        tool_eps = eps.select(group="openvort.tools") if hasattr(eps, "select") else eps.get("openvort.tools", [])

        for ep in tool_eps:
            try:
                cls = ep.load()
                if isinstance(cls, type) and issubclass(cls, BaseTool):
                    instance = cls()
                    self.registry.register_tool(instance)
                else:
                    log.warning(f"Tool entry_point '{ep.name}' 不是 BaseTool 子类，跳过")
            except Exception as e:
                log.error(f"加载 Tool '{ep.name}' 失败: {e}")
