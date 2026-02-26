"""
OpenVort CLI

参考 OpenClaw 风格，提供项目初始化、服务启动、插件管理等命令。
"""

import asyncio
import json
import os
import signal
from pathlib import Path

import click

from openvort import __version__

PID_FILE = Path.home() / ".openvort" / "openvort.pid"


def _is_process_alive(pid: int) -> bool:
    """检查进程是否存活"""
    try:
        os.kill(pid, 0)
        return True
    except (OSError, ProcessLookupError):
        return False


def _check_and_kill_existing():
    """检查并杀掉已有的 openvort 进程，写入当前 PID"""
    if PID_FILE.exists():
        try:
            old_pid = int(PID_FILE.read_text().strip())
            if old_pid != os.getpid() and _is_process_alive(old_pid):
                click.echo(f"发现已有进程 (PID={old_pid})，正在终止...")
                os.kill(old_pid, signal.SIGTERM)
                # 等待旧进程退出
                import time
                for _ in range(10):
                    time.sleep(0.5)
                    if not _is_process_alive(old_pid):
                        break
                else:
                    os.kill(old_pid, signal.SIGKILL)
                click.echo(f"已终止旧进程 (PID={old_pid})")
        except (ValueError, OSError):
            pass

    PID_FILE.parent.mkdir(parents=True, exist_ok=True)
    PID_FILE.write_text(str(os.getpid()))


def _cleanup_pid():
    """清理 PID 文件"""
    try:
        if PID_FILE.exists():
            pid = int(PID_FILE.read_text().strip())
            if pid == os.getpid():
                PID_FILE.unlink()
    except (ValueError, OSError):
        pass


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
@click.option("--relay-url", default=None, help="Relay Server 地址（中继模式）")
@click.option("--poll-db", default=None, help="远程数据库轮询配置（JSON 字符串）")
def start(relay_url, poll_db):
    """启动 OpenVort 服务"""
    _run_async(_start_service(relay_url, poll_db))


