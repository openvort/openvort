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


def _graceful_kill(pid: int, timeout: float = 5.0) -> bool:
    """SIGTERM first, wait, then SIGKILL if needed. Returns True if process was stopped."""
    import time

    if not _is_process_alive(pid):
        return True

    try:
        os.kill(pid, signal.SIGTERM)
    except OSError:
        return True

    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if not _is_process_alive(pid):
            return True
        time.sleep(0.3)

    # Still alive — force kill
    try:
        os.kill(pid, signal.SIGKILL)
        time.sleep(0.5)
    except OSError:
        pass
    return not _is_process_alive(pid)


def _check_and_kill_existing():
    """检查并杀掉已有的 openvort 进程，写入当前 PID"""
    if PID_FILE.exists():
        try:
            old_pid = int(PID_FILE.read_text().strip())
            if old_pid != os.getpid() and _is_process_alive(old_pid):
                click.echo(f"发现已有进程 (PID={old_pid})，正在终止...")
                killed = _graceful_kill(old_pid)
                click.echo(f"已终止旧进程 (PID={old_pid})" if killed else f"警告: 旧进程 {old_pid} 未能完全退出")
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
        "# 数据库 (本地开发连接 Docker Compose 中的 PostgreSQL)",
        "OPENVORT_DATABASE_URL=postgresql+asyncpg://openvort:openvort@localhost:5432/openvort",
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
@click.option("--web/--no-web", default=None, help="启用/禁用 Web 管理面板")
def start(web):
    """启动 OpenVort 服务"""
    _run_async(_start_service(web))


async def _cleanup_duplicate_admins(session_factory):
    """Remove duplicate 'admin' members created by a historical seed bug."""
    from sqlalchemy import select, text
    from openvort.contacts.models import Member

    async with session_factory() as session:
        stmt = select(Member.id).where(Member.name == "admin").order_by(Member.created_at)
        rows = (await session.execute(stmt)).all()
        if len(rows) <= 1:
            return
        keep_id = rows[0][0]
        delete_ids = [r[0] for r in rows[1:]]
        await session.execute(text("DELETE FROM member_roles WHERE member_id = ANY(:ids)"), {"ids": delete_ids})
        await session.execute(text("DELETE FROM members WHERE id = ANY(:ids)"), {"ids": delete_ids})
        await session.commit()
        from openvort.utils.logging import get_logger
        get_logger("cli").info(f"已清理 {len(delete_ids)} 条重复 admin 记录")


