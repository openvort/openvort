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

    # 统计消息数
    total_messages = 0
    for key, session in session_store._sessions.items():
        total_messages += len(session.messages)

    return {
        "agentStatus": "running",
        "totalMessages": total_messages,
        "totalContacts": 0,
        "totalPlugins": len(plugins),
        "totalChannels": len(channels),
        "totalTools": len(tools),
        "recentMessages": [],
    }
