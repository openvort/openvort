"""仪表盘路由"""

from fastapi import APIRouter

from openvort.web.deps import get_registry, get_session_store

router = APIRouter()


@router.get("")
async def dashboard():
    registry = get_registry()
    session_store = get_session_store()

    plugins = registry.list_plugins()
    channels = registry.list_channels()
    tools = registry.list_tools()

    # 统计消息数和 token 用量
    total_messages = 0
    total_input_tokens = 0
    total_output_tokens = 0
    session_usage = []  # 每个 session 的用量

    for key, session in session_store._sessions.items():
        total_messages += len(session.messages)
        total_input_tokens += session.total_input_tokens
        total_output_tokens += session.total_output_tokens
        if session.total_input_tokens > 0 or session.total_output_tokens > 0:
            session_usage.append({
                "key": key,
                "user_id": session.user_id,
                "channel": session.channel,
                "input_tokens": session.total_input_tokens,
                "output_tokens": session.total_output_tokens,
                "messages": len(session.messages),
            })

    # 按 output_tokens 降序排列
    session_usage.sort(key=lambda x: x["output_tokens"], reverse=True)

    return {
        "agentStatus": "running",
        "totalMessages": total_messages,
        "totalContacts": 0,
        "totalPlugins": len(plugins),
        "totalChannels": len(channels),
        "totalTools": len(tools),
        "totalInputTokens": total_input_tokens,
        "totalOutputTokens": total_output_tokens,
        "sessionUsage": session_usage[:20],  # Top 20
        "recentMessages": [],
    }