async def _start_service(web_flag: bool | None):
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

    # 清理可能由历史 bug 产生的重复 admin 记录
    await _cleanup_duplicate_admins(session_factory)

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

    # Initialize remote work node service and register executors
    try:
        from openvort.core.remote_node import RemoteNodeService
        from openvort.core.remote_executor import register_executor
        from openvort.core.docker_executor import DockerExecutor
        from openvort.core.node_tools import set_node_tools_runtime
        register_executor("docker", DockerExecutor())
        remote_node_service = RemoteNodeService(session_factory)
        set_node_tools_runtime(remote_node_service, session_factory)
    except Exception as e:
        log.warning(f"远程工作节点服务初始化失败: {e}")

    # Initialize TaskRunner for async agent execution
    try:
        from openvort.core.task_runner import init_task_runner
        task_runner = init_task_runner(session_factory)
        await task_runner.recover_on_startup()
        log.info("AgentTaskRunner 已初始化")
    except Exception as e:
        log.warning(f"TaskRunner 初始化失败: {e}")

    # Initialize NotificationCenter for delayed IM delivery
    try:
        from openvort.core.notification import init_notification_center
        notif_center = init_notification_center(session_factory, registry)
        await notif_center.recover_on_startup()
        log.info("NotificationCenter 已初始化")
    except Exception as e:
        log.warning(f"NotificationCenter 初始化失败: {e}")

    # 加载 Skill（知识注入，DB 驱动）
    from openvort.skill.loader import SkillLoader
    skill_loader = SkillLoader(registry)
    await skill_loader.load_all(session_factory)

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
    await config_service.apply_org_to_settings()
    await config_service.apply_web_to_settings()

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

    # 初始化 ASR 服务（用于语音消息转写）
    from openvort.services.asr import ASRService
    asr_service = ASRService(session_factory)
    await asr_service.load_providers()
    if asr_service._providers:
        log.info(f"已加载 {len(asr_service._providers)} 个 ASR Provider 用于语音识别")
    else:
        log.info("未配置 ASR Provider，语音消息将无法识别")

    # 初始化 TTS 服务（用于语音消息发送）
    from openvort.services.tts import TTSService
    tts_service = TTSService(session_factory)
    await tts_service.load_providers()
    if tts_service.available:
        log.info("TTS 服务已就绪，语音发送功能可用")
    else:
        log.info("未配置 TTS Provider，语音发送功能不可用")

    # 初始化 Embedding 服务（用于知识库向量检索）
    from openvort.services.embedding import EmbeddingService
    embedding_service = EmbeddingService(session_factory)
    await embedding_service.load_providers()
    if embedding_service.available:
        log.info("Embedding 服务已就绪，知识库检索功能可用")
    else:
        log.info("未配置 Embedding Provider，知识库检索功能不可用")

    # 将 TTS 服务注入到语音发送工具
    voice_tool = registry.get_tool("wecom_send_voice")
    if voice_tool and hasattr(voice_tool, "set_tts_service"):
        voice_tool.set_tts_service(tts_service)
    feishu_voice_tool = registry.get_tool("feishu_send_voice")
    if feishu_voice_tool and hasattr(feishu_voice_tool, "set_tts_service"):
        feishu_voice_tool.set_tts_service(tts_service)
    dingtalk_voice_tool = registry.get_tool("dingtalk_send_voice")
    if dingtalk_voice_tool and hasattr(dingtalk_voice_tool, "set_tts_service"):
        dingtalk_voice_tool.set_tts_service(tts_service)

    # 初始化 InboxService（IM 跨实例消息去重）
    from openvort.core.inbox import InboxService
    inbox_service = InboxService(session_factory)

    # 配置 Channel
    channels = registry.list_channels()
    for ch in channels:
        if hasattr(ch, "set_inbox_service"):
            ch.set_inbox_service(inbox_service)
    for ch in channels:
        if ch.name == "wecom" and ch.is_configured():
            _ch = ch  # 闭包捕获
            if hasattr(_ch, "set_asr_service"):
                _ch.set_asr_service(asr_service)

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

            # Bot mode runs alongside other modes (separate message source)
            if ch.is_bot_configured():
                async def bot_stream_handler(msg):
                    from openvort.core.setup import is_initialized as _is_init
                    if not await _is_init(session_factory):
                        yield {"type": "text", "text": "系统正在初始化中，请稍后再试。"}
                        return

                    # Determine session scope: group chats use chat_id
                    raw = getattr(msg, "raw", None) or {}
                    chat_type = raw.get("_bot_chat_type", "single")
                    chat_id = raw.get("_bot_chat_id", "")
                    is_group = chat_type != "single" and bool(chat_id)
                    session_uid = f"group:{chat_id}" if is_group else msg.sender_id

                    cmd_result = await command_handler.handle(msg.channel, session_uid, msg.content)
                    if cmd_result.handled:
                        if cmd_result.reply:
                            yield {"type": "text", "text": cmd_result.reply}
                        return

                    ctx = await build_context(msg.channel, msg.sender_id)
                    ctx.images = getattr(msg, "images", []) or []

                    content = msg.content
                    if is_group:
                        ctx.user_id = session_uid
                        ctx.group_id = chat_id
                        sender_name = ctx.member.name if ctx.member else msg.sender_id
                        content = f"[{sender_name}]: {content}"

                        try:
                            from openvort.core.group_context import group_context_manager as gcm
                            await gcm.get_or_create(chat_id, msg.channel)
                            ctx.group_prompt = await gcm.build_group_prompt(chat_id)
                        except Exception as e:
                            log.warning(f"群聊上下文加载失败: {e}")

                    async for event in agent.process_stream_im(ctx, content):
                        yield event

                _ch.set_stream_handler(bot_stream_handler)
                await ch.start_bot()

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

        # ---- DingTalk Channel (Stream mode) ----
        if ch.name == "dingtalk" and ch.is_configured():
            from openvort.channels.dingtalk.channel import DingTalkChannel as _DingTalkCh
            _dt_ch: _DingTalkCh = ch  # type: ignore[assignment]

            async def dingtalk_stream_handler(msg):
                from openvort.core.setup import is_initialized as _is_init
                if not await _is_init(session_factory):
                    yield {"type": "text", "text": "系统正在初始化中，请稍后再试。"}
                    return

                cmd_result = await command_handler.handle(msg.channel, msg.sender_id, msg.content)
                if cmd_result.handled:
                    if cmd_result.reply:
                        yield {"type": "text", "text": cmd_result.reply}
                    return

                ctx = await build_context(msg.channel, msg.sender_id)
                ctx.images = getattr(msg, "images", []) or []

                async for event in agent.process_stream_im(ctx, msg.content):
                    yield event

            async def handle_dingtalk_message(msg):
                from openvort.core.setup import is_initialized as _is_init
                if not await _is_init(session_factory):
                    return "系统正在初始化中，请稍后再试。"

                cmd_result = await command_handler.handle(msg.channel, msg.sender_id, msg.content)
                if cmd_result.handled:
                    return cmd_result.reply

                ctx = await build_context(msg.channel, msg.sender_id)
                ctx.images = getattr(msg, "images", []) or []

                async def process_fn(ctx_, content_):
                    return await agent.process(ctx_, content_)

                async def send_fn(reply_):
                    log.info(f"钉钉回复: {reply_[:50]}")
                    from openvort.plugin.base import Message as Msg
                    await _dt_ch.send(msg.sender_id, Msg(content=reply_, channel="dingtalk", raw=msg.raw))

                reply = await dispatcher.dispatch(ctx, msg.content, process_fn, send_fn)
                return reply

            _dt_ch.set_stream_handler(dingtalk_stream_handler)
            _dt_ch.on_message(handle_dingtalk_message)

            if _dt_ch.is_stream_configured():
                await _dt_ch.start_stream()
            else:
                await _dt_ch.start()

        # ---- Feishu Channel (WebSocket mode) ----
        if ch.name == "feishu" and ch.is_configured():
            from openvort.channels.feishu.channel import FeishuChannel as _FeishuCh
            _fs_ch: _FeishuCh = ch  # type: ignore[assignment]
            if hasattr(_fs_ch, "set_asr_service"):
                _fs_ch.set_asr_service(asr_service)

            async def feishu_stream_handler(msg):
                from openvort.core.setup import is_initialized as _is_init
                if not await _is_init(session_factory):
                    yield {"type": "text", "text": "系统正在初始化中，请稍后再试。"}
                    return

                cmd_result = await command_handler.handle(msg.channel, msg.sender_id, msg.content)
                if cmd_result.handled:
                    if cmd_result.reply:
                        yield {"type": "text", "text": cmd_result.reply}
                    return

                ctx = await build_context(msg.channel, msg.sender_id)
                ctx.images = getattr(msg, "images", []) or []

                async for event in agent.process_stream_im(ctx, msg.content):
                    yield event

            async def handle_feishu_message(msg):
                from openvort.core.setup import is_initialized as _is_init
                if not await _is_init(session_factory):
                    return "系统正在初始化中，请稍后再试。"

                cmd_result = await command_handler.handle(msg.channel, msg.sender_id, msg.content)
                if cmd_result.handled:
                    return cmd_result.reply

                ctx = await build_context(msg.channel, msg.sender_id)
                ctx.images = getattr(msg, "images", []) or []

                async def process_fn(ctx_, content_):
                    return await agent.process(ctx_, content_)

                async def send_fn(reply_):
                    log.info(f"飞书回复: {reply_[:50]}")
                    from openvort.plugin.base import Message as Msg
                    await _fs_ch.send(msg.sender_id, Msg(content=reply_, channel="feishu", raw=msg.raw))

                reply = await dispatcher.dispatch(ctx, msg.content, process_fn, send_fn)
                return reply

            _fs_ch.set_stream_handler(feishu_stream_handler)
            _fs_ch.on_message(handle_feishu_message)

            if _fs_ch.is_ws_configured():
                await _fs_ch.start_ws()
            else:
                await _fs_ch.start()

    # Determine wecom mode(s) for logging
    _modes = []
    _wecom_ch = registry.get_channel("wecom")
    if _wecom_ch and hasattr(_wecom_ch, "_bot_mode") and _wecom_ch._bot_mode:
        _modes.append("bot")
    _modes.append("webhook")
    mode = "+".join(_modes)
    log.info(f"已加载 {len(channels)} 个 Channel, {len(registry.list_tools())} 个 Tool (模式: {mode})")

    # ---- 定时任务调度器 ----
    from openvort.core.scheduler import Scheduler as _Scheduler
    from openvort.core.schedule_service import ScheduleService as _ScheduleService

    async def _schedule_notify(
        owner_id: str,
        job_name: str,
        result_text: str,
        executor_member=None,
        job_id: str = "",
        status: str = "success",
        tool_messages: dict | None = None,
    ):
        """Push scheduled task result to the job owner via WebSocket and IM channels."""
        from openvort.plugin.base import Message as _Msg

        # 确定执行人名称和身份
        executor_name = "系统助手"
        is_ai_employee = False
        if executor_member and hasattr(executor_member, "is_virtual") and executor_member.is_virtual:
            executor_name = executor_member.name or "AI 员工"
            is_ai_employee = True

        # 构建消息前缀
        if is_ai_employee:
            prefix = f"【AI 员工·{executor_name}】已完成任务「{job_name}」\n\n"
        else:
            prefix = f"【定时任务】已完成任务「{job_name}」\n\n"

        full_message = prefix + result_text[:3000]  # 限制总长度

        # 0. Persist to chat_messages + bump unread_count
        target_session_id = ""
        try:
            from openvort.core.chat_message import write_chat_message
            from sqlalchemy import select as _sel
            from openvort.db.models import ChatSession

            if is_ai_employee and executor_member:
                async with session_factory() as _s:
                    stmt = _sel(ChatSession).where(
                        ChatSession.user_id == owner_id,
                        ChatSession.channel == "web",
                        ChatSession.target_type == "member",
                        ChatSession.target_id == executor_member.id,
                        ChatSession.hidden == False,  # noqa: E712
                    )
                    session_obj = (await _s.execute(stmt)).scalar_one_or_none()
                    if not session_obj:
                        # Auto-create session for this AI employee
                        session_obj = ChatSession(
                            channel="web",
                            user_id=owner_id,
                            session_id=__import__("uuid").uuid4().hex[:8],
                            title=executor_member.name or "AI 员工",
                            messages="[]",
                            target_type="member",
                            target_id=executor_member.id,
                        )
                        _s.add(session_obj)
                        await _s.flush()

                    target_session_id = session_obj.session_id

                    # Build metadata_json with tool_calls for screenshot persistence
                    meta = {}
                    if tool_messages and tool_messages.get("tool_uses"):
                        result_map: dict[str, str] = {}
                        for tr in tool_messages.get("tool_results", []):
                            result_map[tr.get("tool_use_id", "")] = tr.get("content", "")
                        meta["tool_calls"] = [
                            {
                                "name": tu.get("name", ""),
                                "id": tu.get("id", ""),
                                "status": "done",
                                "output": result_map.get(tu.get("id", ""), ""),
                            }
                            for tu in tool_messages["tool_uses"]
                        ]

                    await write_chat_message(
                        _s,
                        session_id=target_session_id,
                        owner_id=owner_id,
                        sender_type="assistant",
                        sender_id=executor_member.id,
                        content=full_message,
                        metadata_json=__import__("json").dumps(meta, ensure_ascii=False) if meta else "{}",
                        source="schedule",
                        is_read=False,
                        increment_unread=True,
                    )
                    await _s.commit()
        except Exception as e:
            log.warning(f"Failed to persist schedule result to chat_messages: {e}")

        # 0.5 Inject into SessionStore so the message persists in chat history
        if target_session_id and is_ai_employee:
            try:
                msgs = await session_store.get_messages("web", owner_id, target_session_id)
                if tool_messages and tool_messages.get("tool_uses"):
                    # Inject structured assistant message (tool_use blocks + text)
                    # so /chat/history can parse tool_calls and screenshots
                    content_blocks = list(tool_messages["tool_uses"])
                    content_blocks.append({"type": "text", "text": full_message})
                    msgs.append({"role": "assistant", "content": content_blocks})
                    if tool_messages.get("tool_results"):
                        msgs.append({"role": "user", "content": list(tool_messages["tool_results"])})
                else:
                    msgs.append({"role": "assistant", "content": full_message})
                await session_store.save_messages("web", owner_id, msgs, target_session_id)
            except Exception as e:
                log.debug(f"注入 SessionStore 失败: {e}")

        # 1. WebSocket push (web UI)
        try:
            from openvort.web.ws import manager as ws_manager

            severity = "error" if status == "failed" else "info"
            actions = [
                {"label": "重新执行", "action": "rerun", "job_id": job_id},
                {"label": "查看详情", "action": "view_detail", "job_id": job_id},
            ] if job_id else []

            await ws_manager.send_to(owner_id, {
                "type": "schedule_result",
                "job_id": job_id,
                "job_name": job_name,
                "result": result_text[:2000],
                "executor_name": executor_name,
                "is_ai_employee": is_ai_employee,
                "severity": severity,
                "actions": actions,
            })

            if is_ai_employee and executor_member and target_session_id:
                await ws_manager.send_to(owner_id, {
                    "type": "message",
                    "session_id": target_session_id,
                    "sender_type": "member",
                    "sender_id": executor_member.id,
                    "sender_name": executor_name,
                    "content": full_message,
                    "from_schedule": True,
                    "job_id": job_id,
                    "job_name": job_name,
                })
                from openvort.core.chat_message import push_unread_update
                await push_unread_update(owner_id, target_session_id)
        except Exception as e:
            log.debug(f"WebSocket 推送失败（用户可能不在线）: {e}")

        # 2. Delayed IM notification via NotificationCenter
        try:
            from openvort.core.notification import get_notification_center
            nc = get_notification_center()
            if nc:
                await nc.schedule_notify(
                    recipient_id=owner_id,
                    source="schedule",
                    source_id=job_id,
                    session_id=target_session_id,
                    title=f"{executor_name} {'完成' if status == 'success' else '执行失败'}了「{job_name}」",
                    summary=result_text[:300],
                    severity="error" if status == "failed" else "info",
                )
        except Exception as e:
            log.warning(f"NotificationCenter 调度失败: {e}")

    _scheduler = _Scheduler()
    _scheduler.start()

    # im_inbox periodic cleanup (every hour, delete entries older than 24h)
    async def _im_inbox_cleanup():
        await inbox_service.cleanup(max_age_hours=24)
    _scheduler.add_interval("im_inbox_cleanup", _im_inbox_cleanup, seconds=3600)

    schedule_service = _ScheduleService(session_factory, _scheduler, agent, notify_fn=_schedule_notify)
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

            # 初始化 MarketplaceInstaller（如果启用）
            marketplace_installer = None
            if settings.marketplace.enabled:
                from openvort.marketplace import MarketplaceClient, MarketplaceInstaller
                mkt_client = MarketplaceClient(base_url=settings.marketplace.url)
                marketplace_installer = MarketplaceInstaller(mkt_client, session_factory, registry, data_dir=settings.data_dir)

            # 注入运行时依赖
            set_runtime(agent, registry, session_store, session_factory,
                        auth_service=auth_service, build_context_fn=build_context,
                        skill_loader=skill_loader, config_service=config_service,
                        schedule_service=schedule_service,
                        embedding_service=embedding_service,
                        marketplace_installer=marketplace_installer)
            install_log_handler()

            web_app = create_app()
            try:
                _feishu_ch = registry.get_channel("feishu")
                if _feishu_ch and _feishu_ch.is_configured():
                    from openvort.channels.feishu.callback import create_feishu_callback_router

                    web_app.include_router(create_feishu_callback_router(_feishu_ch), tags=["feishu-callback"])
                    log.info("已挂载飞书回调路由: /callback/feishu")
            except Exception as e:
                log.warning(f"挂载飞书回调路由失败: {e}")

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
        except ImportError as ie:
            log.warning(f"未安装 uvicorn/fastapi，Web 面板未启动。运行 pip install uvicorn fastapi 安装。ImportError: {ie}")
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


