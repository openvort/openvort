"""仪表盘路由"""

from datetime import datetime, timezone

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

    total_messages = 0
    total_input_tokens = 0
    total_output_tokens = 0
    session_usage = []
    recent_messages = []

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

        # Collect recent user messages for display
        for msg in reversed(session.messages):
            if msg.get("role") == "user" and isinstance(msg.get("content"), str):
                content = msg["content"][:120]
                updated = datetime.fromtimestamp(session.updated_at, tz=timezone.utc)
                recent_messages.append({
                    "user": session.user_id,
                    "content": content,
                    "time": updated.strftime("%m-%d %H:%M"),
                    "timestamp": session.updated_at,
                })
                break

    session_usage.sort(key=lambda x: x["output_tokens"], reverse=True)
    recent_messages.sort(key=lambda x: x["timestamp"], reverse=True)

    return {
        "agentStatus": "running",
        "totalMessages": total_messages,
        "totalContacts": 0,
        "totalPlugins": len(plugins),
        "totalChannels": len(channels),
        "totalTools": len(tools),
        "totalInputTokens": total_input_tokens,
        "totalOutputTokens": total_output_tokens,
        "sessionUsage": session_usage[:20],
        "recentMessages": recent_messages[:10],
        "pluginNames": [p.name for p in plugins],
        "channelNames": [c.name for c in channels],
        "activeSessions": len(session_store._sessions),
    }
