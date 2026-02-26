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

    def __init__(self, registry: PluginRegistry, auth_service=None):
        self.registry = registry
        self._plugins: list[BasePlugin] = []
        self._auth = auth_service

    def load_all(self) -> None:
        """加载所有插件（entry_points）"""
        self._load_plugins()
        self._load_channels()
        self._load_tools()
        self._inject_sync_providers()

    async def load_all_async(self) -> None:
        """异步注册插件声明的权限和角色（在 load_all 之后调用）"""
        await self._register_plugin_permissions()

    def get_plugins(self) -> list[BasePlugin]:
        """返回已加载的 Plugin 实例列表"""
        return list(self._plugins)

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
                self._plugins.append(plugin)
                self.registry.register_plugin(plugin)
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

    def _inject_sync_providers(self) -> None:
        """收集所有 SyncProvider 并注入到 ContactsPlugin"""
        from openvort.contacts.plugin import ContactsPlugin

        # 找到 ContactsPlugin 实例
        contacts_plugin = None
        for plugin in self._plugins:
            if isinstance(plugin, ContactsPlugin):
                contacts_plugin = plugin
                break

        if not contacts_plugin:
            return

        # 从所有 Channel 和 Plugin 收集 SyncProvider
        providers = []
        for ch in self.registry.list_channels():
            p = ch.get_sync_provider()
            if p:
                providers.append(p)

        for plugin in self._plugins:
            if plugin is contacts_plugin:
                continue
            p = plugin.get_sync_provider()
            if p:
                providers.append(p)

                contacts_plugin.set_providers(providers)

    async def _register_plugin_permissions(self) -> None:
        """注册所有 Plugin 声明的权限和角色到 AuthService"""
        if not self._auth:
            return

        for plugin in self._plugins:
            source = plugin.name

            # 注册权限
            for perm_def in plugin.get_permissions():
                await self._auth.register_permission(
                    code=perm_def["code"],
                    display_name=perm_def.get("display_name", ""),
                    source=source,
                )

            # 注册角色
            for role_def in plugin.get_roles():
                await self._auth.register_role(
                    name=role_def["name"],
                    display_name=role_def.get("display_name", ""),
                    permissions=role_def.get("permissions", []),
                    source=source,
                )

        log.info("插件权限和角色注册完成")