# ============ stop / restart ============


@main.command()
def stop():
    """停止 OpenVort 服务"""
    if not PID_FILE.exists():
        click.echo("未发现运行中的 OpenVort 进程（PID 文件不存在）")
        return

    try:
        pid = int(PID_FILE.read_text().strip())
    except (ValueError, OSError):
        click.echo("PID 文件损坏，已清理")
        PID_FILE.unlink(missing_ok=True)
        return

    if not _is_process_alive(pid):
        click.echo(f"进程 {pid} 已不存在，清理 PID 文件")
        PID_FILE.unlink(missing_ok=True)
        return

    click.echo(f"正在停止 OpenVort (PID={pid}) ...")
    killed = _graceful_kill(pid)
    if killed:
        PID_FILE.unlink(missing_ok=True)
        click.echo("已停止")
    else:
        click.echo(f"警告: 进程 {pid} 未能完全退出，请手动 kill -9 {pid}")


@main.command()
@click.option("--web/--no-web", default=None, help="启用/禁用 Web 管理面板")
def restart(web):
    """重启 OpenVort 服务（stop + start）"""
    if PID_FILE.exists():
        try:
            pid = int(PID_FILE.read_text().strip())
            if _is_process_alive(pid):
                click.echo(f"正在停止旧进程 (PID={pid}) ...")
                killed = _graceful_kill(pid)
                if killed:
                    PID_FILE.unlink(missing_ok=True)
                    click.echo("旧进程已停止")
                else:
                    click.echo(f"警告: 旧进程 {pid} 未能退出，尝试强制启动...")
        except (ValueError, OSError):
            pass

    click.echo("正在启动...")
    _run_async(_start_service(web))


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
                f"自动关联 {stats['matched']}, 待确认 {stats['pending']}, "
                f"跳过 {stats.get('skipped', 0)}"
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


