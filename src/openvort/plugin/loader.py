"""
插件加载器

通过 Python entry_points 自动发现并加载 Plugin、Channel 和 Tool。
"""

import importlib.util
import inspect
import json
import sys
from importlib.metadata import entry_points
from pathlib import Path

from openvort.plugin.base import BaseChannel, BasePlugin, BaseTool
from openvort.plugin.registry import PluginRegistry
from openvort.utils.logging import get_logger

log = get_logger("plugin.loader")


class _ManifestPlugin(BasePlugin):
    """Lightweight plugin created from a manifest.json + SKILL.md bundle
    (no plugin.py). Used for marketplace knowledge/skill packages installed
    via the plugin path."""

    def __init__(self, *, name: str, display_name: str, description: str,
                 version: str, prompts: list[str], manifest: dict,
                 readme: str = "", plugin_dir: Path | None = None):
        self.name = name
        self.display_name = display_name
        self.description = description
        self.version = version
        self._prompts = prompts
        self.manifest = manifest
        self.readme = readme
        self.plugin_dir = plugin_dir

    def get_tools(self) -> list[BaseTool]:
        return []

    def get_prompts(self) -> list[str]:
        return self._prompts

    def get_extended_meta(self) -> dict:
        return {
            "tags": self.manifest.get("tags", []),
            "author": self.manifest.get("author", ""),
            "homepage": self.manifest.get("homepage", ""),
            "repository": self.manifest.get("repository", ""),
            "license": self.manifest.get("license", ""),
            "category": self.manifest.get("category", ""),
            "readme": self.readme,
            "prompts_count": len(self._prompts),
        }


