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
@click.option("--web/--no-web", default=None, help="启用/禁用 Web 管理面板")
def start(relay_url, poll_db, web):
    """启动 OpenVort 服务"""
    _run_async(_start_service(relay_url, poll_db, web))


async def _start_service(relay_url: str | None, poll_db_json: str | None, web_flag: bool | None):
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

    # 加载 Skill（知识注入）
    from openvort.skill.loader import SkillLoader
    skill_loader = SkillLoader(registry)
    skill_loader.load_all()

    # 注入 AuthService 到 ContactsPlugin
    for plugin in loader.get_plugins():
        if isinstance(plugin, ContactsPlugin):
            plugin.set_auth_service(auth_service)

    # 初始化身份解析器
    resolver = IdentityResolver(session_factory)

    # 从 DB 加载配置覆盖（优先级：DB > .env > 默认值）
    from openvort.config.config_service import ConfigService
    config_service = ConfigService(session_factory)
    await config_service.load_all()
    await config_service.apply_llm_to_settings()

    # 初始化 Agent
    session_store = SessionStore(session_factory=session_factory)
    agent = AgentRuntime(settings.llm, registry, session_store)

    # 初始化 IM 命令处理器
    from openvort.core.commands import CommandHandler
    command_handler = CommandHandler(
        session_store=session_store,
        llm_client=agent._llm,
        model_name=settings.llm.model,
    )

    # 注入 AI 人设到 system prompt
    if identity_prompt:
        agent._system_prompt += f"\n\n# AI 身份\n\n{identity_prompt}"

    # 确定 relay 配置（CLI 参数优先，其次 .env）
    effective_relay_url = relay_url or settings.relay.url
    effective_relay_secret = settings.relay.secret

    # 构建 RequestContext 的辅助函数
    async def build_context(channel_name: str, user_id: str) -> RequestContext:
        ctx = RequestContext(channel=channel_name, user_id=user_id)

        # 注入身份刷新回调（同步/绑定后可重新解析身份）
        async def _refresh_identity(ctx: RequestContext) -> None:
            resolver.invalidate(ctx.channel, ctx.user_id)
            member = await resolver.resolve(ctx.channel, ctx.user_id)
            if member:
                ctx.member = member
                ctx.roles = await auth_service.get_member_roles(member.id)
                ctx.permissions = await auth_service.get_member_permissions(member.id)
                ctx.platform_accounts.clear()
                from sqlalchemy import select
                from openvort.contacts.models import PlatformIdentity
                async with session_factory() as session:
                    stmt = select(PlatformIdentity.platform, PlatformIdentity.platform_user_id).where(
                        PlatformIdentity.member_id == member.id,
                    )
                    result = await session.execute(stmt)
                    for row in result.all():
                        ctx.platform_accounts[row[0]] = row[1]

        ctx._identity_refresher = _refresh_identity

        # 解析身份
        try:
            member = None
            if channel_name == "web":
                # Web 通道的 user_id 就是 member_id，直接按 ID 查
                from sqlalchemy import select as _select
                from openvort.contacts.models import Member as _Member
                async with session_factory() as _sess:
                    _result = await _sess.execute(_select(_Member).where(_Member.id == user_id))
                    member = _result.scalar_one_or_none()
            else:
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

                # IM 命令拦截（/new /status /compact /think /usage /help）
                cmd_result = await command_handler.handle(msg.channel, msg.sender_id, msg.content)
                if cmd_result.handled:
                    if cmd_result.reply:
                        from openvort.plugin.base import Message as Msg
                        await _ch.send(msg.sender_id, Msg(content=cmd_result.reply, channel="wecom"))
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

        # ---- OpenClaw Channel ----
        if ch.name == "openclaw" and ch.is_configured():
            _oc_ch = ch

            async def handle_openclaw_message(msg):
                from openvort.core.setup import is_initialized as _is_init
                if not await _is_init(session_factory):
                    log.warning(f"系统未初始化，忽略来自 openclaw:{msg.sender_id} 的消息")
                    return None

                cmd_result = await command_handler.handle(msg.channel, msg.sender_id, msg.content)
                if cmd_result.handled:
                    if cmd_result.reply:
                        from openvort.plugin.base import Message as Msg
                        await _oc_ch.send(msg.sender_id, Msg(content=cmd_result.reply, channel="openclaw"))
                    return None

                ctx = await build_context(msg.channel, msg.sender_id)
                ctx.images = getattr(msg, "images", []) or []

                async def process_fn(ctx_, content_):
                    return await agent.process(ctx_, content_)

                async def send_fn(reply_):
                    log.info(f"OpenClaw 回复: {reply_[:50]}")
                    from openvort.plugin.base import Message as Msg
                    await _oc_ch.send(msg.sender_id, Msg(content=reply_, channel="openclaw"))

                reply = await dispatcher.dispatch(ctx, msg.content, process_fn, send_fn)
                return reply

            ch.on_message(handle_openclaw_message)
            await ch.start()

    mode = "relay" if effective_relay_url else ("poll-db" if poll_db_json else "webhook")
    log.info(f"已加载 {len(channels)} 个 Channel, {len(registry.list_tools())} 个 Tool (模式: {mode})")

    # ---- 定时任务调度器 ----
    from openvort.core.scheduler import Scheduler as _Scheduler
    from openvort.core.schedule_service import ScheduleService as _ScheduleService

    _scheduler = _Scheduler()
    _scheduler.start()
    schedule_service = _ScheduleService(session_factory, _scheduler, agent)
    try:
        count = await schedule_service.sync_to_scheduler()
        if count:
            log.info(f"已恢复 {count} 个定时任务")
    except Exception as e:
        log.warning(f"恢复定时任务失败: {e}")

    # ---- Web 管理面板 ----
    web_enabled = web_flag if web_flag is not None else settings.web.enabled
    web_server = None
    if web_enabled:
        try:
            import uvicorn
            from openvort.web.app import create_app
            from openvort.web.deps import set_runtime
            from openvort.web.routers.logs import install_log_handler

            # 注入运行时依赖
            set_runtime(agent, registry, session_store, session_factory,
                        auth_service=auth_service, build_context_fn=build_context,
                        skill_loader=skill_loader, config_service=config_service,
                        schedule_service=schedule_service)
            install_log_handler()

            web_app = create_app()
            config = uvicorn.Config(
                web_app,
                host=settings.web.host,
                port=settings.web.port,
                log_level="warning",
            )
            web_server = uvicorn.Server(config)

            async def _run_web_server():
                try:
                    await web_server.serve()
                except SystemExit:
                    pass
                except Exception as e:
                    log.warning(f"Web 面板运行异常: {e}")

            asyncio.create_task(_run_web_server())
            log.info(f"Web 管理面板已启动: http://{settings.web.host}:{settings.web.port}")
        except ImportError:
            log.warning("未安装 uvicorn/fastapi，Web 面板未启动。运行 pip install uvicorn fastapi 安装。")
        except Exception as e:
            log.warning(f"Web 面板启动失败: {e}")

    log.info("OpenVort 已就绪，等待消息...")

    # 保持运行
    try:
        while True:
            await asyncio.sleep(1)
    except (KeyboardInterrupt, asyncio.CancelledError):
        log.info("正在关闭...")
        _scheduler.stop()
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


