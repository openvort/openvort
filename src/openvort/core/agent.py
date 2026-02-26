"""
Agent Runtime

基于 Claude tool use 的 agentic loop。
不依赖 LangChain 等框架，保持轻量可控。
"""

import anthropic

from openvort.config.settings import LLMSettings
from openvort.core.context import RequestContext
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
        client_kwargs = {
            "api_key": llm_settings.api_key,
            "timeout": llm_settings.timeout,
        }
        if llm_settings.api_base and llm_settings.api_base != "https://api.anthropic.com":
            client_kwargs["base_url"] = llm_settings.api_base
        self._client = anthropic.AsyncAnthropic(**client_kwargs)
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
        messages = self._sessions.get_messages(ctx.channel, ctx.user_id)

        # 构建 user content（支持多模态：文本 + 图片）
        user_content = self._build_user_content(content, ctx.images)
        messages.append({"role": "user", "content": user_content})

        # 2. 构建 system prompt
        sender_context = ctx.get_sender_prompt()
        channel_prompt = ctx.channel_prompt

        # 2.1 插件引导 prompt（检查各插件就绪状态）
        onboarding_hints = []
        is_admin = "*" in (ctx.permissions or set()) or "admin" in {r.name if hasattr(r, "name") else r for r in (ctx.roles or [])}
        for plugin in self._registry.list_plugins():
            platform = plugin.get_platform()
            if not platform:
                continue
            try:
                status = await plugin.get_setup_status(ctx)
                if status != "ready":
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

        # 4. Agentic loop
        max_rounds = 10
        response = None
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

                kwargs = {
                    "model": self._model,
                    "max_tokens": self._max_tokens,
                    "system": system,
                    "messages": messages,
                }
                if tools:
                    kwargs["tools"] = tools

                response = await self._client.messages.create(**kwargs)
            except anthropic.APIError as e:
                log.error(f"LLM API 调用失败: {e}")
                return "抱歉，AI 服务暂时不可用，请稍后再试。"

            # 追加 assistant 回复
            messages.append({"role": "assistant", "content": self._serialize_content(response.content)})

            # 不是 tool_use，说明完成了
            if response.stop_reason != "tool_use":
                break

            # 执行工具调用
            tool_results = []
            for block in response.content:
                if block.type == "tool_use":
                    log.info(f"调用工具: {block.name}({block.input})")
                    tool_input = dict(block.input)
                    tool_input["_caller_id"] = ctx.user_id
                    if ctx.member:
                        tool_input["_member_id"] = ctx.member.id
                    # 注入禅道账号（优先用操作人自己的账号）
                    if ctx.platform_accounts.get("zentao"):
                        tool_input["_zentao_account"] = ctx.platform_accounts["zentao"]
                    # 注入图片 URL（pic_url 列表）
                    if ctx.images:
                        tool_input["_image_urls"] = [
                            img["pic_url"] for img in ctx.images if img.get("pic_url")
                        ]
                    result = await self._registry.execute_tool(block.name, tool_input)
                    log.info(f"工具结果: {result[:200]}")
                    tool_results.append({
                        "type": "tool_result",
                        "tool_use_id": block.id,
                        "content": result,
                    })

            # 回传工具结果
            messages.append({"role": "user", "content": tool_results})

        # 5. 保存对话历史
        self._sessions.save_messages(ctx.channel, ctx.user_id, messages)

        # 6. 提取文本回复（必要时截断）
        reply = self._extract_text(response) if response else "（无回复内容）"
        if ctx.max_reply_length and len(reply) > ctx.max_reply_length:
            reply = reply[: ctx.max_reply_length - 3] + "..."
        return reply

    async def chat(self, content: str) -> str:
        """简单对话接口（无 channel/user 上下文，用于 CLI 调试）"""
        ctx = RequestContext(channel="cli", user_id="debug")
        return await self.process(ctx, content)

    @staticmethod
    def _extract_text(response) -> str:
        """从 Claude 响应中提取文本内容"""
        parts = []
        for block in response.content:
            if block.type == "text":
                parts.append(block.text)
        return "\n".join(parts) if parts else "（无回复内容）"

    @staticmethod
    def _serialize_content(content) -> list[dict]:
        """将 Claude 响应 content 序列化为可 JSON 化的格式"""
        serialized = []
        for block in content:
            if block.type == "text":
                serialized.append({"type": "text", "text": block.text})
            elif block.type == "tool_use":
                serialized.append({
                    "type": "tool_use",
                    "id": block.id,
                    "name": block.name,
                    "input": block.input,
                })
        return serialized

    @staticmethod
    def _build_user_content(text: str, images: list[dict]) -> str | list[dict]:
        """构建用户消息 content（纯文本或多模态）

        无图片时返回纯字符串（节省 token），有图片时返回 content blocks。
        同时把 pic_url 写入文本，确保后续轮次 AI 也能引用图片 URL。
        """
        if not images:
            return text

        blocks: list[dict] = []
        # 先放图片
        pic_urls = []
        for img in images:
            data = img.get("data")
            media_type = img.get("media_type", "image/jpeg")
            if data:
                blocks.append({
                    "type": "image",
                    "source": {
                        "type": "base64",
                        "media_type": media_type,
                        "data": data,
                    },
                })
            pic_url = img.get("pic_url", "")
            if pic_url:
                pic_urls.append(pic_url)

        # 文本中附上 pic_url，确保跨轮次可引用
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
