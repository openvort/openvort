"""
OpenVort CLI

参考 OpenClaw 风格，提供项目初始化、服务启动、插件管理等命令。
"""

import asyncio
import json
import sys
from pathlib import Path

import click

from openvort import __version__


def _run_async(coro):
    """在同步 CLI 中运行异步函数"""
    return asyncio.run(coro)


@click.group()
@click.version_option(__version__, prog_name="openvort")
def main():
    """OpenVort — 开源 AI 研发工作流引擎"""
    pass


# ============ init ============


@main.command()
def init():
    """初始化配置（交互式）"""
    env_file = Path(".env")
    if env_file.exists():
        if not click.confirm(".env 文件已存在，是否覆盖？", default=False):
            click.echo("已取消")
            return

    click.echo("🚀 OpenVort 初始化向导\n")

    # LLM 配置
    click.echo("── LLM 配置 ──")
    provider = click.prompt("LLM 提供商", default="anthropic")
    api_key = click.prompt("API Key", hide_input=True)
    api_base = click.prompt("API Base URL", default="https://api.anthropic.com")
    model = click.prompt("模型", default="claude-sonnet-4-20250514")

    # 企微配置（可选）
    click.echo("\n── 企业微信配置（可选，回车跳过）──")
    corp_id = click.prompt("Corp ID", default="", show_default=False)
    app_secret = click.prompt("App Secret", default="", show_default=False, hide_input=bool(corp_id))
    agent_id = click.prompt("Agent ID", default="", show_default=False)

    # 写入 .env
    lines = [
        "# OpenVort 配置",
        f"OPENVORT_LLM_PROVIDER={provider}",
        f"OPENVORT_LLM_API_KEY={api_key}",
        f"OPENVORT_LLM_API_BASE={api_base}",
        f"OPENVORT_LLM_MODEL={model}",
        "",
        "# 数据库",
        "OPENVORT_DATABASE_URL=sqlite+aiosqlite:///openvort.db",
        "",
    ]

    if corp_id:
        lines.extend([
            "# 企业微信",
            f"OPENVORT_WECOM_CORP_ID={corp_id}",
            f"OPENVORT_WECOM_APP_SECRET={app_secret}",
            f"OPENVORT_WECOM_AGENT_ID={agent_id}",
        ])

    env_file.write_text("\n".join(lines) + "\n")
    click.echo(f"\n✅ 配置已写入 {env_file}")
    click.echo("运行 `openvort start` 启动服务")


# ============ start ============


@main.command()
@click.option("--poll-db", default=None, help="远程数据库轮询配置（JSON 字符串）")
def start(poll_db):
    """启动 OpenVort 服务"""
    _run_async(_start_service(poll_db))


async def _start_service(poll_db_json: str | None):
    """启动服务的异步实现"""
    from openvort.config.settings import get_settings
    from openvort.core.agent import AgentRuntime
    from openvort.core.session import SessionStore
    from openvort.db import init_db
    from openvort.plugin import PluginLoader, PluginRegistry
    from openvort.utils.logging import setup_logging

    settings = get_settings()
    setup_logging(settings.log_level)

    from openvort.utils.logging import get_logger
    log = get_logger("cli")

    log.info(f"OpenVort v{__version__} 启动中...")

    # 初始化数据库
    await init_db(settings.database_url)

    # 初始化插件系统
    registry = PluginRegistry()
    loader = PluginLoader(registry)
    loader.load_all()

    # 初始化 Agent
    session_store = SessionStore()
    agent = AgentRuntime(settings.llm, registry, session_store)

    # 配置企微 Channel
    channels = registry.list_channels()
    for ch in channels:
        if ch.name == "wecom" and ch.is_configured():
            # 注册消息处理器
            async def handle_message(msg):
                reply = await agent.process(msg.channel, msg.sender_id, msg.content)
                return reply

            ch.on_message(handle_message)

            if poll_db_json:
                db_config = json.loads(poll_db_json)
                await ch.start_polling(db_config)
            else:
                await ch.start()

    log.info(f"已加载 {len(channels)} 个 Channel, {len(registry.list_tools())} 个 Tool")
    log.info("OpenVort 已就绪，等待消息...")

    # 保持运行
    try:
        while True:
            await asyncio.sleep(1)
    except (KeyboardInterrupt, asyncio.CancelledError):
        log.info("正在关闭...")
        for ch in channels:
            await ch.stop()
        from openvort.db import close_db
        await close_db()
        log.info("已退出")


# ============ channels ============


@main.group()
def channels():
    """管理 IM 通道"""
    pass


@channels.command("list")
def channels_list():
    """列出已配置的通道"""
    from openvort.plugin import PluginLoader, PluginRegistry

    registry = PluginRegistry()
    loader = PluginLoader(registry)
    loader.load_all()

    chs = registry.list_channels()
    if not chs:
        click.echo("未发现任何 Channel 插件")
        return

    click.echo(f"已注册 {len(chs)} 个 Channel:\n")
    for ch in chs:
        status = "✅ 已配置" if ch.is_configured() else "❌ 未配置"
        click.echo(f"  {ch.name:12s} {ch.display_name:10s} {status}")