# ============ plugins ============


@main.group()
def plugins():
    """管理插件"""
    pass


@plugins.command("list")
def plugins_list():
    """列出所有 Plugin（内置 + pip + 本地）"""
    from openvort.plugin import PluginLoader, PluginRegistry

    registry = PluginRegistry()
    loader = PluginLoader(registry)
    loader.load_all()

    all_plugins = registry.list_plugins()
    if not all_plugins:
        click.echo("未发现任何 Plugin")
        return

    click.echo(f"已注册 {len(all_plugins)} 个 Plugin:\n")
    for p in all_plugins:
        source_label = {"builtin": "内置", "pip": "pip", "local": "本地"}.get(p.source, p.source)
        tools_count = len(p.get_tools())
        click.echo(
            f"  {p.name:16s} {p.display_name:16s} "
            f"[{source_label:4s}] {tools_count} 个 Tool"
        )


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


# ============ skills ============


@main.group()
def skills():
    """管理 Skill（知识注入）"""
    pass


@skills.command("list")
def skills_list():
    """列出所有 Skill（内置 + workspace）"""
    from openvort.plugin import PluginRegistry
    from openvort.skill.loader import SkillLoader

    registry = PluginRegistry()
    loader = SkillLoader(registry)
    loader.load_all()

    all_skills = loader.get_skills()
    if not all_skills:
        click.echo("未发现任何 Skill")
        return

    # 按来源分组
    builtin = [s for s in all_skills if s.source == "builtin"]
    workspace = [s for s in all_skills if s.source == "workspace"]

    if builtin:
        click.echo(f"\n内置 Skill ({len(builtin)}):\n")
        for s in builtin:
            status = "✅ 启用" if s.enabled else "❌ 禁用"
            click.echo(f"  {s.name:20s} {s.description[:40]:40s} {status}")

    if workspace:
        click.echo(f"\n用户 Skill ({len(workspace)}):\n")
        for s in workspace:
            status = "✅ 启用" if s.enabled else "❌ 禁用"
            click.echo(f"  {s.name:20s} {s.description[:40]:40s} {status}")

    click.echo(f"\n共 {len(all_skills)} 个 Skill")