class PluginLoader:
    """插件加载器"""

    def __init__(self, registry: PluginRegistry, auth_service=None):
        self.registry = registry
        self._plugins: list[BasePlugin] = []
        self._auth = auth_service
        self._api: "PluginAPI | None" = None

    @property
    def api(self) -> "PluginAPI":
        if self._api is None:
            from openvort.core.events import event_bus
            from openvort.plugin.api import PluginAPI
            self._api = PluginAPI(
                registry=self.registry,
                event_bus=event_bus,
            )
        return self._api

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
                    log.warning(f"Plugin '{plugin.name}' 凭证校验失败，跳过工具注册（请检查配置）")
                    self._plugins.append(plugin)
                    self.registry.register_plugin(plugin)
                    self.registry.disable_plugin(plugin.name)
                    continue

                # Call activate(api) — new plugins override this to register
                # tools/prompts/slots via the PluginAPI directly.
                # The default BasePlugin.activate() delegates to get_tools()/get_prompts().
                plugin.activate(self.api)

                # Load skills bundled with the plugin
                module_file = inspect.getfile(cls)
                if module_file:
                    self._load_plugin_skills(Path(module_file).parent, plugin.name)

                tools = plugin.get_tools()
                prompts = plugin.get_prompts()
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

        scan_dirs = [plugins_dir]
        marketplace_dir = plugins_dir / "local"
        if marketplace_dir.exists() and marketplace_dir.is_dir():
            scan_dirs.append(marketplace_dir)

        seen: set[str] = set()
        for scan_dir in scan_dirs:
            for plugin_dir in sorted(scan_dir.iterdir()):
                if not plugin_dir.is_dir():
                    continue

                dir_key = str(plugin_dir.resolve())
                if dir_key in seen:
                    continue
                seen.add(dir_key)

                plugin_py = plugin_dir / "plugin.py"
                if plugin_py.exists():
                    self._load_single_local_plugin(plugin_dir)
                elif (plugin_dir / "manifest.json").exists():
                    self._load_manifest_plugin(plugin_dir)

    def _load_manifest_plugin(self, plugin_dir: Path) -> None:
        """Load a marketplace bundle that has manifest.json + SKILL.md but no plugin.py."""
        manifest_path = plugin_dir / "manifest.json"
        try:
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        except Exception as e:
            log.warning(f"读取 manifest.json 失败 '{plugin_dir.name}': {e}")
            return

        slug = manifest.get("slug", plugin_dir.name)
        display_name = manifest.get("displayName") or manifest.get("name") or slug
        description = manifest.get("description", "")
        version = manifest.get("version", "1.0.0")

        prompts: list[str] = []
        skill_md = plugin_dir / "SKILL.md"
        if skill_md.exists():
            try:
                content = skill_md.read_text(encoding="utf-8")
                if content.strip():
                    prompts.append(content)
            except Exception as e:
                log.warning(f"读取 SKILL.md 失败 '{plugin_dir.name}': {e}")

        readme = ""
        readme_path = plugin_dir / "README.md"
        if readme_path.exists():
            try:
                readme = readme_path.read_text(encoding="utf-8")
            except Exception:
                pass

        plugin = _ManifestPlugin(
            name=slug,
            display_name=display_name,
            description=description,
            version=version,
            prompts=prompts,
            manifest=manifest,
            readme=readme,
            plugin_dir=plugin_dir,
        )
        plugin.source = "local"

        plugin.activate(self.api)

        log.info(
            f"已加载 Manifest Plugin: {plugin.name} ({plugin.display_name}) "
            f"— {len(prompts)} 条 Prompt"
        )
        self._plugins.append(plugin)
        self.registry.register_plugin(plugin)

    def _load_single_local_plugin(self, plugin_dir: Path) -> None:
        """Load a single local plugin from the given directory."""
        plugin_py = plugin_dir / "plugin.py"
        module_name = f"openvort_local_plugin_{plugin_dir.name}"
        try:
            spec = importlib.util.spec_from_file_location(module_name, plugin_py)
            if not spec or not spec.loader:
                log.warning(f"无法加载本地 Plugin '{plugin_dir.name}'：无效的模块")
                return

            plugin_dir_str = str(plugin_dir)
            if plugin_dir_str not in sys.path:
                sys.path.insert(0, plugin_dir_str)

            module = importlib.util.module_from_spec(spec)
            sys.modules[module_name] = module
            spec.loader.exec_module(module)

            plugin_cls = None
            for _, obj in inspect.getmembers(module, inspect.isclass):
                if issubclass(obj, BasePlugin) and obj is not BasePlugin:
                    plugin_cls = obj
                    break

            if not plugin_cls:
                log.warning(f"本地 Plugin '{plugin_dir.name}' 中未找到 BasePlugin 子类，跳过")
                return

            plugin = plugin_cls()
            plugin.source = "local"

            if not plugin.validate_credentials():
                log.warning(f"本地 Plugin '{plugin.name}' 凭证校验失败，跳过工具注册")
                self._plugins.append(plugin)
                self.registry.register_plugin(plugin)
                self.registry.disable_plugin(plugin.name)
                return

            plugin.activate(self.api)

            self._load_plugin_skills(plugin_dir, plugin.name)

            tools = plugin.get_tools()
            prompts = plugin.get_prompts()
            log.info(
                f"已加载本地 Plugin: {plugin.name} ({plugin.display_name}) "
                f"— {len(tools)} 个 Tool, {len(prompts)} 条 Prompt"
            )
            self._plugins.append(plugin)
            self.registry.register_plugin(plugin)
        except Exception as e:
            log.error(f"加载本地 Plugin '{plugin_dir.name}' 失败: {e}")

    def _load_plugin_skills(self, plugin_dir: Path, plugin_name: str) -> None:
        """Load SKILL.md files bundled inside a plugin's skills/ directory."""
        skills_dir = plugin_dir / "skills"
        if not skills_dir.exists() or not skills_dir.is_dir():
            return

        from openvort.skill.loader import _parse_skill_file, _apply_content_template

        count = 0
        for skill_subdir in sorted(skills_dir.iterdir()):
            if not skill_subdir.is_dir():
                continue
            skill_file = skill_subdir / "SKILL.md"
            if not skill_file.exists():
                continue
            parsed = _parse_skill_file(skill_file)
            if parsed and parsed["enabled"] and parsed["content"]:
                content = _apply_content_template(parsed["content"], skill_subdir)
                self.registry.register_prompt(content, source=f"plugin:{plugin_name}")
                count += 1

        if count:
            log.info(f"从 Plugin '{plugin_name}' 加载了 {count} 个 Skills")

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
                log.debug(f"已通过兜底逻辑加载内置 Channel: {channel_name}")
            except Exception as e:
                log.warning(f"兜底加载内置 Channel '{channel_name}' 失败: {e}")

    def _register_channel_tools(self, channel: BaseChannel) -> None:
        """注册 Channel 附带的工具（如企微发消息）"""
        if channel.name == "wecom":
            try:
                from openvort.channels.wecom.tools import SendWeComMessageTool, SendWeComVoiceTool
                tool = SendWeComMessageTool(channel=channel)
                self.registry.register_tool(tool)
                voice_tool = SendWeComVoiceTool(channel=channel)
                self.registry.register_tool(voice_tool)
            except Exception as e:
                log.error(f"注册企微 Channel 工具失败: {e}")
        elif channel.name == "feishu":
            try:
                from openvort.channels.feishu.tools import SendFeishuMessageTool, SendFeishuVoiceTool

                tool = SendFeishuMessageTool(channel=channel)
                self.registry.register_tool(tool)
                voice_tool = SendFeishuVoiceTool(channel=channel)
                self.registry.register_tool(voice_tool)
            except Exception as e:
                log.error(f"注册飞书 Channel 工具失败: {e}")
        elif channel.name == "dingtalk":
            try:
                from openvort.channels.dingtalk.tools import SendDingTalkMessageTool, SendDingTalkVoiceTool

                tool = SendDingTalkMessageTool(channel=channel)
                self.registry.register_tool(tool)
                voice_tool = SendDingTalkVoiceTool(channel=channel)
                self.registry.register_tool(voice_tool)
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
        """Register core infrastructure tools (node tools, etc.)."""
        try:
            from openvort.core.execution.node_tools import get_node_tools
            for tool in get_node_tools():
                self.registry.register_tool(tool)
        except Exception as e:
            log.warning(f"加载节点核心工具失败: {e}")

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
                        log.debug(f"从数据库加载 Channel 配置: {row.channel_name}")
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
                    log.debug(f"Plugin '{row.plugin_name}' 已禁用")
                    continue

                if row.config_data:
                    config = json.loads(row.config_data)
                    if config:
                        plugin.apply_config(config)
                        log.debug(f"从数据库加载 Plugin 配置: {row.plugin_name}")

                if row.enabled and self.registry.is_plugin_disabled(row.plugin_name):
                    if plugin.validate_credentials():
                        self.registry.enable_plugin(row.plugin_name)
                        log.debug(f"Plugin '{row.plugin_name}' 在应用 DB 配置后已启用")
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

        log.debug("插件权限和角色注册完成")