# ============ marketplace ============


@main.group()
def marketplace():
    """扩展市场（从 openvort.com 安装 Skill/Plugin）"""
    pass


@marketplace.command("search")
@click.argument("query", default="")
@click.option("--type", "-t", "ext_type", default="all", help="Filter: all/skill/plugin")
@click.option("--limit", "-n", default=10, help="Max results")
def marketplace_search(query, ext_type, limit):
    """搜索扩展市场"""
    _run_async(_marketplace_search(query, ext_type, limit))


async def _marketplace_search(query: str, ext_type: str, limit: int):
    from openvort.marketplace.client import MarketplaceClient
    from openvort.config.settings import get_settings

    settings = get_settings()
    client = MarketplaceClient(base_url=settings.marketplace.url)

    try:
        result = await client.search(query=query, type=ext_type, limit=limit)
        items = result.get("items", [])
        total = result.get("total", 0)
        if not items:
            click.echo("未找到相关扩展")
            return

        click.echo(f"找到 {total} 个扩展:\n")
        for item in items:
            t = "Plugin" if item.get("type") == "plugin" else "Skill"
            name = item.get("displayName", item.get("name", "?"))
            author = item.get("author", "?")
            ver = item.get("version", "?")
            dl = item.get("downloads", 0)
            click.echo(f"  [{t:6s}] {name:30s} by {author:16s} v{ver}  ({dl} downloads)")
    finally:
        await client.close()


