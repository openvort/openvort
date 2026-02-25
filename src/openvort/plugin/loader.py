"""
插件加载器

通过 Python entry_points 和目录扫描自动发现并加载插件。
"""

from importlib.metadata import entry_points

from openvort.plugin.base import BaseChannel, BaseTool
from openvort.plugin.registry import PluginRegistry
from openvort.utils.logging import get_logger

log = get_logger("plugin.loader")


class PluginLoader:
    """插件加载器"""

    def __init__(self, registry: PluginRegistry):
        self.registry = registry

    def load_all(self) -> None:
        """加载所有插件（entry_points）"""
        self._load_channels()
        self._load_tools()

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
        """从 entry_points 加载 Tool 插件"""
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
