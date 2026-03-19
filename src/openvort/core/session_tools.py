"""
Agent-to-Agent 通信工具

提供 sessions_list、sessions_send、sessions_history 三个 AI Tool，
允许 Agent 间跨 session 协作。
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from openvort.plugin.base import BaseTool
from openvort.utils.logging import get_logger

if TYPE_CHECKING:
    from openvort.core.engine.session import SessionStore
    from openvort.core.engine.agent import AgentRuntime

log = get_logger("core.session_tools")

# 全局引用（由 cli.py 启动时注入）
_session_store: SessionStore | None = None
_agent: AgentRuntime | None = None


def set_session_tools_runtime(session_store: SessionStore, agent: AgentRuntime) -> None:
    """注入运行时依赖"""
    global _session_store, _agent
    _session_store = session_store
    _agent = agent


class SessionsListTool(BaseTool):
    """列出活跃会话"""

    name = "sessions_list"
    description = "列出当前所有活跃的会话（Agent session），返回会话 ID、消息数、最后更新时间等信息。用于了解系统中有哪些正在进行的对话。"

    def input_schema(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "channel": {
                    "type": "string",
                    "description": "按通道过滤（可选，如 wecom/dingtalk/web），不填则返回全部",
                },
            },
            "required": [],
        }

    async def execute(self, params: dict) -> str:
        if not _session_store:
            return "会话服务未初始化"

        channel_filter = params.get("channel", "")
        sessions = []
        for key, session in _session_store._sessions.items():
            if channel_filter and session.channel != channel_filter:
                continue
            sessions.append({
                "key": key,
                "channel": session.channel,
                "user_id": session.user_id,
                "message_count": len(session.messages),
                "updated_at": session.updated_at,
                "thinking_level": session.thinking_level,
            })

        if not sessions:
            return "当前没有活跃会话"

        lines = [f"共 {len(sessions)} 个活跃会话:\n"]
        for s in sessions:
            lines.append(f"- {s['key']}: {s['message_count']} 条消息")
        return "\n".join(lines)


class SessionsHistoryTool(BaseTool):
    """查看指定会话的历史记录"""

    name = "sessions_history"
    description = "查看指定会话的对话历史记录。需要提供通道和用户 ID。返回最近的消息摘要。"

    def input_schema(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "channel": {
                    "type": "string",
                    "description": "通道名（如 wecom、web、cli）",
                },
                "user_id": {
                    "type": "string",
                    "description": "用户 ID",
                },
                "limit": {
                    "type": "integer",
                    "description": "返回最近多少条消息（默认 10）",
                },
            },
            "required": ["channel", "user_id"],
        }

    async def execute(self, params: dict) -> str:
        if not _session_store:
            return "会话服务未初始化"

        channel = params.get("channel", "")
        user_id = params.get("user_id", "")
        limit = params.get("limit", 10)

        if not channel or not user_id:
            return "请提供 channel 和 user_id"

        messages = await _session_store.get_messages(channel, user_id)
        if not messages:
            return f"会话 {channel}:{user_id} 没有历史记录"

        recent = messages[-limit:]
        lines = [f"会话 {channel}:{user_id} 最近 {len(recent)} 条消息:\n"]
        for msg in recent:
            role = msg.get("role", "?")
            content = msg.get("content", "")
            if isinstance(content, str):
                text = content[:150]
            elif isinstance(content, list):
                text_parts = []
                for block in content:
                    if isinstance(block, dict):
                        if block.get("type") == "text":
                            text_parts.append(block.get("text", "")[:100])
                        elif block.get("type") == "tool_use":
                            text_parts.append(f"[工具: {block.get('name', '')}]")
                        elif block.get("type") == "tool_result":
                            text_parts.append("[工具结果]")
                text = " ".join(text_parts)[:150]
            else:
                text = str(content)[:150]
            label = "👤" if role == "user" else "🤖"
            lines.append(f"{label} {text}")

        return "\n".join(lines)


class SessionsSendTool(BaseTool):
    """向另一个会话发送消息"""

    name = "sessions_send"
    description = "向另一个会话（Agent session）发送消息，实现 Agent 间协作。目标会话的 Agent 会处理消息并返回结果。"

    def input_schema(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "channel": {
                    "type": "string",
                    "description": "目标会话的通道名",
                },
                "user_id": {
                    "type": "string",
                    "description": "目标会话的用户 ID",
                },
                "message": {
                    "type": "string",
                    "description": "要发送的消息内容",
                },
            },
            "required": ["channel", "user_id", "message"],
        }

    async def execute(self, params: dict) -> str:
        if not _agent:
            return "Agent 服务未初始化"

        channel = params.get("channel", "")
        user_id = params.get("user_id", "")
        message = params.get("message", "")

        if not all([channel, user_id, message]):
            return "请提供 channel、user_id 和 message"

        try:
            from openvort.core.engine.context import RequestContext
            ctx = RequestContext(channel=channel, user_id=user_id, permissions={"*"})
            reply = await _agent.process(ctx, message)
            return f"会话 {channel}:{user_id} 回复:\n{reply}"
        except Exception as e:
            log.error(f"跨会话发送失败: {e}")
            return f"发送失败: {e}"


# 获取所有 session tools 实例
def get_session_tools() -> list[BaseTool]:
    return [SessionsListTool(), SessionsHistoryTool(), SessionsSendTool()]