@marketplace.command("install")
@click.argument("ext_type", type=click.Choice(["skill", "plugin"]))
@click.argument("ref")
def marketplace_install(ext_type, ref):
    """安装扩展 (openvort marketplace install skill author/slug)"""
    _run_async(_marketplace_install(ext_type, ref))


async def _marketplace_install(ext_type: str, ref: str):
    from openvort.config.settings import get_settings
    from openvort.marketplace.client import MarketplaceClient
    from openvort.marketplace.installer import MarketplaceInstaller
    from openvort.plugin.registry import PluginRegistry
    from openvort.db import init_db

    settings = get_settings()
    session_factory = await init_db(settings.database_url)

    client = MarketplaceClient(base_url=settings.marketplace.url)
    registry = PluginRegistry()
    installer = MarketplaceInstaller(client, session_factory, registry, data_dir=settings.data_dir)

    parts = ref.split("/", 1)
    author = parts[0] if len(parts) > 1 else ""
    slug = parts[-1]

    try:
        if ext_type == "skill":
            result = await installer.install_skill(slug, author=author)
            method = " (bundle)" if result.get("has_bundle") else ""
            click.echo(f"Skill 安装成功{method}: {result['name']} v{result['version']}")
        else:
            result = await installer.install_plugin(slug, author=author)
            method = result.get("method", "pip")
            name = result.get("packageName", result.get("slug", slug))
            click.echo(f"Plugin 安装成功 ({method}): {name} v{result['version']}")
            if result.get("restart_required"):
                click.echo("  需要重启 OpenVort 服务以加载新插件")
    except Exception as e:
        click.echo(f"安装失败: {e}", err=True)
    finally:
        await client.close()
        from openvort.db import close_db
        await close_db()


