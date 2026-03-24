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
        self._prompts: list[tuple[str, str]] = []  # (source, content)
        self._plugins: dict[str, "BasePlugin"] = {}
        self._disabled: set[str] = set()
        self._slots: dict[str, object] = {}

    # ---- Slot management ----

    def register_slot(self, name: str, provider: object) -> None:
        if name in self._slots:
            log.warning(f"Slot '{name}' already registered, overwriting")
        self._slots[name] = provider
        log.debug(f"Slot registered: {name}")

    def get_slot(self, name: str) -> object | None:
        return self._slots.get(name)

    # ---- Plugin 管理 ----

    def register_plugin(self, plugin: "BasePlugin") -> None:
        """注册一个 Plugin 实例"""
        from openvort.plugin.base import BasePlugin
        if not isinstance(plugin, BasePlugin):
            return
        self._plugins[plugin.name] = plugin
        log.debug(f"已注册 Plugin: {plugin.name}")

    def get_plugin(self, name: str) -> "BasePlugin | None":
        """获取指定 Plugin"""
        return self._plugins.get(name)

    def list_plugins(self) -> list["BasePlugin"]:
        """列出所有已注册的 Plugin"""
        return list(self._plugins.values())

    def disable_plugin(self, name: str) -> None:
        """禁用插件：移除 Tools 和 Prompts，但保留 Plugin 对象在注册中心（管理面板可见）"""
        plugin = self._plugins.get(name)
        if not plugin:
            return
        tool_names = [t.name for t in plugin.get_tools()]
        for tn in tool_names:
            self._tools.pop(tn, None)
        self._prompts = [(s, c) for s, c in self._prompts if s != f"plugin:{name}"]
        self._disabled.add(name)
        log.debug(f"已禁用 Plugin: {name}（移除 {len(tool_names)} 个 Tool）")

    def enable_plugin(self, name: str) -> None:
        """启用插件：重新注册 Tools 和 Prompts"""
        plugin = self._plugins.get(name)
        if not plugin:
            return
        for tool in plugin.get_tools():
            self.register_tool(tool)
        for prompt in plugin.get_prompts():
            self.register_prompt(prompt, source=f"plugin:{name}")
        self._disabled.discard(name)
        log.debug(f"已启用 Plugin: {name}")

    def is_plugin_disabled(self, name: str) -> bool:
        return name in self._disabled

    def unregister_plugin(self, name: str) -> None:
        """完全注销一个 Plugin 及其 Tools 和 Prompts（删除插件时使用）"""
        plugin = self._plugins.pop(name, None)
        if not plugin:
            return
        tool_names = [t.name for t in plugin.get_tools()]
        for tn in tool_names:
            self._tools.pop(tn, None)
        self._prompts = [(s, c) for s, c in self._prompts if s != f"plugin:{name}"]
        self._disabled.discard(name)
        log.info(f"已注销 Plugin: {name}（移除 {len(tool_names)} 个 Tool）")

    # ---- Channel 管理 ----

    def register_channel(self, channel: BaseChannel) -> None:
        """注册一个 Channel"""
        if channel.name in self._channels:
            log.warning(f"Channel '{channel.name}' 已存在，将被覆盖")
        self._channels[channel.name] = channel
        log.debug(f"已注册 Channel: {channel.name} ({channel.display_name})")

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
        log.debug(f"已注册 Tool: {tool.name}")

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

    # ---- Prompt 管理（插件领域知识 + Skill）----

    def register_prompt(self, prompt: str, source: str = "") -> None:
        """注册一条领域知识 prompt（带来源标记）"""
        self._prompts.append((source, prompt))

    def unregister_prompt(self, source: str) -> None:
        """移除指定来源的所有 prompt"""
        self._prompts = [(s, p) for s, p in self._prompts if s != source]

    def get_system_prompt_extension(self) -> str:
        """拼接所有领域知识，按来源分节输出"""
        if not self._prompts:
            return ""

        plugin_parts = []
        skill_parts = []
        for source, content in self._prompts:
            if source.startswith("plugin:"):
                plugin_parts.append(content)
            else:
                skill_parts.append(content)

        sections = []
        if plugin_parts:
            sections.append("## 插件能力\n\n" + "\n\n".join(plugin_parts))
        if skill_parts:
            sections.append("## 技能知识\n\n" + "\n\n".join(skill_parts))
        return "\n\n".join(sections)
