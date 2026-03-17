"""
OpenVort 启动器 - 直接运行 Web 服务器

在 Windows 上绕过 CLI 的进程检查问题
"""
import asyncio
import os
import sys

# 设置 UTF-8 编码
if sys.platform == "win32":
    os.environ["PYTHONIOENCODING"] = "utf-8"

# 确保项目路径在 sys.path 中
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from openvort import __version__
from openvort.config.settings import get_settings
from openvort.db import init_db, get_session_factory
from openvort.auth.service import AuthService
from openvort.plugin.registry import PluginRegistry
from openvort.plugin.loader import PluginLoader
from openvort.core.engine.session import SessionStore
from openvort.core.engine.context import RequestContext
from openvort.skill.loader import SkillLoader
from openvort.web.deps import set_runtime
from openvort.web.app import create_app
import uvicorn


async def init_runtime():
    """初始化运行时依赖"""
    from openvort.utils.logging import get_logger
    from openvort.contacts.resolver import IdentityResolver

    log = get_logger("init")

    settings = get_settings()

    log.info(f"OpenVort v{__version__} 初始化...")

    # 初始化数据库
    await init_db(settings.database_url)
    session_factory = get_session_factory()

    # 初始化权限服务
    auth_service = AuthService(session_factory)
    await auth_service.init_builtin()

    # 初始化插件系统
    registry = PluginRegistry()
    loader = PluginLoader(registry, auth_service=auth_service)
    loader.load_all()
    await loader.load_all_async()

    # 加载 Skill
    skill_loader = SkillLoader(registry)

    # 创建 SessionStore
    session_store = SessionStore()

    # 创建 AgentRuntime（需要 LLM 配置）
    llm_settings = settings.llm
    agent = None
    if llm_settings.api_key and llm_settings.api_key != "your-api-key-here":
        from openvort.core.engine.agent import AgentRuntime
        agent = AgentRuntime(
            llm_settings=llm_settings,
            registry=registry,
            session_store=session_store,
            system_prompt="",
        )
        log.info("AgentRuntime 已创建")
    else:
        log.warning("未配置 LLM API Key，Agent 功能不可用")

    # 简化版 build_context
    resolver = IdentityResolver(session_factory)
    async def build_context(channel_name: str, user_id: str) -> RequestContext:
        ctx = RequestContext(channel=channel_name, user_id=user_id)
        async def _refresh_identity(ctx: RequestContext) -> None:
            resolver.invalidate(ctx.channel, ctx.user_id)
            member = await resolver.resolve(ctx.channel, ctx.user_id)
            if member:
                ctx.member = member
                ctx.roles = await auth_service.get_member_roles(member.id)
                ctx.permissions = await auth_service.get_member_permissions(member.id)
        ctx._identity_refresher = _refresh_identity
        return ctx

    # 注入依赖
    set_runtime(
        agent=agent,
        registry=registry,
        session_store=session_store,
        session_factory=session_factory,
        auth_service=auth_service,
        build_context_fn=build_context,
        skill_loader=skill_loader,
    )

    log.info("运行时依赖初始化完成")
    return session_factory


async def _serve():
    """在同一事件循环内完成初始化并启动服务。"""
    await init_runtime()
    config = uvicorn.Config(
        "openvort.web.app:create_app",
        factory=True,
        host="0.0.0.0",
        port=8090,
        log_level="info",
    )
    server = uvicorn.Server(config)
    await server.serve()


def main():
    asyncio.run(_serve())


if __name__ == "__main__":
    main()
