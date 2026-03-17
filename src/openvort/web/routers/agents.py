"""Agent 路由管理路由（CRUD）"""

from fastapi import APIRouter
from pydantic import BaseModel

from openvort.web.deps import get_agent

router = APIRouter()

# 运行时引用，由 app.py 注入
_router_instance = None


def set_agent_router(agent_router):
    global _router_instance
    _router_instance = agent_router


class AgentRouteItem(BaseModel):
    name: str
    model: str = ""
    system_prompt: str = ""
    max_tokens: int = 0
    channels: list[str] = []
    user_ids: list[str] = []
    group_ids: list[str] = []


@router.get("")
async def list_agents():
    """列出所有 Agent 路由"""
    if _router_instance:
        return _router_instance.list_agents()
    # 无路由器时返回默认 agent 信息
    from openvort.config.settings import get_settings
    settings = get_settings()
    return [{"name": "default", "model": settings.llm.model, "channels": ["*"], "users": ["*"]}]


@router.post("")
async def create_agent_route(req: AgentRouteItem):
    """创建 Agent 路由规则"""
    if not _router_instance:
        return {"success": False, "error": "Agent 路由器未初始化"}
    from openvort.core.engine.router import AgentConfig
    config = AgentConfig(
        name=req.name, model=req.model, system_prompt=req.system_prompt,
        max_tokens=req.max_tokens, channels=req.channels,
        user_ids=req.user_ids, group_ids=req.group_ids,
    )
    _router_instance.add_agent(config)
    return {"success": True}


@router.delete("/{name}")
async def delete_agent_route(name: str):
    """删除 Agent 路由规则（仅移除配置，不销毁已创建的实例）"""
    if not _router_instance:
        return {"success": False, "error": "Agent 路由器未初始化"}
    if name == "default":
        return {"success": False, "error": "不能删除默认 Agent"}
    _router_instance._configs = [c for c in _router_instance._configs if c.name != name]
    _router_instance._agents.pop(name, None)
    return {"success": True}
