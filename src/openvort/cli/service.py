"""Service commands: init, start, stop, restart."""

import os
from pathlib import Path

import click

from openvort import __version__
from openvort.cli import (
    PID_FILE,
    _check_and_kill_existing,
    _cleanup_pid,
    _graceful_kill,
    _is_process_alive,
    _run_async,
)


@click.command()
def init_cmd():
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


@click.command()
@click.option("--web/--no-web", default=None, help="启用/禁用 Web 管理面板")
def start_cmd(web):
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
    from openvort.core.engine.agent import AgentRuntime
    from openvort.core.engine.context import RequestContext
    from openvort.core.engine.session import SessionStore
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
        from openvort.core.execution.remote_node import RemoteNodeService
        from openvort.core.execution.remote_executor import register_executor
        from openvort.core.execution.docker_executor import DockerExecutor
        from openvort.core.execution.node_tools import set_node_tools_runtime
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
        from openvort.core.services.notification import init_notification_center
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
    from openvort.core.messaging.commands import CommandHandler
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
    from openvort.core.messaging.dispatcher import MessageDispatcher
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
    from openvort.core.messaging.inbox import InboxService
    inbox_service = InboxService(session_factory)

    # 配置 Channel
    import asyncio

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
                            from openvort.core.messaging.group_context import group_context_manager as gcm
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
    from openvort.core.services.scheduler import Scheduler as _Scheduler
    from openvort.core.services.schedule_service import ScheduleService as _ScheduleService

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
            from openvort.core.services.chat_message import write_chat_message
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
                from openvort.core.services.chat_message import push_unread_update
                await push_unread_update(owner_id, target_session_id)
        except Exception as e:
            log.debug(f"WebSocket 推送失败（用户可能不在线）: {e}")

        # 2. Delayed IM notification via NotificationCenter
        try:
            from openvort.core.services.notification import get_notification_center
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


@click.command()
def stop_cmd():
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


@click.command()
@click.option("--web/--no-web", default=None, help="启用/禁用 Web 管理面板")
def restart_cmd(web):
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


async def _run_bootstrap_wizard(settings, session_factory, auth_service):
    """AI 驱动的首次启动向导（CLI 对话循环）"""
    from pathlib import Path

    from openvort.core.engine.agent import AgentRuntime
    from openvort.core.bootstrap import SetupCompleteTool
    from openvort.core.engine.session import SessionStore
    from openvort.core.setup import is_initialized
    from openvort.plugin.registry import PluginRegistry

    click.echo("\n" + "=" * 50)
    click.echo("  🚀 OpenVort 首次启动向导")
    click.echo("=" * 50 + "\n")

    # Path adjusted: cli/service.py -> parent.parent -> openvort/
    prompt_path = Path(__file__).parent.parent / "core" / "prompts" / "bootstrap.md"
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
    from openvort.core.engine.context import RequestContext

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