@skills.command("enable")
@click.argument("name")
def skills_enable(name):
    """启用指定 Skill"""
    from openvort.plugin import PluginRegistry
    from openvort.skill.loader import SkillLoader

    registry = PluginRegistry()
    loader = SkillLoader(registry)
    loader.load_all()

    if loader.enable_skill(name):
        click.echo(f"✅ Skill '{name}' 已启用")
    else:
        click.echo(f"❌ 未找到 Skill '{name}'")


@skills.command("disable")
@click.argument("name")
def skills_disable(name):
    """禁用指定 Skill"""
    from openvort.plugin import PluginRegistry
    from openvort.skill.loader import SkillLoader

    registry = PluginRegistry()
    loader = SkillLoader(registry)
    loader.load_all()

    if loader.disable_skill(name):
        click.echo(f"✅ Skill '{name}' 已禁用")
    else:
        click.echo(f"❌ 未找到 Skill '{name}'")


@skills.command("create")
@click.argument("name")
def skills_create(name):
    """在 workspace 创建新 Skill 模板"""
    from openvort.plugin import PluginRegistry
    from openvort.skill.loader import SkillLoader

    registry = PluginRegistry()
    loader = SkillLoader(registry)

    path = loader.create_skill(name)
    if path:
        click.echo(f"✅ 已创建 Skill 模板: {path}")
        click.echo(f"   编辑 {path} 添加 Skill 内容，重启服务后生效")
    else:
        click.echo(f"❌ Skill '{name}' 已存在")


# ============ pairing ============


@main.group()
def pairing():
    """DM 配对管理"""
    pass


@pairing.command("approve")
@click.argument("code")
def pairing_approve(code):
    """批准配对码"""
    from openvort.core.pairing import PairingManager
    manager = PairingManager()
    ok, msg = manager.approve(code, approved_by="cli")
    click.echo(f"{'✅' if ok else '❌'} {msg}")


@pairing.command("reject")
@click.argument("code")
def pairing_reject(code):
    """拒绝配对码"""
    from openvort.core.pairing import PairingManager
    manager = PairingManager()
    ok, msg = manager.reject(code)
    click.echo(f"{'✅' if ok else '❌'} {msg}")