@marketplace.command("list")
def marketplace_list():
    """列出已安装的市场扩展"""
    _run_async(_marketplace_list())


async def _marketplace_list():
    from openvort.config.settings import get_settings
    from openvort.marketplace.client import MarketplaceClient
    from openvort.marketplace.installer import MarketplaceInstaller
    from openvort.plugin.registry import PluginRegistry
    from openvort.db import init_db

    settings = get_settings()
    session_factory = await init_db(settings.database_url)

    client = MarketplaceClient(base_url=settings.marketplace.url)
    registry = PluginRegistry()
    installer = MarketplaceInstaller(client, session_factory, registry, data_dir=settings.data_dir)

    try:
        items = await installer.list_installed()
        if not items:
            click.echo("未安装任何市场扩展")
            return

        click.echo(f"已安装 {len(items)} 个市场扩展:\n")
        for item in items:
            status = "启用" if item.get("enabled") else "禁用"
            click.echo(
                f"  {item['name']:24s} {item.get('author', ''):16s}/"
                f"{item.get('slug', ''):20s} v{item.get('version', '?')}  [{status}]"
            )
    finally:
        await client.close()
        from openvort.db import close_db
        await close_db()


@marketplace.command("uninstall")
@click.argument("slug")
def marketplace_uninstall(slug):
    """卸载市场扩展"""
    _run_async(_marketplace_uninstall(slug))


async def _marketplace_uninstall(slug: str):
    from openvort.config.settings import get_settings
    from openvort.marketplace.client import MarketplaceClient
    from openvort.marketplace.installer import MarketplaceInstaller
    from openvort.plugin.registry import PluginRegistry
    from openvort.db import init_db

    settings = get_settings()
    session_factory = await init_db(settings.database_url)

    client = MarketplaceClient(base_url=settings.marketplace.url)
    registry = PluginRegistry()
    installer = MarketplaceInstaller(client, session_factory, registry, data_dir=settings.data_dir)

    try:
        result = await installer.uninstall_skill(slug)
        click.echo(f"已卸载: {result['name']} ({slug})")
    except ValueError as e:
        click.echo(f"卸载失败: {e}", err=True)
    finally:
        await client.close()
        from openvort.db import close_db
        await close_db()


@marketplace.command("update")
def marketplace_update():
    """检查并更新市场扩展"""
    _run_async(_marketplace_update())


async def _marketplace_update():
    from openvort.config.settings import get_settings
    from openvort.marketplace.client import MarketplaceClient
    from openvort.marketplace.installer import MarketplaceInstaller
    from openvort.plugin.registry import PluginRegistry
    from openvort.db import init_db

    settings = get_settings()
    session_factory = await init_db(settings.database_url)

    client = MarketplaceClient(base_url=settings.marketplace.url)
    registry = PluginRegistry()
    installer = MarketplaceInstaller(client, session_factory, registry, data_dir=settings.data_dir)

    try:
        updates = await installer.check_updates()
        if not updates:
            click.echo("所有市场扩展均为最新版本")
            return

        click.echo(f"发现 {len(updates)} 个可更新:\n")
        for u in updates:
            extra = " (hash changed)" if u.get("hash_changed") else ""
            click.echo(f"  [{u.get('type', 'skill'):6s}] {u['name']:24s} {u['local_version']} -> {u['remote_version']}{extra}")

        if click.confirm("\n是否全部更新?"):
            for u in updates:
                try:
                    if u.get("type") == "plugin":
                        result = await installer.install_plugin(u["slug"])
                    else:
                        result = await installer.install_skill(u["slug"])
                    click.echo(f"  已更新: {result.get('name', u['slug'])} v{result.get('version', '?')}")
                except Exception as e:
                    click.echo(f"  更新 {u['slug']} 失败: {e}")
    finally:
        await client.close()
        from openvort.db import close_db
        await close_db()