@channels.command("test")
@click.argument("channel_name")
def channels_test(channel_name):
    """测试通道连通性"""
    _run_async(_test_channel(channel_name))


async def _test_channel(name: str):
    from openvort.plugin import PluginLoader, PluginRegistry

    registry = PluginRegistry()
    loader = PluginLoader(registry)
    loader.load_all()

    ch = registry.get_channel(name)
    if not ch:
        click.echo(f"未找到 Channel: {name}")
        return

    if not ch.is_configured():
        click.echo(f"Channel '{name}' 未配置，请先运行 `openvort init`")
        return

    click.echo(f"测试 {name} 连通性...")
    if hasattr(ch, "api"):
        ok = await ch.api.health_check()
        click.echo(f"  {'✅ 连接成功' if ok else '❌ 连接失败'}")
    else:
        click.echo("  ⚠️ 该 Channel 不支持连通性测试")


# ============ tools ============


@main.group()
def tools():
    """管理 AI 工具"""
    pass


@tools.command("list")
def tools_list():
    """列出已注册的工具"""
    from openvort.plugin import PluginLoader, PluginRegistry

    registry = PluginRegistry()
    loader = PluginLoader(registry)
    loader.load_all()

    ts = registry.list_tools()
    if not ts:
        click.echo("未发现任何 Tool 插件")
        return

    click.echo(f"已注册 {len(ts)} 个 Tool:\n")
    for t in ts:
        click.echo(f"  {t.name:30s} {t.description[:60]}")


# ============ agent ============


@main.group()
def agent():
    """Agent 调试"""
    pass


@agent.command("chat")
@click.argument("message")
def agent_chat(message):
    """直接跟 Agent 对话（调试用）"""
    _run_async(_agent_chat(message))


async def _agent_chat(message: str):
    from openvort.config.settings import get_settings
    from openvort.core.agent import AgentRuntime
    from openvort.core.session import SessionStore
    from openvort.plugin import PluginLoader, PluginRegistry
    from openvort.utils.logging import setup_logging

    settings = get_settings()
    setup_logging("WARNING")  # CLI 模式减少日志噪音

    registry = PluginRegistry()
    loader = PluginLoader(registry)
    loader.load_all()

    session_store = SessionStore()
    runtime = AgentRuntime(settings.llm, registry, session_store)

    click.echo("🤖 思考中...\n")
    reply = await runtime.chat(message)
    click.echo(reply)


if __name__ == "__main__":
    main()


# ============ relay ============


@main.group()
def relay():
    """Relay 消息中继服务"""
    pass


@relay.command("start")
@click.option("--port", default=None, type=int, help="监听端口")
@click.option("--host", default="0.0.0.0", help="监听地址")
@click.option("--db-path", default="relay.db", help="SQLite 数据库路径")
def relay_start(port, host, db_path):
    """启动 Relay Server（部署在公网服务器）"""
    from openvort.config.settings import get_settings
    from openvort.utils.logging import setup_logging

    settings = get_settings()
    setup_logging(settings.log_level)

    effective_port = port or settings.relay.port or 8080

    if not settings.wecom.corp_id or not settings.wecom.app_secret:
        click.echo("❌ 企微未配置，请先在 .env 中设置 OPENVORT_WECOM_CORP_ID 和 OPENVORT_WECOM_APP_SECRET")
        return

    from openvort.relay.server import create_app

    app = create_app(
        corp_id=settings.wecom.corp_id,
        app_secret=settings.wecom.app_secret,
        agent_id=settings.wecom.agent_id,
        callback_token=settings.wecom.callback_token,
        callback_aes_key=settings.wecom.callback_aes_key,
        relay_secret=settings.relay.secret,
        db_path=db_path,
    )

    click.echo(f"🚀 Relay Server 启动中 → {host}:{effective_port}")
    click.echo(f"   回调地址: http://<your-domain>:{effective_port}/callback/wecom")
    click.echo(f"   API 地址: http://<your-domain>:{effective_port}/relay/")

    import uvicorn
    uvicorn.run(app, host=host, port=effective_port, log_level="info")


@relay.command("health")
@click.option("--url", default=None, help="Relay Server 地址")
def relay_health(url):
    """检查 Relay Server 连通性"""
    _run_async(_relay_health(url))


async def _relay_health(url: str | None):
    from openvort.config.settings import get_settings

    settings = get_settings()
    effective_url = url or settings.relay.url

    if not effective_url:
        click.echo("❌ 未配置 Relay URL，请通过 --url 参数或 OPENVORT_RELAY_URL 环境变量指定")
        return

    import httpx
    try:
        headers = {}
        if settings.relay.secret:
            headers["Authorization"] = f"Bearer {settings.relay.secret}"
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.get(f"{effective_url.rstrip('/')}/relay/health", headers=headers)
            data = resp.json()
            if data.get("status") == "ok":
                click.echo(f"✅ Relay Server 正常 ({effective_url})")
            else:
                click.echo(f"⚠️ Relay Server 异常: {data}")
    except Exception as e:
        click.echo(f"❌ 连接失败: {e}")
