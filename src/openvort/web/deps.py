"""
Web 面板依赖注入

提供 FastAPI Depends 所需的运行时对象。
"""

from typing import Optional

from openvort.core.agent import AgentRuntime
from openvort.core.session import SessionStore
from openvort.plugin.registry import PluginRegistry

# 运行时单例，由 cli.py 启动时注入
_agent: Optional[AgentRuntime] = None
_registry: Optional[PluginRegistry] = None
_session_store: Optional[SessionStore] = None
_session_factory = None  # SQLAlchemy async session factory
_auth_service = None  # AuthService
_build_context_fn = None  # async (channel, user_id) -> RequestContext
_skill_loader = None  # SkillLoader
_config_service = None  # ConfigService
_schedule_service = None  # ScheduleService
_embedding_service = None  # EmbeddingService


def set_runtime(
    agent: AgentRuntime,
    registry: PluginRegistry,
    session_store: SessionStore,
    session_factory=None,
    auth_service=None,
    build_context_fn=None,
    skill_loader=None,
    config_service=None,
    schedule_service=None,
    embedding_service=None,
):
    global _agent, _registry, _session_store, _session_factory, _auth_service, _build_context_fn, _skill_loader, _config_service, _schedule_service, _embedding_service
    _agent = agent
    _registry = registry
    _session_store = session_store
    _session_factory = session_factory
    _auth_service = auth_service
    _build_context_fn = build_context_fn
    _skill_loader = skill_loader
    _config_service = config_service
    _schedule_service = schedule_service
    _embedding_service = embedding_service


def get_agent() -> AgentRuntime:
    assert _agent is not None, "AgentRuntime not initialized"
    return _agent


def get_registry() -> PluginRegistry:
    assert _registry is not None, "PluginRegistry not initialized"
    return _registry


def get_session_store() -> SessionStore:
    assert _session_store is not None, "SessionStore not initialized"
    return _session_store


def get_db_session_factory():
    assert _session_factory is not None, "DB session factory not initialized"
    return _session_factory


def get_auth_service():
    assert _auth_service is not None, "AuthService not initialized"
    return _auth_service


def get_build_context_fn():
    """获取构建 RequestContext 的函数"""
    return _build_context_fn


def get_skill_loader():
    """获取 SkillLoader 实例"""
    assert _skill_loader is not None, "SkillLoader not initialized"
    return _skill_loader


def get_config_service():
    """获取 ConfigService 实例"""
    assert _config_service is not None, "ConfigService not initialized"
    return _config_service


def get_schedule_service():
    """获取 ScheduleService 实例（可能为 None）"""
    return _schedule_service


def get_embedding_service():
    """获取 EmbeddingService 实例（可能为 None）"""
    return _embedding_service