@marketplace.command("publish")
@click.argument("folder", type=click.Path(exists=True, file_okay=False))
@click.option("--type", "-t", "ext_type", default="auto", help="Extension type: auto/skill/plugin")
@click.option("--slug", "-s", default="", help="Extension slug (default: folder name)")
@click.option("--username", "-u", default="", help="Marketplace username")
@click.option("--password", "-p", default="", help="Marketplace password (or set OPENVORT_MARKETPLACE_TOKEN)")
def marketplace_publish(folder, ext_type, slug, username, password):
    """发布本地文件夹到扩展市场 (openvort marketplace publish ./my-skill)"""
    _run_async(_marketplace_publish(folder, ext_type, slug, username, password))


async def _marketplace_publish(folder: str, ext_type: str, slug: str, username: str, password: str):
    import os
    import tempfile
    import zipfile
    import hashlib
    from pathlib import Path
    from openvort.config.settings import get_settings
    from openvort.marketplace.client import MarketplaceClient

    settings = get_settings()
    folder_path = Path(folder).resolve()
    slug = slug or folder_path.name.lower().replace("_", "-").replace(" ", "-")

    # Auto-detect type
    if ext_type == "auto":
        skill_md = _find_publish_file(folder_path, "SKILL.md")
        pyproject = folder_path / "pyproject.toml"
        setup_py = folder_path / "setup.py"
        if skill_md:
            ext_type = "skill"
        elif pyproject.exists() or setup_py.exists():
            ext_type = "plugin"
        else:
            ext_type = "skill"
        click.echo(f"自动检测类型: {ext_type}")

    # Read metadata
    skill_md_path = _find_publish_file(folder_path, "SKILL.md")
    readme_path = _find_publish_file(folder_path, "README.md")
    manifest_path = folder_path / "manifest.json"

    content = ""
    readme = ""
    manifest: dict = {}

    if skill_md_path:
        content = skill_md_path.read_text(encoding="utf-8")
        click.echo(f"  读取 SKILL.md ({len(content)} chars)")
    if readme_path:
        readme = readme_path.read_text(encoding="utf-8")
        click.echo(f"  读取 README.md ({len(readme)} chars)")
    if manifest_path.exists():
        import json
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        click.echo(f"  读取 manifest.json")

    # Package to zip
    with tempfile.NamedTemporaryFile(suffix=".zip", delete=False) as tmp:
        tmp_path = Path(tmp.name)

    with zipfile.ZipFile(tmp_path, "w", zipfile.ZIP_DEFLATED) as zf:
        for p in folder_path.rglob("*"):
            if p.is_file():
                rel = p.relative_to(folder_path)
                # Skip common unwanted files
                parts = rel.parts
                if any(part.startswith(".") for part in parts):
                    continue
                if any(part in ("__pycache__", "node_modules", ".git", ".venv", "venv") for part in parts):
                    continue
                zf.write(p, rel)

    zip_size = tmp_path.stat().st_size
    zip_hash = hashlib.sha256(tmp_path.read_bytes()).hexdigest()
    click.echo(f"  打包完成: {zip_size / 1024:.1f} KB, SHA-256: {zip_hash[:16]}...")

    # Auth
    token = ""
    if username and password:
        import base64
        token = base64.b64encode(f"{username}:{password}".encode()).decode()
    elif os.environ.get("OPENVORT_MARKETPLACE_TOKEN"):
        token = os.environ["OPENVORT_MARKETPLACE_TOKEN"]

    if not token:
        username = click.prompt("Marketplace 用户名")
        password = click.prompt("Marketplace 密码", hide_input=True)
        import base64
        token = base64.b64encode(f"{username}:{password}".encode()).decode()

    client = MarketplaceClient(base_url=settings.marketplace.url, token=token)

    try:
        click.echo("上传 Bundle...")
        bundle_info = await client.upload_bundle(slug, ext_type, tmp_path)
        click.echo(f"  Bundle 上传成功: {bundle_info.get('bundleUrl', '')}")

        # Build extension body
        display_name = manifest.get("displayName", slug.replace("-", " ").title())
        body = {
            "type": ext_type,
            "slug": slug,
            "name": slug,
            "displayName": display_name,
            "description": manifest.get("description", ""),
            "readme": readme,
            "content": content,
            "version": manifest.get("version", "1.0.0"),
            "icon": manifest.get("icon", "i-heroicons-academic-cap" if ext_type == "skill" else "i-heroicons-puzzle-piece"),
            "category": manifest.get("category", "general"),
            "tags": manifest.get("tags", []),
            "license": manifest.get("license", "MIT-0"),
            "homepage": manifest.get("homepage", ""),
            "repository": manifest.get("repository", ""),
            "bundleUrl": bundle_info.get("bundleUrl"),
            "bundleHash": bundle_info.get("bundleHash"),
            "bundleSize": bundle_info.get("bundleSize"),
        }

        if ext_type == "skill":
            body["skillType"] = manifest.get("skillType", "workflow")
        elif ext_type == "plugin":
            body["packageName"] = manifest.get("packageName", "")
            body["entryPoint"] = manifest.get("entryPoint", "")
            body["pythonRequires"] = manifest.get("pythonRequires", "")
            body["dependencies"] = manifest.get("dependencies", [])
            body["toolsCount"] = manifest.get("toolsCount", 0)
            body["promptsCount"] = manifest.get("promptsCount", 0)
            body["configSchema"] = manifest.get("configSchema", [])

        body["compatVersion"] = manifest.get("compatVersion", "")

        click.echo("发布扩展...")
        result = await client.publish_extension(body)
        click.echo(f"\n发布成功! {result.get('author', '')}/{result.get('slug', slug)}")
        click.echo(f"  版本: v{result.get('version', '1.0.0')}")
        click.echo(f"  查看: {settings.marketplace.url.replace('/api', '')}/{result.get('author', '')}/{result.get('slug', slug)}")
    except Exception as e:
        click.echo(f"发布失败: {e}", err=True)
        raise SystemExit(1)
    finally:
        await client.close()
        tmp_path.unlink(missing_ok=True)


