"""
IM 聊天命令

在 IM 通道中支持 / 前缀命令，拦截后直接处理，不进入 Agent loop。
支持: /new /status /compact /think /usage
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from openvort.utils.logging import get_logger

if TYPE_CHECKING:
    from openvort.core.session import SessionStore
    from openvort.core.llm import LLMClient

log = get_logger("core.commands")


@dataclass
class CommandResult:
    """命令执行结果"""
    handled: bool = False  # 是否被命令处理（True 则不进入 Agent）
    reply: str = ""  # 回复文本


class CommandHandler:
    """IM 命令处理器

    在消息进入 Agent 前拦截 / 前缀命令。
    """

    def __init__(self, session_store: SessionStore, llm_client: LLMClient | None = None,
                 model_name: str = "", group_activation=None):
        self._sessions = session_store
        self._llm = llm_client
        self._model_name = model_name
        self._group_activation = group_activation

    async def handle(self, channel: str, user_id: str, content: str) -> CommandResult:
        """尝试处理命令，返回 CommandResult

        Args:
            channel: 渠道
            user_id: 用户 ID
            content: 原始消息内容

        Returns:
            CommandResult: handled=True 表示已处理，reply 为回复文本
        """
        text = content.strip()
        if not text.startswith("/"):
            return CommandResult(handled=False)

        parts = text.split(maxsplit=1)
        cmd = parts[0].lower()
        arg = parts[1].strip() if len(parts) > 1 else ""

        handler = self._commands.get(cmd)
        if not handler:
            return CommandResult(handled=False)

        try:
            reply = await handler(self, channel, user_id, arg)
            return CommandResult(handled=True, reply=reply)
        except Exception as e:
            log.error(f"命令 {cmd} 执行失败: {e}")
            return CommandResult(handled=True, reply=f"命令执行失败: {e}")

    # ---- 命令实现 ----

    async def _cmd_new(self, channel: str, user_id: str, arg: str) -> str:
        """重置会话"""
        await self._sessions.clear(channel, user_id)
        return "✅ 会话已重置"

    async def _cmd_status(self, channel: str, user_id: str, arg: str) -> str:
        """显示会话状态"""
        info = self._sessions.get_session_info(channel, user_id)
        if not info.get("exists"):
            return f"📊 模型: {self._model_name}\n当前无活跃会话"

        thinking = info.get("thinking_level") or "off"
        usage_mode = info.get("usage_mode", "off")
        lines = [
            f"📊 会话状态",
            f"模型: {self._model_name}",
            f"消息数: {info['message_count']}",
            f"思考级别: {thinking}",
            f"用量显示: {usage_mode}",
            f"累计 Token: ↑{info.get('total_input_tokens', 0)} ↓{info.get('total_output_tokens', 0)}",
        ]
        return "\n".join(lines)

    async def _cmd_compact(self, channel: str, user_id: str, arg: str) -> str:
        """压缩会话上下文"""
        result = await self._sessions.compact(channel, user_id, llm_client=self._llm)
        return f"🗜️ {result}"

    async def _cmd_think(self, channel: str, user_id: str, arg: str) -> str:
        """设置思考级别"""
        valid_levels = {"off", "low", "medium", "high"}
        level = arg.lower() if arg else ""
        if level not in valid_levels:
            current = self._sessions.get_thinking_level(channel, user_id) or "off"
            return f"当前思考级别: {current}\n可选: off | low | medium | high\n用法: /think high"
        self._sessions.set_thinking_level(channel, user_id, level)
        return f"✅ 思考级别已设为: {level}"

    async def _cmd_usage(self, channel: str, user_id: str, arg: str) -> str:
        """设置用量显示模式"""
        valid_modes = {"off", "tokens", "full"}
        mode = arg.lower() if arg else ""
        if mode not in valid_modes:
            current = self._sessions.get_usage_mode(channel, user_id)
            return f"当前用量显示: {current}\n可选: off | tokens | full\n用法: /usage tokens"
        self._sessions.set_usage_mode(channel, user_id, mode)
        labels = {"off": "关闭", "tokens": "显示 Token 数", "full": "显示完整用量"}
        return f"✅ 用量显示已设为: {labels[mode]}"

    async def _cmd_help(self, channel: str, user_id: str, arg: str) -> str:
        """显示帮助"""
        return (
            "📋 可用命令:\n"
            "/new — 重置会话\n"
            "/status — 查看会话状态\n"
            "/compact — 压缩上下文\n"
            "/think <off|low|medium|high> — 设置思考级别\n"
            "/usage <off|tokens|full> — 设置用量显示\n"
            "/activation <mention|always> — 群聊激活模式\n"
            "/help — 显示此帮助"
        )

    async def _cmd_activation(self, channel: str, user_id: str, arg: str) -> str:
        """设置群聊激活模式"""
        valid_modes = {"mention", "always"}
        mode = arg.lower() if arg else ""
        if mode not in valid_modes:
            return "群聊激活模式:\n  mention — 被 @mention 时响应\n  always — 响应所有消息\n用法: /activation mention"
        # 通过 group_activation 控制器设置（需要外部注入）
        if self._group_activation:
            # 用 channel:user_id 作为 group_id（实际群聊场景中应传入真实 group_id）
            self._group_activation.set_mode(f"{channel}:{user_id}", mode)
        return f"✅ 群聊激活模式已设为: {mode}"

    # 命令路由表
    _commands = {
        "/new": _cmd_new,
        "/reset": _cmd_new,
        "/status": _cmd_status,
        "/compact": _cmd_compact,
        "/think": _cmd_think,
        "/usage": _cmd_usage,
        "/activation": _cmd_activation,
        "/help": _cmd_help,
    }
