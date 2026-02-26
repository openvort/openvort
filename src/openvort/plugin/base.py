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
    raw: dict = field(default_factory=dict)  # 原始数据，Channel 特有字段


# 消息处理回调类型
MessageHandler = Callable[[Message], Coroutine[Any, Any, str | None]]


# ============ Channel 基类 ============


class BaseChannel(ABC):
    """IM 通道适配器基类

    每个 Channel 负责：
    - 接收消息（轮询 / Webhook）
    - 发送消息（调用 IM 平台 API）
    - 消息格式转换（平台格式 ↔ 统一 Message）
    """

    name: str = ""  # 通道标识，如 "wecom", "dingtalk", "feishu"
    display_name: str = ""  # 显示名称，如 "企业微信"

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