@pairing.command("list")
def pairing_list():
    """列出待审批的配对请求"""
    from openvort.core.pairing import PairingManager
    manager = PairingManager()
    pending = manager.list_pending()
    if not pending:
        click.echo("没有待审批的配对请求")
        return
    click.echo(f"待审批 {len(pending)} 条:\n")
    for p in pending:
        click.echo(f"  🔑 {p['code']}  {p['channel']}:{p['user_id']}  (剩余 {p['remaining_seconds']}s)")


@pairing.command("allowlist")
def pairing_allowlist():
    """查看白名单"""
    from openvort.core.pairing import PairingManager
    manager = PairingManager()
    items = manager.list_allowlist()
    if not items:
        click.echo("白名单为空")
        return
    click.echo(f"白名单 {len(items)} 条:\n")
    for item in items:
        click.echo(f"  {item['channel']}:{item['user_id']}  (by {item.get('approved_by', '?')})")


# ============ coding ============


@main.group()
def coding():
    """AI 编码环境管理"""
    pass


@coding.command("setup")
def coding_setup():
    """配置 AI 编码环境（拉取 Docker 镜像 + 配置 API Key + 验证）"""
    _run_async(_coding_setup())


async def _coding_setup():
    from openvort.core.coding_env import CodingEnvironment, EnvMode
    from openvort.plugins.vortgit.config import VortGitSettings

    click.echo("🔧 AI 编码环境配置\n")

    env = CodingEnvironment()
    settings = VortGitSettings()

    # 1. Local CLI tools check
    click.echo("── 本地 CLI 工具检测 ──")
    from openvort.plugins.vortgit.cli_runner import BUILTIN_CLI_TOOLS
    import shutil
    local_found = False
    for name, spec in BUILTIN_CLI_TOOLS.items():
        path = shutil.which(spec.binary)
        if path:
            click.echo(f"  ✅ {spec.display_name}: {path}")
            local_found = True
        else:
            click.echo(f"  ⚠️  {spec.display_name}: 未安装 ({spec.install_cmd})")

    # 2. Docker check (optional if local tools found)
    click.echo("\n── Docker 检测 ──")
    docker_ready = False
    if env._is_docker_available():
        click.echo("  ✅ Docker 已安装")
        image = settings.cli_docker_image
        click.echo(f"  📦 镜像: {image}")
        pulled = await env._is_image_pulled(image)
        if pulled:
            click.echo("  ✅ 镜像已存在")
            docker_ready = True
        else:
            click.echo("  ⏳ 正在拉取（可能需要几分钟）...")
            result = await env.pull_image()
            if result.success:
                click.echo("  ✅ 镜像拉取完成")
                docker_ready = True
            else:
                click.echo(f"  ❌ 镜像拉取失败: {result.stderr[:200]}")
    else:
        click.echo("  ⚠️  Docker 未安装（可选，已安装本地 CLI 工具即可）")

    if not local_found and not docker_ready:
        click.echo("\n❌ 无可用的编码环境。请安装 CLI 工具或 Docker：")
        click.echo("   pip install aider-chat")
        click.echo("   npm install -g @anthropic-ai/claude-code")
        return

    # 3. API Key check
    click.echo("\n── API Key 配置 ──")
    click.echo("  ℹ️  API Key 通过 Web 管理界面的「模型库」配置")
    if settings.claude_code_api_key:
        click.echo("  ✅ Claude Code API Key: 已配置（环境变量）")
    if settings.aider_api_key:
        click.echo("  ✅ Aider API Key: 已配置（环境变量）")

    # 4. Verify
    click.echo("\n── 环境验证 ──")
    status = await env.get_status()
    mode = status.mode
    if mode != EnvMode.UNAVAILABLE:
        click.echo(f"  ✅ 执行模式: {mode.value}")
    else:
        click.echo("  ❌ 环境不可用，请检查上述问题")
        return

    # 5. Test execution
    click.echo("  🧪 测试执行...", nl=False)
    test_result = await env.execute(["echo", "openvort-coding-ok"])
    if test_result.success and "openvort-coding-ok" in test_result.stdout:
        click.echo(" ✅")
    else:
        click.echo(f" ❌ {test_result.stderr[:100]}")
        return

    click.echo("\n" + "=" * 40)
    click.echo("✅ AI 编码环境准备就绪！")
    click.echo("   团队成员现在可以通过对话触发代码修改了。")


