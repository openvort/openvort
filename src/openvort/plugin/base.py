"""
插件基类

定义 Channel（IM 通道）和 Tool（AI 工具）的标准接口。
第三方插件只需继承基类并实现抽象方法。
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Callable, Coroutine

if TYPE_CHECKING:
    from openvort.contacts.sync import ContactSyncProvider
    from openvort.plugin.api import PluginAPI

# ============ 消息模型 ============


@dataclass
class Message:
    """统一消息格式，跨 Channel 通用"""

    content: str
    sender_id: str = ""
    sender_name: str = ""
    channel: str = ""
    msg_type: str = "text"  # text, image, voice, file, ...
    images: list[dict] = field(default_factory=list)
    voice_media_ids: list[str] = field(default_factory=list)  # 语音消息的 media_id 列表
    raw: dict = field(default_factory=dict)  # 原始数据，Channel 特有字段


# 消息处理回调类型
MessageHandler = Callable[[Message], Coroutine[Any, Any, str | None]]


# ============ Channel 基类 ============


class BaseChannel(ABC):
    """IM 通道适配器基类

    每个 Channel 负责：
    - 接收消息（长连接 / Webhook）
    - 发送消息（调用 IM 平台 API）
    - 消息格式转换（平台格式 ↔ 统一 Message）
    """

    name: str = ""  # 通道标识，如 "wecom", "dingtalk", "feishu"
    display_name: str = ""  # 显示名称，如 "企业微信"
    description: str = ""  # 功能简述，一句话概括通道能力

    @abstractmethod
    async def start(self) -> None:
        """启动通道（开始接收消息）"""
        ...

    @abstractmethod
    async def stop(self) -> None:
        """停止通道"""
        ...

    @abstractmethod
    async def send(self, target: str, message: Message) -> None:
        """发送消息到指定目标（用户/群）"""
        ...

    @abstractmethod
    def on_message(self, handler: MessageHandler) -> None:
        """注册消息回调，收到消息时调用 handler"""
        ...

    def is_configured(self) -> bool:
        """检查通道是否已配置（子类可覆盖）"""
        return True

    def get_sync_provider(self) -> "ContactSyncProvider | None":
        """返回通讯录同步提供者（可选）

        Channel 可实现此方法，提供从 IM 平台同步通讯录的能力。
        """
        return None

    def get_channel_prompt(self) -> str:
        """返回渠道特有的 prompt 片段（回复风格、格式约束）

        Channel 可覆盖此方法，提供差异化的 AI 回复风格。
        """
        return ""

    def get_tool_filter(self) -> list[str] | None:
        """返回该渠道允许使用的 Tool 名称列表

        返回 None 表示不限制（所有 Tool 可用）。
        """
        return None

    def get_max_reply_length(self) -> int:
        """回复长度限制（字符数），0 表示不限制"""
        return 0

    # ---- 配置管理接口 ----

    def get_config_schema(self) -> list[dict]:
        """返回配置字段定义，用于前端动态渲染表单

        每个字段支持:
          key, label, type, required, secret, placeholder, description, help_url

        返回: [{"key": "corp_id", "label": "企业ID", "type": "string",
                "required": True, "secret": False, "placeholder": "",
                "description": "在企微管理后台 > 我的企业 中获取"}, ...]
        """
        return []

    def get_setup_guide(self) -> str:
        """返回 markdown 格式的配置指南

        用于前端配置抽屉顶部展示，引导用户完成通道配置。
        子类应覆盖此方法，提供从平台获取凭证的步骤说明。
        """
        return ""

    def get_current_config(self) -> dict:
        """返回当前配置值（secret 字段脱敏显示）"""
        return {}

    def apply_config(self, config: dict) -> None:
        """应用新配置（运行时生效），子类实现具体逻辑"""
        pass

    async def test_connection(self) -> dict:
        """测试通道连通性

        返回: {"ok": True/False, "message": "..."}
        """
        if self.is_configured():
            return {"ok": True, "message": "通道已配置"}
        return {"ok": False, "message": "通道未配置"}

    def get_connection_info(self) -> dict:
        """返回当前连接模式信息（只读展示用）

        返回: {"mode": "webhook"} 等
        """
        return {"mode": "unknown"}


# ============ Tool 基类 ============


class BaseTool(ABC):
    """AI 工具基类

    每个 Tool 自动注册为 Claude tool use 的可用工具。
    Agent 根据用户意图自主决定调用哪些工具。
    """

    name: str = ""  # 工具标识，如 "zentao.create_bug"
    description: str = ""  # 工具描述（给 LLM 看，影响调用决策）
    required_permission: str = ""  # 所需权限码，空字符串表示无需权限

    @abstractmethod
    def input_schema(self) -> dict:
        """返回 JSON Schema，定义工具的输入参数"""
        ...

    @abstractmethod
    async def execute(self, params: dict) -> str:
        """执行工具，返回结果文本（给 LLM 看）"""
        ...

    def to_claude_tool(self) -> dict:
        """转换为 Claude tool use 格式"""
        return {
            "name": self.name,
            "description": self.description,
            "input_schema": self.input_schema(),
        }


# ============ Plugin 基类 ============


class BasePlugin(ABC):
    """插件基类 — Plugin 是 Tool + Prompt + Config 的容器

    参考 Dify Provider + Semantic Kernel Plugin 设计：
    - 一个 Plugin 包含一组相关的 Tool（如禅道的任务/Bug/需求操作）
    - 可包含领域知识 Prompt（自动注入 Agent system prompt）
    - 统一管理凭证/配置校验

    第三方插件通过 pyproject.toml entry_points 注册：
        [project.entry-points."openvort.plugins"]
        zentao = "openvort_zentao:ZentaoPlugin"
    """

    name: str = ""                # 插件标识，如 "zentao", "gitee", "jenkins"
    display_name: str = ""        # 显示名称，如 "禅道项目管理"
    description: str = ""         # 插件描述
    version: str = "0.1.0"
    source: str = "builtin"       # 来源: "builtin" | "pip" | "local"
    core: bool = False            # 核心插件不可禁用

    def activate(self, api: "PluginAPI") -> None:
        """Register all capabilities via the PluginAPI.

        Default implementation delegates to the legacy get_tools() / get_prompts()
        methods for backward compatibility.  New plugins should override this
        and call api.register_tool() / api.register_prompt() / api.register_slot()
        directly.
        """
        for tool in self.get_tools():
            api.register_tool(tool)
        for prompt in self.get_prompts():
            api.register_prompt(prompt, source=f"plugin:{self.name}")

    @abstractmethod
    def get_tools(self) -> list[BaseTool]:
        """返回插件提供的所有 Tool 实例"""
        ...

    def get_prompts(self) -> list[str]:
        """返回插件的领域知识 prompt 列表（可选）

        每个 prompt 是一段 markdown 文本，会被自动追加到 Agent 的 system prompt 中，
        让 Agent 具备该插件领域的业务知识和流程规则。
        """
        return []

    def validate_credentials(self) -> bool:
        """校验插件凭证/配置是否有效（可选）

        返回 False 时插件不会被加载，其 Tools 和 Prompts 不会注册。
        """
        return True

    def get_sync_provider(self) -> "ContactSyncProvider | None":
        """返回通讯录同步提供者（可选）

        Plugin 可实现此方法，提供从外部系统同步通讯录的能力。
        """
        return None

    def get_permissions(self) -> list[dict]:
        """声明插件提供的权限列表（可选）

        返回: [{"code": "zentao.create_task", "display_name": "创建禅道任务"}, ...]
        """
        return []

    def get_roles(self) -> list[dict]:
        """声明插件提供的自定义角色（可选）

        返回: [{"name": "zentao_pm", "display_name": "禅道项目经理",
                "permissions": ["zentao.create_task", "zentao.view_task"]}]
        """
        return []

    # ---- 配置管理接口 ----

    def get_config_schema(self) -> list[dict]:
        """返回配置字段定义，用于前端动态渲染表单

        返回: [{"key": "host", "label": "数据库地址", "type": "string",
                "required": True, "secret": False, "placeholder": "127.0.0.1"}, ...]
        """
        return []

    def get_personal_config_schema(self) -> list[dict]:
        """返回个人级配置字段定义（每位成员独立配置）

        格式同 get_config_schema()。常用于个人 API Key / Token 等凭证。
        前端会在「个人设置 → 插件配置」中渲染表单。
        """
        return []

    def get_current_config(self) -> dict:
        """返回当前配置值（secret 字段脱敏显示）"""
        return {}

    def apply_config(self, config: dict) -> None:
        """应用新配置（运行时生效），子类实现具体逻辑"""
        pass

    # ---- UI 扩展与 API 路由 ----

    def get_ui_extensions(self) -> dict | None:
        """声明插件的 UI 扩展（菜单、路由、Dashboard widget 等）

        返回 None 表示该插件无 UI。
        """
        return None

    def get_api_router(self) -> Any:
        """返回插件的 FastAPI sub-router，由宿主动态挂载

        返回 None 表示该插件无独立 API。
        """
        return None

    # ---- 插件引导接口 ----

    def get_platform(self) -> str:
        """返回插件关联的平台标识（如 "zentao"、"gitee"）

        用于与 PlatformIdentity 表关联，判断用户是否已绑定该平台身份。
        返回空字符串表示该插件不关联特定平台。
        """
        return ""

    async def get_setup_status(self, ctx: Any) -> str:
        """检查插件对当前用户的就绪状态

        Args:
            ctx: RequestContext，包含 member、platform_accounts 等

        Returns:
            "ready"      — 插件已就绪，用户已关联
            "not_synced" — 该平台通讯录尚未同步
            "not_bound"  — 通讯录已同步但当前用户未关联该平台身份
        """
        return "ready"

    def get_onboarding_prompt(self, status: str, is_admin: bool) -> str:
        """根据就绪状态和用户角色返回引导 prompt

        Args:
            status: get_setup_status 返回的状态
            is_admin: 当前用户是否为管理员

        Returns:
            引导 prompt 文本，注入到 Agent system prompt 中
        """
        return ""
