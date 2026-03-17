"""
插件加载器

通过 Python entry_points 自动发现并加载 Plugin、Channel 和 Tool。
"""

import importlib.util
import inspect
import sys
from importlib.metadata import entry_points
from pathlib import Path

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
        """加载所有插件（entry_points + 本地目录）"""
        self._load_plugins()
        self._load_local_plugins()
        self._load_channels()
        self._load_tools()
        self._load_core_tools()
        self._inject_sync_providers()

    async def load_all_async(self) -> None:
        """异步注册插件声明的权限和角色（在 load_all 之后调用）"""
        await self._load_channel_configs_from_db()
        await self._load_plugin_configs_from_db()
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

                # 判断来源：模块路径在 openvort 包内的是内置，否则是 pip 安装
                module = cls.__module__ or ""
                if module.startswith("openvort."):
                    plugin.source = "builtin"
                else:
                    plugin.source = "pip"

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
                    self.registry.register_prompt(prompt, source=f"plugin:{plugin.name}")

                log.info(
                    f"已加载 Plugin: {plugin.name} ({plugin.display_name}) "
                    f"— {len(tools)} 个 Tool, {len(prompts)} 条 Prompt"
                )
                self._plugins.append(plugin)
                self.registry.register_plugin(plugin)
            except Exception as e:
                log.error(f"加载 Plugin '{ep.name}' 失败: {e}")

    def _load_local_plugins(self) -> None:
        """从 ~/.openvort/plugins/ 扫描本地 Plugin"""
        from openvort.config.settings import get_settings

        plugins_dir = get_settings().data_dir / "plugins"
        if not plugins_dir.exists():
            return

        for plugin_dir in sorted(plugins_dir.iterdir()):
            if not plugin_dir.is_dir():
                continue
            plugin_py = plugin_dir / "plugin.py"
            if not plugin_py.exists():
                continue

            module_name = f"openvort_local_plugin_{plugin_dir.name}"
            try:
                spec = importlib.util.spec_from_file_location(module_name, plugin_py)
                if not spec or not spec.loader:
                    log.warning(f"无法加载本地 Plugin '{plugin_dir.name}'：无效的模块")
                    continue

                # Add plugin directory to sys.path so sub-modules (tools/, etc.) are importable
                plugin_dir_str = str(plugin_dir)
                if plugin_dir_str not in sys.path:
                    sys.path.insert(0, plugin_dir_str)

                module = importlib.util.module_from_spec(spec)
                sys.modules[module_name] = module
                spec.loader.exec_module(module)

                # 在模块中查找 BasePlugin 子类
                plugin_cls = None
                for _, obj in inspect.getmembers(module, inspect.isclass):
                    if issubclass(obj, BasePlugin) and obj is not BasePlugin:
                        plugin_cls = obj
                        break

                if not plugin_cls:
                    log.warning(f"本地 Plugin '{plugin_dir.name}' 中未找到 BasePlugin 子类，跳过")
                    continue

                plugin = plugin_cls()
                plugin.source = "local"

                if not plugin.validate_credentials():
                    log.warning(f"本地 Plugin '{plugin.name}' 凭证校验失败，跳过")
                    continue

                tools = plugin.get_tools()
                for tool in tools:
                    self.registry.register_tool(tool)

                prompts = plugin.get_prompts()
                for prompt in prompts:
                    self.registry.register_prompt(prompt, source=f"plugin:{plugin.name}")

                log.info(
                    f"已加载本地 Plugin: {plugin.name} ({plugin.display_name}) "
                    f"— {len(tools)} 个 Tool, {len(prompts)} 条 Prompt"
                )
                self._plugins.append(plugin)
                self.registry.register_plugin(plugin)
            except Exception as e:
                log.error(f"加载本地 Plugin '{plugin_dir.name}' 失败: {e}")

    def _load_channels(self) -> None:
        """从 entry_points 加载 Channel 插件，并兜底注册内置通道"""
        eps = entry_points()
        channel_eps = eps.select(group="openvort.channels") if hasattr(eps, "select") else eps.get("openvort.channels", [])

        for ep in channel_eps:
            try:
                cls = ep.load()
                if isinstance(cls, type) and issubclass(cls, BaseChannel):
                    instance = cls()
                    self.registry.register_channel(instance)
                    # 注册 Channel 提供的工具
                    self._register_channel_tools(instance)
                else:
                    log.warning(f"Channel entry_point '{ep.name}' 不是 BaseChannel 子类，跳过")
            except Exception as e:
                log.error(f"加载 Channel '{ep.name}' 失败: {e}")

        # 某些开发环境未执行 editable install 时，entry_points 可能不完整。
        # 这里兜底确保内置通道都能在管理后台可见。
        self._load_builtin_channels_fallback()

    def _load_builtin_channels_fallback(self) -> None:
        """兜底加载内置 Channel（wecom/dingtalk/feishu）"""
        builtin_channels = [
            ("wecom", "openvort.channels.wecom", "WeComChannel"),
            ("dingtalk", "openvort.channels.dingtalk", "DingTalkChannel"),
            ("feishu", "openvort.channels.feishu", "FeishuChannel"),
            ("openclaw", "openvort.channels.openclaw", "OpenClawChannel"),
        ]

        for channel_name, module_name, class_name in builtin_channels:
            if self.registry.get_channel(channel_name):
                continue
            try:
                module = __import__(module_name, fromlist=[class_name])
                cls = getattr(module, class_name)
                if not (isinstance(cls, type) and issubclass(cls, BaseChannel)):
                    log.warning(f"内置 Channel '{channel_name}' 类型异常，跳过")
                    continue
                instance = cls()
                self.registry.register_channel(instance)
                self._register_channel_tools(instance)
                log.info(f"已通过兜底逻辑加载内置 Channel: {channel_name}")
            except Exception as e:
                log.warning(f"兜底加载内置 Channel '{channel_name}' 失败: {e}")

    def _register_channel_tools(self, channel: BaseChannel) -> None:
        """注册 Channel 附带的工具（如企微发消息）"""
        if channel.name == "wecom":
            try:
                from openvort.channels.wecom.tools import SendWeComMessageTool, SendWeComVoiceTool
                tool = SendWeComMessageTool(channel=channel)
                self.registry.register_tool(tool)
                log.info(f"已注册 Channel 工具: {tool.name}")
                voice_tool = SendWeComVoiceTool(channel=channel)
                self.registry.register_tool(voice_tool)
                log.info(f"已注册 Channel 工具: {voice_tool.name}")
            except Exception as e:
                log.error(f"注册企微 Channel 工具失败: {e}")
        elif channel.name == "feishu":
            try:
                from openvort.channels.feishu.tools import SendFeishuMessageTool, SendFeishuVoiceTool

                tool = SendFeishuMessageTool(channel=channel)
                self.registry.register_tool(tool)
                log.info(f"已注册 Channel 工具: {tool.name}")
                voice_tool = SendFeishuVoiceTool(channel=channel)
                self.registry.register_tool(voice_tool)
                log.info(f"已注册 Channel 工具: {voice_tool.name}")
            except Exception as e:
                log.error(f"注册飞书 Channel 工具失败: {e}")
        elif channel.name == "dingtalk":
            try:
                from openvort.channels.dingtalk.tools import SendDingTalkMessageTool, SendDingTalkVoiceTool

                tool = SendDingTalkMessageTool(channel=channel)
                self.registry.register_tool(tool)
                log.info(f"已注册 Channel 工具: {tool.name}")
                voice_tool = SendDingTalkVoiceTool(channel=channel)
                self.registry.register_tool(voice_tool)
                log.info(f"已注册 Channel 工具: {voice_tool.name}")
            except Exception as e:
                log.error(f"注册钉钉 Channel 工具失败: {e}")

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

    def _load_core_tools(self) -> None:
        """Register core infrastructure tools (remote work, etc.)."""
        try:
            from openvort.core.remote_work_tool import get_remote_work_tools
            for tool in get_remote_work_tools():
                self.registry.register_tool(tool)
        except Exception as e:
            log.warning(f"加载远程工作核心工具失败: {e}")

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

    async def _load_channel_configs_from_db(self) -> None:
        """从数据库加载 channel 配置，覆盖环境变量默认值"""
        try:
            import json
            from sqlalchemy import select
            from openvort.db.engine import get_session_factory
            from openvort.db.models import ChannelConfig

            session_factory = get_session_factory()
            async with session_factory() as session:
                result = await session.execute(select(ChannelConfig))
                rows = result.scalars().all()

            for row in rows:
                ch = self.registry.get_channel(row.channel_name)
                if ch and row.config_data:
                    config = json.loads(row.config_data)
                    if config:
                        ch.apply_config(config)
                        log.info(f"从数据库加载 Channel 配置: {row.channel_name}")
        except Exception as e:
            log.warning(f"从数据库加载 Channel 配置失败（将使用环境变量）: {e}")

    async def _load_plugin_configs_from_db(self) -> None:
        """从数据库加载 plugin 配置，覆盖环境变量默认值，处理启用/禁用"""
        try:
            import json
            from sqlalchemy import select
            from openvort.db.engine import get_session_factory
            from openvort.db.models import PluginConfig

            session_factory = get_session_factory()
            async with session_factory() as session:
                result = await session.execute(select(PluginConfig))
                rows = result.scalars().all()

            for row in rows:
                plugin = self.registry.get_plugin(row.plugin_name)
                if not plugin:
                    continue

                # 核心插件不可禁用
                if not row.enabled and not plugin.core:
                    self.registry.disable_plugin(row.plugin_name)
                    log.info(f"Plugin '{row.plugin_name}' 已禁用")
                    continue

                # 应用 DB 中保存的配置
                if row.config_data:
                    config = json.loads(row.config_data)
                    if config:
                        plugin.apply_config(config)
                        log.info(f"从数据库加载 Plugin 配置: {row.plugin_name}")
        except Exception as e:
            log.warning(f"从数据库加载 Plugin 配置失败（将使用环境变量）: {e}")

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