@coding.command("status")
def coding_status():
    """查看 AI 编码环境状态"""
    _run_async(_coding_status())


async def _coding_status():
    from openvort.core.coding_env import CodingEnvironment, EnvMode
    from openvort.plugins.vortgit.cli_runner import CLIRunner

    click.echo("🔍 AI 编码环境状态\n")

    env = CodingEnvironment()
    status = await env.get_status()

    click.echo("── 运行环境 ──")
    click.echo(f"  模式: {status.mode.value}")
    click.echo(f"  在 Docker 中运行: {'是' if status.running_in_docker else '否'}")
    click.echo(f"  Docker 可用: {'是' if status.docker_available else '否'}")
    click.echo(f"  Docker Socket: {'是' if status.docker_socket else '否'}")

    click.echo(f"\n── 编码沙箱镜像 ──")
    click.echo(f"  镜像: {status.coding_image_name}")
    click.echo(f"  已拉取: {'是' if status.coding_image_pulled else '否'}")

    click.echo(f"\n── CLI 编码工具 ──")
    runner = CLIRunner(env)
    for spec in runner.list_tools():
        ts = status.cli_tools.get(spec.name)
        if ts and ts.installed:
            click.echo(f"  ✅ {spec.display_name}: {ts.version or '已安装'}")
        else:
            click.echo(f"  ❌ {spec.display_name}: 未安装")
            click.echo(f"     安装: {spec.install_cmd}")

    click.echo(f"\n── API Key ──")
    for name, configured in status.api_keys.items():
        icon = "✅" if configured else "⚠️"
        label = "已配置" if configured else "未配置"
        click.echo(f"  {icon} {name}: {label}")

    if status.mode == EnvMode.UNAVAILABLE:
        click.echo(f"\n⚠️  编码环境不可用。运行: openvort coding setup")


main.add_command(coding)


# ============ doctor ============


@main.command()
def doctor():
    """诊断系统配置和连接状态"""
    _run_async(_doctor())


