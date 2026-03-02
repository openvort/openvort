"""
Agent Runtime

基于 LLM tool use 的 agentic loop。
支持多 Provider（Anthropic/OpenAI/DeepSeek 等）+ Failover。
不依赖 LangChain 等框架，保持轻量可控。
"""

import asyncio

from openvort.config.settings import LLMSettings
from openvort.core.context import RequestContext
from openvort.core.llm import LLMClient, LLMResponse, TextBlock, ToolUseBlock, Usage
from openvort.core.session import SessionStore
from openvort.plugin.registry import PluginRegistry
from openvort.utils.logging import get_logger

log = get_logger("core.agent")

# Agent 系统提示词
SYSTEM_PROMPT = """你是 OpenVort 助手，一个智能研发工作流引擎。

你的职责：
- 理解用户通过 IM（企业微信等）发来的消息
- 根据用户意图，调用合适的工具完成任务
- 用中文回复，语气友好专业，简洁明了
- 如果没有合适的工具，直接用知识回答

回复规则：
- 只输出回复内容，不加多余前缀
- 提及团队成员时使用中文名
- 涉及敏感信息不回答，引导找相关负责人
"""


class AgentRuntime:
    """AI Agent 运行时

    核心循环：接收消息 → 调 LLM → 执行工具 → 回传结果 → 循环直到完成
    """

    def __init__(
        self,
        llm_settings: LLMSettings,
        registry: PluginRegistry,
        session_store: SessionStore,
        system_prompt: str = SYSTEM_PROMPT,
    ):
        self._llm = LLMClient(llm_settings.get_model_chain())
        self._model = llm_settings.model
        self._max_tokens = llm_settings.max_tokens
        self._registry = registry
        self._sessions = session_store
        self._system_prompt = system_prompt

    async def process(self, ctx: RequestContext, content: str) -> str:
        """处理一条用户消息，返回回复文本

        Args:
            ctx: 请求上下文（渠道、身份、角色、权限等）
            content: 消息内容

        Returns:
            AI 回复文本
        """
        # 0. 空消息保护
        if not content or not content.strip():
            if not ctx.images:
                log.warning(f"收到空消息，跳过处理 ({ctx.channel}:{ctx.user_id})")
                return ""

        # 1. 加载对话历史，追加用户消息
        messages = await self._sessions.get_messages(ctx.channel, ctx.user_id)

        # 构建 user content（支持多模态：文本 + 图片）
        user_content = self._build_user_content(content, ctx.images)
        messages.append({"role": "user", "content": user_content})

        # 2. 构建 system prompt
        sender_context = ctx.get_sender_prompt()
        channel_prompt = ctx.channel_prompt

        # 2.1 插件引导 prompt（检查各插件就绪状态）
        onboarding_hints = []
        blocked_tools: set[str] = set()  # 未就绪插件的工具，不暴露给 LLM
        is_admin = "*" in (ctx.permissions or set()) or "admin" in {r.name if hasattr(r, "name") else r for r in (ctx.roles or [])}
        for plugin in self._registry.list_plugins():
            platform = plugin.get_platform()
            if not platform:
                continue
            try:
                status = await plugin.get_setup_status(ctx)
                if status != "ready":
                    # 屏蔽该插件的所有工具，强制走引导流程
                    for tool in plugin.get_tools():
                        blocked_tools.add(tool.name)
                    hint = plugin.get_onboarding_prompt(status, is_admin)
                    if hint:
                        onboarding_hints.append(f"## {plugin.display_name}引导\n\n{hint}")
            except Exception as e:
                log.warning(f"检查插件 {plugin.name} 就绪状态失败: {e}")

        # 3. 获取可用工具（按权限和渠道过滤）
        tools = self._registry.to_claude_tools(
            permissions=ctx.permissions if ctx.permissions else None,
            allowed_tools=ctx.allowed_tools,
        )
        # 移除未就绪插件的工具，用户必须先完成引导（同步通讯录 + 绑定身份）
        if blocked_tools:
            tools = [t for t in tools if t["name"] not in blocked_tools]

        # 4. Agentic loop
        max_rounds = 10
        response = None
        total_usage = Usage()

        # 获取 per-session thinking 级别
        thinking_level = self._sessions.get_thinking_level(ctx.channel, ctx.user_id)
        thinking_param = self._build_thinking_param(thinking_level)

        for _ in range(max_rounds):
            try:
                system = self._system_prompt + sender_context
                if channel_prompt:
                    system += f"\n\n# 渠道回复规范\n\n{channel_prompt}"
                plugin_prompts = self._registry.get_system_prompt_extension()
                if plugin_prompts:
                    system += "\n\n# 插件能力\n\n" + plugin_prompts
                if onboarding_hints:
                    system += "\n\n# 插件引导（优先处理）\n\n" + "\n\n".join(onboarding_hints)

                response = await self._llm.create(
                    system=system, messages=messages,
                    tools=tools if tools else None,
                    thinking=thinking_param,
                )
                total_usage.input_tokens += response.usage.input_tokens
                total_usage.output_tokens += response.usage.output_tokens
                total_usage.cache_creation_input_tokens += response.usage.cache_creation_input_tokens
                total_usage.cache_read_input_tokens += response.usage.cache_read_input_tokens
            except Exception as e:
                log.error(f"LLM API 调用失败: {e}")
                reason = self._extract_error_reason(e)
                error_text = f"抱歉，AI 服务暂时不可用：{reason}\n请稍后再试。"
                messages.append({"role": "assistant", "content": [{"type": "text", "text": error_text}]})
                await self._sessions.save_messages(ctx.channel, ctx.user_id, messages)
                return error_text

            # 追加 assistant 回复
            messages.append({"role": "assistant", "content": self._serialize_content(response.content)})

            # 不是 tool_use，说明完成了
            if response.stop_reason != "tool_use":
                break

            # 执行工具调用
            tool_results = []
            need_refresh_tools = False
            for block in response.content:
                if getattr(block, "type", None) == "tool_use":
                    log.info(f"调用工具: {block.name}({block.input})")
                    tool_input = dict(block.input)
                    tool_input["_caller_id"] = ctx.user_id
                    if ctx.member:
                        tool_input["_member_id"] = ctx.member.id
                    # 注入禅道账号（优先用操作人自己的账号）
                    if ctx.platform_accounts.get("zentao"):
                        tool_input["_zentao_account"] = ctx.platform_accounts["zentao"]
                    if ctx.images:
                        tool_input["_image_urls"] = [
                            img.get("pic_url") or img.get("file_url", "")
                            for img in ctx.images
                            if img.get("pic_url") or img.get("file_url")
                        ]
                        tool_input["_image_files"] = [
                            {"data": img["data"], "media_type": img.get("media_type", "image/png")}
                            for img in ctx.images if img.get("data")
                        ]
                    result = await self._registry.execute_tool(block.name, tool_input)
                    log.info(f"工具结果: {result[:200]}")
                    tool_results.append({
                        "type": "tool_result",
                        "tool_use_id": block.id,
                        "content": result,
                    })
                    # 同步/绑定操作可能改变插件就绪状态，标记需要刷新工具列表
                    if block.name in ("contacts_sync", "contacts_bind_identity"):
                        need_refresh_tools = True

            # 引导工具执行后，重新检查插件状态并刷新可用工具列表
            if need_refresh_tools and blocked_tools:
                await ctx.refresh_identity()
                blocked_tools.clear()
                onboarding_hints.clear()
                for plugin in self._registry.list_plugins():
                    platform = plugin.get_platform()
                    if not platform:
                        continue
                    try:
                        status = await plugin.get_setup_status(ctx)
                        if status != "ready":
                            for tool in plugin.get_tools():
                                blocked_tools.add(tool.name)
                            hint = plugin.get_onboarding_prompt(status, is_admin)
                            if hint:
                                onboarding_hints.append(f"## {plugin.display_name}引导\n\n{hint}")
                    except Exception as e:
                        log.warning(f"刷新插件 {plugin.name} 就绪状态失败: {e}")
                tools = self._registry.to_claude_tools(
                    permissions=ctx.permissions if ctx.permissions else None,
                    allowed_tools=ctx.allowed_tools,
                )
                if blocked_tools:
                    tools = [t for t in tools if t["name"] not in blocked_tools]
                log.info(f"工具列表已刷新，当前可用 {len(tools)} 个工具")

            # 回传工具结果
            messages.append({"role": "user", "content": tool_results})

        # 5. 保存对话历史 + 累计用量
        await self._sessions.save_messages(ctx.channel, ctx.user_id, messages)
        self._sessions.add_usage(
            ctx.channel, ctx.user_id, total_usage.input_tokens, total_usage.output_tokens,
            cache_creation_tokens=total_usage.cache_creation_input_tokens,
            cache_read_tokens=total_usage.cache_read_input_tokens,
        )
        cache_info = ""
        if total_usage.cache_read_input_tokens:
            cache_info = f", cache_read={total_usage.cache_read_input_tokens}"
        if total_usage.cache_creation_input_tokens:
            cache_info += f", cache_create={total_usage.cache_creation_input_tokens}"
        log.info(f"本次用量: input={total_usage.input_tokens}, output={total_usage.output_tokens}{cache_info}")

        # 6. 提取文本回复（必要时截断）
        reply = self._extract_text(response) if response else "（无回复内容）"

        # 6.1 附加用量信息（根据 per-session usage_mode）
        usage_mode = self._sessions.get_usage_mode(ctx.channel, ctx.user_id)
        if usage_mode == "tokens":
            cache_suffix = ""
            if total_usage.cache_read_input_tokens:
                cache_suffix = f" 💾{total_usage.cache_read_input_tokens}"
            reply += f"\n\n📊 本次: ↑{total_usage.input_tokens} ↓{total_usage.output_tokens}{cache_suffix}"
        elif usage_mode == "full":
            info = self._sessions.get_session_info(ctx.channel, ctx.user_id)
            cache_suffix = ""
            if total_usage.cache_read_input_tokens:
                cache_suffix = f" 💾{total_usage.cache_read_input_tokens}"
            reply += (
                f"\n\n📊 本次: ↑{total_usage.input_tokens} ↓{total_usage.output_tokens}{cache_suffix}"
                f" | 累计: ↑{info['total_input_tokens']} ↓{info['total_output_tokens']}"
            )

        if ctx.max_reply_length and len(reply) > ctx.max_reply_length:
            reply = reply[: ctx.max_reply_length - 3] + "..."
        return reply

    async def chat(self, content: str) -> str:
        """简单对话接口（无 channel/user 上下文，用于 CLI 调试）"""
        ctx = RequestContext(channel="cli", user_id="debug")
        return await self.process(ctx, content)

    async def process_stream_web(self, content: str, member_id: str = "admin", images: list[dict] | None = None, session_id: str = "default"):
        """Web 面板流式对话接口

        使用 Anthropic streaming API，逐块 yield 事件。
        每个成员有独立的会话历史，使用真实身份构建上下文。

        Args:
            content: 用户消息
            member_id: 成员 ID，用于独立会话和身份识别
            session_id: 会话 ID，支持多会话

        Yields:
            dict: {"type": "text_delta", "text": "..."} |
                  {"type": "tool_use", "name": "..."} |
                  {"type": "tool_result", "name": "...", "result": "..."} |
                  {"type": "thinking"}
        """
        # 尝试用真实身份构建上下文
        from openvort.web.deps import get_build_context_fn
        build_context = get_build_context_fn()
        if build_context:
            try:
                ctx = await build_context("web", member_id)
            except Exception as e:
                log.warning(f"[web] 构建上下文失败，使用默认: {e}")
                ctx = RequestContext(channel="web", user_id=member_id, permissions={"*"})
        else:
            ctx = RequestContext(channel="web", user_id=member_id, permissions={"*"})

        ctx.images = images or []

        if (not content or not content.strip()) and not images:
            return

        messages = await self._sessions.get_messages(ctx.channel, ctx.user_id, session_id)
        user_content = self._build_user_content(content, images or [])
        messages.append({"role": "user", "content": user_content})

        # 构建 system prompt（注入用户身份 + 插件引导）
        sender_context = ctx.get_sender_prompt()

        # 检查插件引导状态
        onboarding_hints = []
        blocked_tools: set[str] = set()
        is_admin = "*" in (ctx.permissions or set()) or "admin" in {r.name if hasattr(r, "name") else r for r in (ctx.roles or [])}
        for plugin in self._registry.list_plugins():
            platform = plugin.get_platform()
            if not platform:
                continue
            try:
                status = await plugin.get_setup_status(ctx)
                if status != "ready":
                    for tool in plugin.get_tools():
                        blocked_tools.add(tool.name)
                    hint = plugin.get_onboarding_prompt(status, is_admin)
                    if hint:
                        onboarding_hints.append(f"## {plugin.display_name}引导\n\n{hint}")
            except Exception as e:
                log.warning(f"[web] 检查插件 {plugin.name} 就绪状态失败: {e}")

        system = self._system_prompt + sender_context
        plugin_prompts = self._registry.get_system_prompt_extension()
        if plugin_prompts:
            system += "\n\n# 插件能力\n\n" + plugin_prompts
        if onboarding_hints:
            system += "\n\n# 插件引导（优先处理）\n\n" + "\n\n".join(onboarding_hints)

        tools = self._registry.to_claude_tools(permissions=ctx.permissions if ctx.permissions else {"*"})
        if blocked_tools:
            tools = [t for t in tools if t["name"] not in blocked_tools]

        max_rounds = 10
        current_text = ""
        total_usage = Usage()
        completed = False
        try:
            for _ in range(max_rounds):
                try:
                    collected_content = []
                    async with self._llm.stream(
                        system=system, messages=messages,
                        tools=tools if tools else None,
                    ) as stream:
                        async for event in stream:
                            if event.type == "content_block_start":
                                block = event.content_block
                                if getattr(block, "type", None) == "text":
                                    pass
                                elif getattr(block, "type", None) == "tool_use":
                                    yield {"type": "tool_use", "name": block.name, "id": block.id}
                            elif event.type == "content_block_delta":
                                delta = event.delta
                                if getattr(delta, "type", None) == "text_delta":
                                    current_text += delta.text
                                    yield {"type": "text", "text": current_text}
                                elif getattr(delta, "type", None) == "input_json_delta":
                                    pass

                        response = await stream.get_final_message()
                        total_usage.input_tokens += response.usage.input_tokens
                        total_usage.output_tokens += response.usage.output_tokens
                        total_usage.cache_creation_input_tokens += response.usage.cache_creation_input_tokens
                        total_usage.cache_read_input_tokens += response.usage.cache_read_input_tokens
                except Exception as e:
                    log.error(f"LLM API 流式调用失败: {e}")
                    reason = self._extract_error_reason(e)
                    error_text = f"抱歉，AI 服务暂时不可用：{reason}\n请稍后再试。"
                    yield {"type": "text", "text": error_text}
                    messages.append({"role": "assistant", "content": [{"type": "text", "text": error_text}]})
                    await self._sessions.save_messages(ctx.channel, ctx.user_id, messages, session_id)
                    completed = True
                    return

                messages.append({"role": "assistant", "content": self._serialize_content(response.content)})

                if response.stop_reason != "tool_use":
                    break

                tool_results = []
                for block in response.content:
                    if getattr(block, "type", None) == "tool_use":
                        log.info(f"[web] 调用工具: {block.name}({block.input})")
                        tool_input = dict(block.input)
                        tool_input["_caller_id"] = ctx.user_id
                        if ctx.member:
                            tool_input["_member_id"] = ctx.member.id
                        if ctx.platform_accounts.get("zentao"):
                            tool_input["_zentao_account"] = ctx.platform_accounts["zentao"]
                        if ctx.images:
                            tool_input["_image_urls"] = [
                                img.get("pic_url") or img.get("file_url", "")
                                for img in ctx.images
                                if img.get("pic_url") or img.get("file_url")
                            ]
                            tool_input["_image_files"] = [
                                {"data": img["data"], "media_type": img.get("media_type", "image/png")}
                                for img in ctx.images if img.get("data")
                            ]

                        output_queue: asyncio.Queue[str] = asyncio.Queue()
                        tool_input["_output_queue"] = output_queue

                        tool_task = asyncio.create_task(
                            self._registry.execute_tool(block.name, tool_input)
                        )
                        elapsed = 0
                        while not tool_task.done():
                            try:
                                await asyncio.wait_for(asyncio.shield(tool_task), timeout=2)
                            except asyncio.TimeoutError:
                                elapsed += 2
                                # Drain queued CLI output lines
                                lines: list[str] = []
                                while not output_queue.empty():
                                    try:
                                        lines.append(output_queue.get_nowait())
                                    except asyncio.QueueEmpty:
                                        break
                                output_chunk = "\n".join(lines)
                                if output_chunk:
                                    yield {
                                        "type": "tool_output",
                                        "name": block.name,
                                        "output": output_chunk,
                                    }
                                elif elapsed % 10 == 0:
                                    log.info(f"[web] 工具 {block.name} 执行中... ({elapsed}s)")
                                    yield {
                                        "type": "tool_progress",
                                        "name": block.name,
                                        "elapsed": elapsed,
                                    }
                        result = tool_task.result()

                        log.info(f"[web] 工具结果: {result[:200]}")
                        yield {"type": "tool_result", "name": block.name, "result": result[:200]}
                        tool_results.append({
                            "type": "tool_result",
                            "tool_use_id": block.id,
                            "content": result,
                        })

                messages.append({"role": "user", "content": tool_results})

            # Save and yield usage on normal completion
            await self._sessions.save_messages(ctx.channel, ctx.user_id, messages, session_id)
            self._sessions.add_usage(
                ctx.channel, ctx.user_id, total_usage.input_tokens, total_usage.output_tokens,
                session_id,
                cache_creation_tokens=total_usage.cache_creation_input_tokens,
                cache_read_tokens=total_usage.cache_read_input_tokens,
            )
            completed = True

            session_info = self._sessions.get_session_info(ctx.channel, ctx.user_id, session_id)
            yield {
                "type": "usage",
                "input_tokens": total_usage.input_tokens,
                "output_tokens": total_usage.output_tokens,
                "cache_creation_tokens": total_usage.cache_creation_input_tokens,
                "cache_read_tokens": total_usage.cache_read_input_tokens,
                "total_input_tokens": session_info.get("total_input_tokens", 0),
                "total_output_tokens": session_info.get("total_output_tokens", 0),
                "total_cache_creation_tokens": session_info.get("total_cache_creation_tokens", 0),
                "total_cache_read_tokens": session_info.get("total_cache_read_tokens", 0),
            }
        finally:
            if not completed and len(messages) > 1:
                log.warning("[web] SSE 断连或异常中断，强制保存对话历史")
                try:
                    await self._sessions.save_messages(ctx.channel, ctx.user_id, messages, session_id)
                    if total_usage.input_tokens or total_usage.output_tokens:
                        self._sessions.add_usage(
                            ctx.channel, ctx.user_id, total_usage.input_tokens, total_usage.output_tokens,
                            session_id,
                            cache_creation_tokens=total_usage.cache_creation_input_tokens,
                            cache_read_tokens=total_usage.cache_read_input_tokens,
                        )
                except Exception as e:
                    log.error(f"[web] 强制保存对话历史失败: {e}")

    @staticmethod
    def _extract_text(response: LLMResponse) -> str:
        """从 LLM 响应中提取文本内容"""
        parts = []
        for block in response.content:
            if getattr(block, "type", None) == "text":
                parts.append(block.text)
        return "\n".join(parts) if parts else "（无回复内容）"

    @staticmethod
    def _serialize_content(content) -> list[dict]:
        """将 LLM 响应 content 序列化为可 JSON 化的格式"""
        serialized = []
        for block in content:
            block_type = getattr(block, "type", None) if not isinstance(block, dict) else block.get("type")
            if block_type == "text":
                text = block.text if not isinstance(block, dict) else block.get("text", "")
                serialized.append({"type": "text", "text": text})
            elif block_type == "tool_use":
                if isinstance(block, dict):
                    serialized.append(block)
                else:
                    serialized.append({
                        "type": "tool_use",
                        "id": block.id,
                        "name": block.name,
                        "input": block.input,
                    })
        return serialized

    @staticmethod
    def _extract_error_reason(e: Exception) -> str:
        """Extract a user-friendly error reason from an LLM API exception."""
        msg = str(e)
        # Anthropic-style structured error
        if "service_unavailable" in msg or "No verified API" in msg:
            return "AI 服务商暂时不可用"
        if "overloaded" in msg:
            return "AI 服务过载，请稍后重试"
        if "rate_limit" in msg or "429" in msg:
            return "请求频率超限，请稍等"
        if "authentication" in msg.lower() or "401" in msg:
            return "API 认证失败，请联系管理员检查配置"
        if "timeout" in msg.lower() or "timed out" in msg.lower():
            return "请求超时，AI 服务响应过慢"
        if "connection" in msg.lower():
            return "无法连接 AI 服务"
        # Generic: truncate to something readable
        short = msg[:120].strip()
        return short if short else "未知错误"

    @staticmethod
    def _build_thinking_param(level: str) -> dict | None:
        """构建 thinking 参数（仅 Anthropic 支持）

        Args:
            level: off|low|medium|high 或空字符串

        Returns:
            thinking dict 或 None
        """
        if not level or level == "off":
            return None
        # Anthropic extended thinking: budget_tokens 映射
        budget_map = {
            "low": 2048,
            "medium": 5120,
            "high": 10240,
        }
        budget = budget_map.get(level, 5120)
        return {"type": "enabled", "budget_tokens": budget}

    @staticmethod
    def _build_user_content(text: str, images: list[dict]) -> str | list[dict]:
        """构建用户消息 content（纯文本或多模态）

        无图片时返回纯字符串（节省 token），有图片时返回 content blocks。
        同时把 pic_url 写入文本，确保后续轮次 AI 也能引用图片 URL。
        file_url is persisted in image blocks for history recovery.
        """
        if not images:
            return text

        blocks: list[dict] = []
        pic_urls = []
        for img in images:
            data = img.get("data")
            media_type = img.get("media_type", "image/jpeg")
            if data:
                block: dict = {
                    "type": "image",
                    "source": {
                        "type": "base64",
                        "media_type": media_type,
                        "data": data,
                    },
                }
                file_url = img.get("file_url", "")
                if file_url:
                    block["file_url"] = file_url
                blocks.append(block)
            pic_url = img.get("pic_url", "")
            if pic_url:
                pic_urls.append(pic_url)

        url_hint = ""
        if pic_urls:
            url_list = "\n".join(pic_urls)
            url_hint = f"\n\n[图片URL，可用于嵌入禅道]\n{url_list}"

        if text and text.strip():
            blocks.append({"type": "text", "text": text + url_hint})
        else:
            blocks.append({"type": "text", "text": "请看图片" + url_hint})
            blocks.append({"type": "text", "text": "请看图片"})

        return blocks