async def _start_service(relay_url: str | None, poll_db_json: str | None):
    """启动服务的异步实现"""
    from openvort.auth.service import AuthService
    from openvort.config.settings import get_settings
    from openvort.contacts.plugin import ContactsPlugin
    from openvort.contacts.resolver import IdentityResolver
    from openvort.core.agent import AgentRuntime
    from openvort.core.context import RequestContext
    from openvort.core.session import SessionStore
    from openvort.db import init_db
    from openvort.db.engine import get_session_factory
    from openvort.plugin import PluginLoader, PluginRegistry
    from openvort.utils.logging import setup_logging

    settings = get_settings()
    setup_logging(settings.log_level)

    from openvort.utils.logging import get_logger
    log = get_logger("cli")

    log.info(f"OpenVort v{__version__} 启动中...")

    # 单例保护：杀掉旧进程，写入当前 PID
    _check_and_kill_existing()
    log.info(f"PID={os.getpid()}, PID 文件: {PID_FILE}")

    # 初始化数据库
    await init_db(settings.database_url)

    session_factory = get_session_factory()

    # 初始化权限服务
    auth_service = AuthService(session_factory)
    await auth_service.init_builtin()

    # ---- 首次启动向导 ----
    from openvort.core.setup import is_initialized

    if not await is_initialized(session_factory):
        log.info("检测到首次启动，进入初始化向导...")
        await _run_bootstrap_wizard(settings, session_factory, auth_service)
        # 向导完成后再次检查
        if not await is_initialized(session_factory):
            log.error("初始化未完成，退出")
            _cleanup_pid()
            return

    # 加载 AI 人设（如果存在）
    identity_prompt = ""
    identity_file = Path("data/identity.md")
    if identity_file.exists():
        identity_prompt = identity_file.read_text(encoding="utf-8")
        log.info("已加载 AI 人设配置")

    # 初始化插件系统
    registry = PluginRegistry()
    loader = PluginLoader(registry, auth_service=auth_service)
    loader.load_all()
    await loader.load_all_async()

    # 注入 AuthService 到 ContactsPlugin
    for plugin in loader.get_plugins():
        if isinstance(plugin, ContactsPlugin):
            plugin.set_auth_service(auth_service)

    # 初始化身份解析器
    resolver = IdentityResolver(session_factory)

    # 初始化 Agent
    session_store = SessionStore()
    agent = AgentRuntime(settings.llm, registry, session_store)

    # 注入 AI 人设到 system prompt
    if identity_prompt:
        agent._system_prompt += f"\n\n# AI 身份\n\n{identity_prompt}"

    # 确定 relay 配置（CLI 参数优先，其次 .env）
    effective_relay_url = relay_url or settings.relay.url
    effective_relay_secret = settings.relay.secret

    # 构建 RequestContext 的辅助函数
    async def build_context(channel_name: str, user_id: str) -> RequestContext:
        ctx = RequestContext(channel=channel_name, user_id=user_id)
        # 解析身份
        try:
            member = await resolver.resolve(channel_name, user_id)
            if member:
                ctx.member = member
                ctx.roles = await auth_service.get_member_roles(member.id)
                ctx.permissions = await auth_service.get_member_permissions(member.id)
                # 查职位
                from sqlalchemy import select

                from openvort.contacts.models import PlatformIdentity
                async with session_factory() as session:
                    stmt = select(PlatformIdentity.platform_position).where(
                        PlatformIdentity.platform == channel_name,
                        PlatformIdentity.platform_user_id == user_id,
                    )
                    result = await session.execute(stmt)
                    pos = result.scalar_one_or_none()
                    if pos:
                        ctx.position = pos

                    # 查各平台账号映射
                    stmt2 = select(PlatformIdentity.platform, PlatformIdentity.platform_user_id).where(
                        PlatformIdentity.member_id == member.id,
                    )
                    result2 = await session.execute(stmt2)
                    for row in result2.all():
                        ctx.platform_accounts[row[0]] = row[1]
        except Exception as e:
            log.warning(f"构建上下文失败: {e}")

        # 渠道 prompt
        ch = registry.get_channel(channel_name)
        if ch:
            ctx.channel_prompt = ch.get_channel_prompt()
            ctx.allowed_tools = ch.get_tool_filter()
            ctx.max_reply_length = ch.get_max_reply_length()

        return ctx

    # 初始化消息调度器
    from openvort.core.dispatcher import MessageDispatcher
    dispatcher = MessageDispatcher()

    # 配置 Channel
    channels = registry.list_channels()
    for ch in channels:
        if ch.name == "wecom" and ch.is_configured():
            _ch = ch  # 闭包捕获

            async def handle_message(msg):
                # 初始化守卫：未初始化时拒绝外部渠道消息
                from openvort.core.setup import is_initialized as _is_init
                if not await _is_init(session_factory):
                    log.warning(f"系统未初始化，忽略来自 {msg.channel}:{msg.sender_id} 的消息")
                    from openvort.plugin.base import Message as Msg
                    await _ch.send(msg.sender_id, Msg(
                        content="系统正在初始化中，请稍后再试。", channel="wecom",
                    ))
                    return None

                ctx = await build_context(msg.channel, msg.sender_id)
                ctx.images = getattr(msg, "images", []) or []

                async def process_fn(ctx_, content_):
                    return await agent.process(ctx_, content_)

                async def send_fn(reply_):
                    log.info(f"回复: {reply_[:50]}")
                    from openvort.plugin.base import Message as Msg
                    await _ch.send(msg.sender_id, Msg(content=reply_, channel="wecom"))

                # dispatcher 返回 None 表示消息已入队，不需要回复
                reply = await dispatcher.dispatch(ctx, msg.content, process_fn, send_fn)
                return reply

            ch.on_message(handle_message)

            if effective_relay_url:
                await ch.start_relay(effective_relay_url, relay_secret=effective_relay_secret)
            elif poll_db_json:
                db_config = json.loads(poll_db_json)
                await ch.start_polling(db_config)
            else:
                await ch.start()

    mode = "relay" if effective_relay_url else ("poll-db" if poll_db_json else "webhook")
    log.info(f"已加载 {len(channels)} 个 Channel, {len(registry.list_tools())} 个 Tool (模式: {mode})")
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
        _cleanup_pid()
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
    from openvort.auth.service import AuthService
    from openvort.config.settings import get_settings
    from openvort.core.agent import AgentRuntime
    from openvort.core.context import RequestContext
    from openvort.core.session import SessionStore
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


