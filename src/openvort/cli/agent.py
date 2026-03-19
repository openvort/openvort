"""Agent debug commands."""

import click

from openvort.cli import _run_async


@click.group()
def agent():
    """Agent 调试"""
    pass


@agent.command("chat")
@click.argument("message")
def agent_chat(message):
    """直接跟 Agent 对话（调试用）"""
    _run_async(_agent_chat(message))


async def _agent_chat(message: str):
    from openvort.auth.service import AuthService
    from openvort.config.settings import get_settings
    from openvort.core.engine.agent import AgentRuntime
    from openvort.core.engine.context import RequestContext
    from openvort.core.engine.session import SessionStore
    from openvort.db import init_db
    from openvort.db.engine import get_session_factory
    from openvort.plugin import PluginLoader, PluginRegistry
    from openvort.utils.logging import setup_logging

    settings = get_settings()
    setup_logging("WARNING")  # CLI 模式减少日志噪音

    # 初始化数据库（Tool 可能需要）
    await init_db(settings.database_url)

    session_factory = get_session_factory()

    # 初始化权限服务
    auth_service = AuthService(session_factory)
    await auth_service.init_builtin()

    registry = PluginRegistry()
    loader = PluginLoader(registry, auth_service=auth_service)
    loader.load_all()
    await loader.load_all_async()

    session_store = SessionStore()
    runtime = AgentRuntime(settings.llm, registry, session_store)

    # CLI 调试用 RequestContext（debug 用户拥有全部权限）
    ctx = RequestContext(channel="cli", user_id="debug", permissions={"*"})

    click.echo("🤖 思考中...\n")
    reply = await runtime.process(ctx, message)
    click.echo(reply)

    from openvort.db import close_db
    await close_db()