@marketplace.command("sync")
@click.option("--all", "sync_all", is_flag=True, help="Sync all installed marketplace extensions")
def marketplace_sync(sync_all):
    """同步已安装的市场扩展（检查更新并自动安装）"""
    _run_async(_marketplace_sync(sync_all))


async def _marketplace_sync(sync_all: bool):
    from openvort.config.settings import get_settings
    from openvort.marketplace.client import MarketplaceClient
    from openvort.marketplace.installer import MarketplaceInstaller
    from openvort.plugin.registry import PluginRegistry
    from openvort.db import init_db

    settings = get_settings()
    session_factory = await init_db(settings.database_url)

    client = MarketplaceClient(base_url=settings.marketplace.url)
    registry = PluginRegistry()
    installer = MarketplaceInstaller(client, session_factory, registry, data_dir=settings.data_dir)

    try:
        updates = await installer.check_updates()
        if not updates:
            click.echo("所有扩展已是最新版本")
            return

        click.echo(f"发现 {len(updates)} 个更新:\n")
        for u in updates:
            extra = " [content changed]" if u.get("hash_changed") else ""
            click.echo(f"  [{u.get('type', 'skill'):6s}] {u['name']:24s} {u['local_version']} -> {u['remote_version']}{extra}")

        if sync_all or click.confirm("\n是否全部更新?"):
            for u in updates:
                try:
                    if u.get("type") == "plugin":
                        result = await installer.install_plugin(u["slug"])
                    else:
                        result = await installer.install_skill(u["slug"])
                    click.echo(f"  已同步: {result.get('name', u['slug'])} v{result.get('version', '?')}")
                except Exception as e:
                    click.echo(f"  同步 {u['slug']} 失败: {e}")
    finally:
        await client.close()
        from openvort.db import close_db
        await close_db()


def _find_publish_file(folder: Path, name: str) -> Path | None:
    """Find a file by name (case-insensitive) in the folder root."""
    lower = name.lower()
    for p in folder.iterdir():
        if p.is_file() and p.name.lower() == lower:
            return p
    return None


# ============ skills ============


@main.group()
def skills():
    """管理 Skill（知识注入）"""
    pass


@skills.command("list")
def skills_list():
    """列出所有内置 Skill"""
    from openvort.skill.loader import _parse_skill_file
    builtin_dir = Path(__file__).parent / "skills"
    if not builtin_dir.exists():
        click.echo("未发现任何 Skill")
        return

    count = 0
    for skill_dir in sorted(builtin_dir.iterdir()):
        if not skill_dir.is_dir():
            continue
        skill_file = skill_dir / "SKILL.md"
        if not skill_file.exists():
            continue
        parsed = _parse_skill_file(skill_file)
        if parsed:
            status = "✅ 启用" if parsed["enabled"] else "❌ 禁用"
            click.echo(f"  {parsed['name']:20s} {parsed['description'][:40]:40s} {status}")
            count += 1

    click.echo(f"\n共 {count} 个内置 Skill")
    click.echo("公共和个人 Skill 请通过 Web 管理面板管理")


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
    click.echo("\n── 数据库 (PostgreSQL) ──")
    db_url = settings.database_url
    click.echo(f"  URL: {db_url.split('@')[-1] if '@' in db_url else db_url.split('://')[0]}")
    try:
        from openvort.db import init_db, get_session
        await init_db(db_url)
        async with get_session() as session:
            from sqlalchemy import text
            row = await session.execute(text("SELECT version()"))
            pg_version = row.scalar()
            click.echo(f"  ✅ 连接正常: {pg_version}")
    except Exception as e:
        issues.append(f"数据库连接失败: {e}")
        click.echo(f"  ❌ 连接失败: {e}")
        click.echo("     提示: docker compose -f docker-compose.dev.yml up -d 可启动本地 PostgreSQL")

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

    # 4. 安全策略检查
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