if __name__ == "__main__":
    main()


# ============ contacts ============


@main.group()
def contacts():
    """通讯录管理"""
    pass


@contacts.command("sync")
@click.option("--platform", default=None, help="指定平台（wecom/zentao/...），不指定则同步全部")
def contacts_sync(platform):
    """从外部平台同步通讯录"""
    _run_async(_contacts_sync(platform))


async def _contacts_sync(platform: str | None):
    from openvort.config.settings import get_settings
    from openvort.contacts.service import ContactService
    from openvort.db import init_db
    from openvort.db.engine import get_session_factory
    from openvort.plugin import PluginLoader, PluginRegistry
    from openvort.utils.logging import setup_logging

    settings = get_settings()
    setup_logging(settings.log_level)

    await init_db(settings.database_url)

    registry = PluginRegistry()
    loader = PluginLoader(registry)
    loader.load_all()

    # 收集所有 SyncProvider
    providers = []
    for ch in registry.list_channels():
        p = ch.get_sync_provider()
        if p and (platform is None or p.platform == platform):
            providers.append(p)

    # 从 loader 收集 plugin 的 provider（需要访问 plugin 实例）
    for plugin_instance in loader.get_plugins():
        p = plugin_instance.get_sync_provider()
        if p and (platform is None or p.platform == platform):
            providers.append(p)

    if not providers:
        click.echo(f"未找到可用的同步源{f' (platform={platform})' if platform else ''}")
        return

    service = ContactService(get_session_factory(), settings.contacts.auto_match_threshold)

    for provider in providers:
        click.echo(f"同步 {provider.platform} ...")
        try:
            stats = await service.sync_from_provider(provider)
            click.echo(
                f"  ✅ 新建 {stats['created']}, 更新 {stats['updated']}, "
                f"自动关联 {stats['matched']}, 待确认 {stats['pending']}"
            )
        except Exception as e:
            click.echo(f"  ❌ 同步失败: {e}")

    from openvort.db import close_db
    await close_db()


@contacts.command("list")
@click.option("--status", default="active", help="成员状态过滤 (active/inactive)")
def contacts_list(status):
    """列出通讯录成员"""
    _run_async(_contacts_list(status))


async def _contacts_list(status: str):
    from openvort.config.settings import get_settings
    from openvort.contacts.service import ContactService
    from openvort.db import init_db
    from openvort.db.engine import get_session_factory

    settings = get_settings()
    await init_db(settings.database_url)

    service = ContactService(get_session_factory())
    members = await service.list_members(status=status)

    if not members:
        click.echo("通讯录为空")
        return

    click.echo(f"共 {len(members)} 位成员:\n")
    for m in members:
        identities = await service.get_member_identities(m.id)
        platforms = ", ".join(f"{i.platform}:{i.platform_user_id}" for i in identities)
        click.echo(f"  {m.name:12s} {m.email or '-':24s} {m.phone or '-':14s} [{platforms}]")

    from openvort.db import close_db
    await close_db()


@contacts.command("match")
def contacts_match():
    """查看待确认的匹配建议"""
    _run_async(_contacts_match())


async def _contacts_match():
    from openvort.config.settings import get_settings
    from openvort.contacts.service import ContactService
    from openvort.db import init_db
    from openvort.db.engine import get_session_factory

    settings = get_settings()
    await init_db(settings.database_url)

    service = ContactService(get_session_factory())
    suggestions = await service.list_pending_suggestions()

    if not suggestions:
        click.echo("没有待确认的匹配建议")
        return

    click.echo(f"共 {len(suggestions)} 条待确认:\n")
    for s in suggestions:
        click.echo(
            f"  [{s.id}] {s.match_type} (置信度 {s.confidence:.2f}) "
            f"identity#{s.source_identity_id} -> member#{s.target_member_id[:8]}"
        )

    click.echo("\n使用 `openvort contacts accept <id>` 或 `openvort contacts reject <id>` 处理")

    from openvort.db import close_db
    await close_db()


