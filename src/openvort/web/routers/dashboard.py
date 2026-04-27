"""仪表盘路由"""

from datetime import datetime, timezone

from fastapi import APIRouter, Request

from openvort.web.deps import get_registry, get_session_store

router = APIRouter()


def _extract_member_id(request: Request) -> str:
    from openvort.web.auth import verify_token
    auth = request.headers.get("Authorization", "")
    token = auth[7:] if auth.startswith("Bearer ") else ""
    payload = verify_token(token) if token else None
    return (payload or {}).get("sub", "")


def _is_llm_configured() -> bool:
    try:
        from openvort.config.settings import get_settings
        api_key = get_settings().llm.api_key
        return bool(api_key and api_key != "your-api-key-here")
    except Exception:
        return False


@router.get("")
async def dashboard(request: Request):
    member_id = _extract_member_id(request)
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
        if member_id and session.user_id != member_id:
            continue

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

    active_sessions = sum(
        1 for s in session_store._sessions.values()
        if not member_id or s.user_id == member_id
    )

    return {
        "agentStatus": "running",
        "llmConfigured": _is_llm_configured(),
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
        "activeSessions": active_sessions,
    }
