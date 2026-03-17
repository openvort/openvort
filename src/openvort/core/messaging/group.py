"""
群聊激活模式

控制 Bot 在群聊中的响应策略：
- mention: 只在被 @mention 时响应（默认）
- always: 响应所有消息
"""

from __future__ import annotations

from dataclasses import dataclass

from openvort.utils.logging import get_logger

log = get_logger("core.group")


@dataclass
class GroupActivationConfig:
    """群聊激活配置"""
    # 全局默认模式
    default_mode: str = "mention"  # mention | always
    # 按群组 ID 覆盖
    overrides: dict[str, str] | None = None  # {group_id: mode}


class GroupActivation:
    """群聊激活控制器

    判断群聊消息是否应该被 Bot 处理。
    """

    def __init__(self, config: GroupActivationConfig | None = None):
        self._config = config or GroupActivationConfig()
        # 运行时覆盖（通过 /activation 命令设置）
        self._runtime_overrides: dict[str, str] = {}

    def should_respond(self, group_id: str, content: str, is_mentioned: bool) -> bool:
        """判断是否应该响应群聊消息

        Args:
            group_id: 群组 ID
            content: 消息内容
            is_mentioned: 是否被 @mention

        Returns:
            True 表示应该响应
        """
        mode = self.get_mode(group_id)

        if mode == "always":
            return True

        # mention 模式：只在被 @ 时响应
        if mode == "mention":
            return is_mentioned

        return is_mentioned

    def get_mode(self, group_id: str) -> str:
        """获取指定群组的激活模式"""
        # 优先级：运行时覆盖 > 配置覆盖 > 全局默认
        if group_id in self._runtime_overrides:
            return self._runtime_overrides[group_id]
        if self._config.overrides and group_id in self._config.overrides:
            return self._config.overrides[group_id]
        return self._config.default_mode

    def set_mode(self, group_id: str, mode: str) -> bool:
        """设置群组激活模式（运行时）

        Args:
            group_id: 群组 ID
            mode: mention | always

        Returns:
            是否设置成功
        """
        if mode not in ("mention", "always"):
            return False
        self._runtime_overrides[group_id] = mode
        log.info(f"群组 {group_id} 激活模式已设为: {mode}")
        return True

    @staticmethod
    def extract_mention(content: str, bot_name: str = "") -> tuple[bool, str]:
        """从消息内容中提取 @mention 信息

        Args:
            content: 原始消息内容
            bot_name: Bot 名称（用于匹配 @BotName）

        Returns:
            (is_mentioned, cleaned_content) — 是否被 @，以及去掉 @ 后的内容
        """
        import re

        # 通用 @mention 模式
        # 企微: @BotName 或 @所有人
        # 钉钉: @BotName
        # 飞书: @_user_1
        is_mentioned = False
        cleaned = content

        if bot_name:
            pattern = rf"@{re.escape(bot_name)}\s*"
            if re.search(pattern, content):
                is_mentioned = True
                cleaned = re.sub(pattern, "", content).strip()

        # 通用 @mention 标记（各平台 SDK 可能已标记）
        # 如果内容以 @ 开头，也视为 mention
        if not is_mentioned and content.strip().startswith("@"):
            is_mentioned = True

        return is_mentioned, cleaned