async def _doctor():
    from openvort.config.settings import get_settings
    from openvort.utils.logging import setup_logging

    settings = get_settings()
    setup_logging("WARNING")

    click.echo("🩺 OpenVort Doctor\n")
    issues = []

    # 1. LLM 配置检查
    click.echo("── LLM 配置 ──")
    if not settings.llm.api_key:
        issues.append("LLM API Key 未配置")
        click.echo("  ❌ API Key 未配置")
    else:
        click.echo(f"  ✅ Provider: {settings.llm.provider}")
        click.echo(f"  ✅ Model: {settings.llm.model}")
        # 尝试连接
        try:
            from openvort.core.llm import create_provider
            provider = create_provider(
                settings.llm.provider, settings.llm.api_key,
                settings.llm.api_base, timeout=10,
            )
            click.echo("  ✅ API 连接正常")
            await provider.close()
        except Exception as e:
            issues.append(f"LLM API 连接失败: {e}")
            click.echo(f"  ❌ API 连接失败: {e}")

    # 2. 数据库检查
    click.echo("\n── 数据库 ──")
    try:
        from openvort.db import init_db
        await init_db(settings.database_url)
        click.echo(f"  ✅ 数据库连接正常: {settings.database_url.split('://')[0]}")
    except Exception as e:
        issues.append(f"数据库连接失败: {e}")
        click.echo(f"  ❌ 数据库连接失败: {e}")

    # 3. 通道配置检查
    click.echo("\n── 通道配置 ──")
    from openvort.plugin import PluginLoader, PluginRegistry
    registry = PluginRegistry()
    loader = PluginLoader(registry)
    loader.load_all()

    channels = registry.list_channels()
    if not channels:
        click.echo("  ⚠️ 未发现任何 Channel 插件")
    for ch in channels:
        if ch.is_configured():
            click.echo(f"  ✅ {ch.name} ({ch.display_name}) — 已配置")
            try:
                result = await ch.test_connection()
                if result.get("ok"):
                    click.echo(f"     连接测试: ✅ {result.get('message', '')}")
                else:
                    issues.append(f"{ch.name} 连接失败: {result.get('message', '')}")
                    click.echo(f"     连接测试: ❌ {result.get('message', '')}")
            except Exception as e:
                click.echo(f"     连接测试: ⚠️ 跳过 ({e})")
        else:
            click.echo(f"  ⚠️ {ch.name} ({ch.display_name}) — 未配置")

    # 4. Relay 检查
    click.echo("\n── Relay 中继 ──")
    if settings.relay.url:
        click.echo(f"  ✅ Relay URL: {settings.relay.url}")
        if not settings.relay.secret:
            issues.append("Relay Secret 未配置（安全风险）")
            click.echo("  ⚠️ Relay Secret 未配置（建议设置鉴权密钥）")
    else:
        click.echo("  ℹ️ 未配置 Relay（使用 Webhook 或 Poll-DB 模式）")

    # 5. 安全策略检查
    click.echo("\n── 安全策略 ──")
    if not settings.contacts.admin_user_ids:
        issues.append("未配置管理员 user_id")
        click.echo("  ⚠️ 未配置管理员 user_id (OPENVORT_CONTACTS_ADMIN_USER_IDS)")
    else:
        click.echo(f"  ✅ 管理员: {settings.contacts.admin_user_ids}")

    if settings.web.enabled:
        if settings.web.default_password == "openvort":
            issues.append("Web 面板使用默认密码")
            click.echo("  ⚠️ Web 面板使用默认密码 'openvort'（建议修改 OPENVORT_WEB_DEFAULT_PASSWORD）")
        else:
            click.echo("  ✅ Web 面板密码已自定义")

    # 6. 插件检查
    click.echo("\n── 插件 ──")
    plugins = registry.list_plugins()
    tools = registry.list_tools()
    click.echo(f"  ✅ {len(plugins)} 个 Plugin, {len(tools)} 个 Tool")

    # 7. AI 编码环境
    click.echo("\n── AI 编码环境 ──")
    try:
        from openvort.core.coding_env import CodingEnvironment, EnvMode
        env = CodingEnvironment()
        status = await env.get_status()
        if status.mode != EnvMode.UNAVAILABLE:
            click.echo(f"  ✅ 模式: {status.mode.value}")
            for name, ts in status.cli_tools.items():
                if ts.installed:
                    click.echo(f"     {name}: {ts.version or '已安装'}")
            for name, configured in status.api_keys.items():
                if configured:
                    click.echo(f"     {name} API Key: 已配置")
        else:
            click.echo("  ⚠️ 未配置（可选功能）")
            click.echo("     配置后运行: openvort coding setup")
    except Exception as e:
        click.echo(f"  ⚠️ 检测跳过: {e}")

    # 总结
    click.echo("\n" + "=" * 40)
    if issues:
        click.echo(f"⚠️ 发现 {len(issues)} 个问题:\n")
        for i, issue in enumerate(issues, 1):
            click.echo(f"  {i}. {issue}")
    else:
        click.echo("✅ 一切正常！")

    try:
        from openvort.db import close_db
        await close_db()
    except Exception:
        pass


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