@contacts.command("accept")
@click.argument("suggestion_id", type=int)
def contacts_accept(suggestion_id):
    """接受匹配建议"""
    _run_async(_contacts_accept(suggestion_id))


async def _contacts_accept(suggestion_id: int):
    from openvort.config.settings import get_settings
    from openvort.contacts.service import ContactService
    from openvort.db import init_db
    from openvort.db.engine import get_session_factory

    settings = get_settings()
    await init_db(settings.database_url)

    service = ContactService(get_session_factory())
    ok = await service.accept_suggestion(suggestion_id, resolved_by="cli")

    click.echo(f"{'✅ 已接受' if ok else '❌ 操作失败（建议不存在或已处理）'}")

    from openvort.db import close_db
    await close_db()


@contacts.command("reject")
@click.argument("suggestion_id", type=int)
def contacts_reject(suggestion_id):
    """拒绝匹配建议"""
    _run_async(_contacts_reject(suggestion_id))


async def _contacts_reject(suggestion_id: int):
    from openvort.config.settings import get_settings
    from openvort.contacts.service import ContactService
    from openvort.db import init_db
    from openvort.db.engine import get_session_factory

    settings = get_settings()
    await init_db(settings.database_url)

    service = ContactService(get_session_factory())
    ok = await service.reject_suggestion(suggestion_id, resolved_by="cli")

    click.echo(f"{'✅ 已拒绝' if ok else '❌ 操作失败（建议不存在或已处理）'}")

    from openvort.db import close_db
    await close_db()


# ============ Bootstrap Wizard ============


async def _run_bootstrap_wizard(settings, session_factory, auth_service):
    """AI 驱动的首次启动向导（CLI 对话循环）"""
    from pathlib import Path

    from openvort.core.agent import AgentRuntime
    from openvort.core.bootstrap import SetupCompleteTool
    from openvort.core.session import SessionStore
    from openvort.core.setup import is_initialized
    from openvort.plugin.registry import PluginRegistry

    click.echo("\n" + "=" * 50)
    click.echo("  🚀 OpenVort 首次启动向导")
    click.echo("=" * 50 + "\n")

    # 加载 bootstrap prompt
    prompt_path = Path(__file__).parent / "core" / "prompts" / "bootstrap.md"
    bootstrap_prompt = prompt_path.read_text(encoding="utf-8")

    # 创建临时 registry，只注册 setup_complete 工具
    wizard_registry = PluginRegistry()
    setup_tool = SetupCompleteTool(session_factory, auth_service)
    wizard_registry.register_tool(setup_tool)

    # 创建临时 Agent
    wizard_session = SessionStore()
    wizard_agent = AgentRuntime(
        settings.llm,
        wizard_registry,
        wizard_session,
        system_prompt=bootstrap_prompt,
    )

    # 用空消息触发 AI 先开口
    from openvort.core.context import RequestContext

    ctx = RequestContext(channel="cli", user_id="admin_setup", permissions={"*"})
    click.echo("⏳ 正在准备...\n")
    greeting = await wizard_agent.process(ctx, "你好，我刚启动了 OpenVort")
    click.echo(f"🤖 {greeting}\n")

    # 对话循环
    while True:
        try:
            user_input = input("👤 ").strip()
        except (EOFError, KeyboardInterrupt):
            click.echo("\n初始化已取消。")
            return

        if not user_input:
            continue

        click.echo("⏳ 思考中...\n")
        reply = await wizard_agent.process(ctx, user_input)
        click.echo(f"🤖 {reply}\n")

        # 检查是否已完成初始化
        if await is_initialized(session_factory):
            click.echo("=" * 50)
            click.echo("  ✅ 初始化完成，正在启动服务...")
            click.echo("=" * 50 + "\n")
            return
