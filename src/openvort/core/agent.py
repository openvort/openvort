"""
Agent Runtime

基于 LLM tool use 的 agentic loop。
支持多 Provider（Anthropic/OpenAI/DeepSeek 等）+ Failover。
不依赖 LangChain 等框架，保持轻量可控。
"""

import asyncio
import json
import re

from openvort.config.settings import LLMSettings
from openvort.core.context import RequestContext
from openvort.core.llm import (
    LLMClient, LLMResponse, TextBlock, ThinkingBlock, ThinkingDelta, ToolUseBlock, Usage,
)
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

## ⚠️ 最重要的规则：必须调用工具才能执行操作

当用户要求你执行任何操作（创建文件、修改代码、查询数据、管理任务等）时：
1. 你**必须**通过调用工具来完成，绝不能只回复文字假装已完成
2. 在工具调用返回结果之前，不允许说"已完成"、"已创建"、"已添加"等
3. 操作结果必须来自工具的实际返回值，不允许编造

**绝对禁止的行为（违反即为严重错误）：**
- ❌ 不调用工具就说"已完成"、"已创建"、"已添加"、"搞定了"
- ❌ 用户要求执行操作时只回复确认文字而不实际调用工具
- ❌ 编造操作结果（文件路径、ID、链接等）
- ❌ 只说"我来帮你做"却不实际调用工具

**正确行为（严格按此顺序）：**
- ✅ 收到操作请求 → 先用一句话告诉用户你将要做什么（如"好的，我来帮你创建定时任务"）→ 然后在同一次回复中调用工具 → 根据工具返回报告结果
- ✅ 请求有歧义 → 简要确认关键参数 → 确认后立即调用工具执行
- ✅ 没有合适的工具 → 明确告知用户"目前无法执行该操作"，说明原因
- ✅ 工具调用失败 → 如实报告错误，不要编造成功结果

## 回复风格：先说再做

- **每次调用工具之前，必须先输出一段简短文字**，告诉用户你接下来要做什么（一句话即可，如"好的，我来帮你查一下"）
- 不要反复问"确定吗？"、"要开始吗？"——说完就做，同一次回复中完成
- 只在关键参数缺失或有歧义时才简要确认

## 工具路由指南

根据用户意图快速匹配合适的工具：

| 用户意图 | 应使用的工具 |
|---------|------------|
| 写代码、改文件、建文件、修 Bug、加功能 | `git_code_task` |
| 查看有哪些仓库 | `git_list_repos` |
| 查看仓库详情、分支、最近提交 | `git_repo_info` |
| 查某人/某仓库的提交记录 | `git_query_commits` |
| 生成工作日报/周报/月报 | `git_work_summary` |
| 配置 Git 平台（Gitee/GitHub 等） | `git_manage_provider` |
| 提交推送代码 | `git_commit_push` |
| 创建 Pull Request | `git_create_pr` |
| 创建/查询/管理项目、需求、任务、Bug | VortFlow 相关工具 |
| 创建/管理定时任务 | Schedule 相关工具 |
| 配置通道、系统诊断 | System 相关工具 |
| 给企业微信/飞书/钉钉发消息、代发提醒、主动通知某人 | `wecom_send_message` / `wecom_send_voice` / `feishu_send_message` / `feishu_send_voice` / `dingtalk_send_message` / `dingtalk_send_voice` |
| 纯知识问答，不需要执行操作 | 无需工具，直接回答 |

如果用户的请求涉及某个仓库但你不确定是哪个，先用 `git_list_repos` 查一下。
如果用户说“给我的飞书/企微/钉钉发消息”，优先直接调用对应的发消息工具；未明确 user_id 时，可省略该参数，默认发送给当前对话者已绑定的账号。

## 回复规则

- 只输出回复内容，不加多余前缀
- 提及团队成员时使用中文名
- 涉及敏感信息不回答，引导找相关负责人
- 当用户消息以 `[语音消息]` 开头时，表示系统已经完成语音转写，后续文字就是用户原话
- 对于已转写的语音消息，禁止再说“无法识别语音内容”或要求用户把语音改成文字
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

        direct_action = await self._maybe_handle_direct_channel_send(ctx, content)
        if direct_action:
            messages = await self._sessions.get_messages(ctx.channel, ctx.user_id)
            user_content = self._build_user_content(content, ctx.images)
            messages.append({"role": "user", "content": user_content})
            messages.append({"role": "assistant", "content": [{"type": "text", "text": direct_action["reply_text"]}]})
            await self._sessions.save_messages(ctx.channel, ctx.user_id, messages)
            return direct_action["reply_text"]

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
        tools = self._prioritize_tools_for_intent(content, tools)

        # 4. Agentic loop
        max_rounds = 10
        response = None
        total_usage = Usage()
        any_tool_called = False
        correction_injected = False

        # 获取 per-session thinking 级别
        thinking_level = self._sessions.get_thinking_level(ctx.channel, ctx.user_id)
        thinking_param = self._build_thinking_param(thinking_level)

        for _ in range(max_rounds):
            try:
                system = self._system_prompt + sender_context
                if channel_prompt:
                    system += f"\n\n# 渠道回复规范\n\n{channel_prompt}"
                action_hint = self._build_action_hint(content)
                if action_hint:
                    system += f"\n\n# 当前操作提示\n\n{action_hint}"

                if ctx.group_prompt:
                    system += f"\n\n{ctx.group_prompt}"

                # 检查是否为 AI 员工，注入人设
                if ctx.member and ctx.member.is_virtual and ctx.member.virtual_system_prompt:
                    system += f"\n\n# AI 员工人设\n\n{ctx.member.virtual_system_prompt}"

                plugin_prompts = self._registry.get_system_prompt_extension()
                if plugin_prompts:
                    system += "\n\n" + plugin_prompts
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

            # 不是 tool_use — 检查是否虚假完成后结束
            if response.stop_reason != "tool_use":
                if (not any_tool_called and not correction_injected
                        and self._requires_channel_send_tool(content)):
                    log.warning("检测到通道发消息请求未调用工具，注入纠正提示重试")
                    correction_injected = True
                    messages.append({
                        "role": "user",
                        "content": self._CHANNEL_SEND_ACTION_CORRECTION,
                    })
                    continue
                if (not any_tool_called and not correction_injected
                        and self._detect_empty_action(response)):
                    log.warning("检测到空操作：模型声称已完成但未调用工具，注入纠正提示重试")
                    correction_injected = True
                    messages.append({
                        "role": "user",
                        "content": self._EMPTY_ACTION_CORRECTION,
                    })
                    continue
                break

            any_tool_called = True
            # 执行工具调用
            tool_results = []
            need_refresh_tools = False
            
            # 获取用户当前输入（用于确认操作场景）
            current_user_input = content
            
            for block in response.content:
                if getattr(block, "type", None) == "tool_use":
                    log.info(f"调用工具: {block.name}({block.input})")
                    tool_input = dict(block.input)
                    tool_input["_caller_id"] = ctx.user_id
                    # 注入用户输入（用于确认操作场景）
                    tool_input["_user_input"] = current_user_input
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
                    # 注入目标成员信息（用于 AI 员工聊天场景）
                    # target_member_id 是当前对话的 AI 员工成员 ID
                    # caller_member_id 是当前发起请求的真实成员 ID
                    tool_input["_target_member_id"] = getattr(ctx, "target_member_id", "") or ""
                    tool_input["_caller_member_id"] = getattr(ctx, "caller_member_id", "") or ctx.user_id
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

    async def process_stream_im(self, ctx: RequestContext, content: str):
        """IM 渠道流式处理，yield 事件供 channel 逐帧推送

        Yields:
            {"type": "thinking_delta", "text": "..."} — thinking 增量
            {"type": "text_delta", "text": "..."}     — 文本增量
            {"type": "text", "text": "..."}           — 累积全文
            {"type": "tool_use", "name": "...", "id": "..."} — 工具调用
            {"type": "tool_result", "name": "...", "result": "..."} — 工具结果
        """
        if not content or not content.strip():
            if not ctx.images:
                return

        direct_action = await self._maybe_handle_direct_channel_send(ctx, content)
        if direct_action:
            messages = await self._sessions.get_messages(ctx.channel, ctx.user_id)
            user_content = self._build_user_content(content, ctx.images)
            messages.append({"role": "user", "content": user_content})
            messages.append({"role": "assistant", "content": [{"type": "text", "text": direct_action["reply_text"]}]})
            await self._sessions.save_messages(ctx.channel, ctx.user_id, messages)
            yield {"type": "tool_use", "name": direct_action["tool_name"], "id": "direct-channel-send"}
            yield {"type": "tool_result", "name": direct_action["tool_name"], "result": direct_action["tool_result"]}
            yield {"type": "text_delta", "text": direct_action["reply_text"]}
            yield {"type": "text", "text": direct_action["reply_text"]}
            return

        messages = await self._sessions.get_messages(ctx.channel, ctx.user_id)
        user_content = self._build_user_content(content, ctx.images)
        messages.append({"role": "user", "content": user_content})

        sender_context = ctx.get_sender_prompt()
        channel_prompt = ctx.channel_prompt

        onboarding_hints: list[str] = []
        blocked_tools: set[str] = set()
        is_admin = "*" in (ctx.permissions or set()) or "admin" in {
            r.name if hasattr(r, "name") else r for r in (ctx.roles or [])
        }
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
                log.warning(f"[im-stream] 检查插件 {plugin.name} 就绪状态失败: {e}")

        tools = self._registry.to_claude_tools(
            permissions=ctx.permissions if ctx.permissions else None,
            allowed_tools=ctx.allowed_tools,
        )
        if blocked_tools:
            tools = [t for t in tools if t["name"] not in blocked_tools]
        tools = self._prioritize_tools_for_intent(content, tools)

        thinking_level = self._sessions.get_thinking_level(ctx.channel, ctx.user_id)
        thinking_param = self._build_thinking_param(thinking_level)

        max_rounds = 10
        total_usage = Usage()
        accumulated_text = ""
        any_tool_called = False
        correction_injected = False

        for _ in range(max_rounds):
            try:
                system = self._system_prompt + sender_context
                if channel_prompt:
                    system += f"\n\n# 渠道回复规范\n\n{channel_prompt}"
                if ctx.group_prompt:
                    system += f"\n\n{ctx.group_prompt}"
                action_hint = self._build_action_hint(content)
                if action_hint:
                    system += f"\n\n# 当前操作提示\n\n{action_hint}"
                if ctx.member and ctx.member.is_virtual and ctx.member.virtual_system_prompt:
                    system += f"\n\n# AI 员工人设\n\n{ctx.member.virtual_system_prompt}"
                plugin_prompts = self._registry.get_system_prompt_extension()
                if plugin_prompts:
                    system += "\n\n" + plugin_prompts
                if onboarding_hints:
                    system += "\n\n# 插件引导（优先处理）\n\n" + "\n\n".join(onboarding_hints)

                async with self._llm.stream(
                    system=system, messages=messages,
                    tools=tools if tools else None,
                    thinking=thinking_param,
                ) as stream:
                    async for event in stream:
                        if event.type == "content_block_start":
                            block = event.content_block
                            if getattr(block, "type", None) == "tool_use":
                                yield {"type": "tool_use", "name": block.name, "id": block.id}
                        elif event.type == "content_block_delta":
                            delta = event.delta
                            if getattr(delta, "type", None) == "text_delta":
                                accumulated_text += delta.text
                                yield {"type": "text_delta", "text": delta.text}
                                yield {"type": "text", "text": accumulated_text}
                            elif getattr(delta, "type", None) == "thinking_delta":
                                yield {"type": "thinking_delta", "text": delta.thinking}

                    response = await stream.get_final_message()
                    total_usage.input_tokens += response.usage.input_tokens
                    total_usage.output_tokens += response.usage.output_tokens
                    total_usage.cache_creation_input_tokens += response.usage.cache_creation_input_tokens
                    total_usage.cache_read_input_tokens += response.usage.cache_read_input_tokens
            except Exception as e:
                log.error(f"[im-stream] LLM 流式调用失败: {e}")
                reason = self._extract_error_reason(e)
                error_text = f"抱歉，AI 服务暂时不可用：{reason}\n请稍后再试。"
                yield {"type": "text_delta", "text": error_text}
                yield {"type": "text", "text": error_text}
                messages.append({"role": "assistant", "content": [{"type": "text", "text": error_text}]})
                await self._sessions.save_messages(ctx.channel, ctx.user_id, messages)
                return

            messages.append({"role": "assistant", "content": self._serialize_content(response.content)})

            if response.stop_reason != "tool_use":
                if (not any_tool_called and not correction_injected
                        and self._requires_channel_send_tool(content)):
                    correction_injected = True
                    accumulated_text = ""
                    messages.append({
                        "role": "user",
                        "content": self._CHANNEL_SEND_ACTION_CORRECTION,
                    })
                    continue
                if (not any_tool_called and not correction_injected
                        and self._text_claims_action(accumulated_text)):
                    correction_injected = True
                    accumulated_text = ""
                    messages.append({"role": "user", "content": self._EMPTY_ACTION_CORRECTION})
                    continue
                break

            any_tool_called = True
            tool_results = []
            for block in response.content:
                if getattr(block, "type", None) == "tool_use":
                    log.info(f"[im-stream] 调用工具: {block.name}({block.input})")
                    tool_input = dict(block.input)
                    tool_input["_caller_id"] = ctx.user_id
                    tool_input["_user_input"] = content
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
                    tool_input["_target_member_id"] = getattr(ctx, "target_member_id", "") or ""
                    tool_input["_caller_member_id"] = getattr(ctx, "caller_member_id", "") or ctx.user_id
                    result = await self._registry.execute_tool(block.name, tool_input)
                    log.info(f"[im-stream] 工具结果: {result[:200]}")
                    yield {"type": "tool_result", "name": block.name, "result": result}
                    tool_results.append({
                        "type": "tool_result",
                        "tool_use_id": block.id,
                        "content": result,
                    })
                    if block.name in ("contacts_sync", "contacts_bind_identity"):
                        blocked_tools.clear()
                        onboarding_hints.clear()
                        tools = self._registry.to_claude_tools(
                            permissions=ctx.permissions if ctx.permissions else None,
                            allowed_tools=ctx.allowed_tools,
                        )

            messages.append({"role": "user", "content": tool_results})
            accumulated_text = ""

        await self._sessions.save_messages(ctx.channel, ctx.user_id, messages)
        self._sessions.add_usage(
            ctx.channel, ctx.user_id, total_usage.input_tokens, total_usage.output_tokens,
            cache_creation_tokens=total_usage.cache_creation_input_tokens,
            cache_read_tokens=total_usage.cache_read_input_tokens,
        )
        log.info(
            f"[im-stream] 完成: {ctx.channel}:{ctx.user_id}, "
            f"input={total_usage.input_tokens}, output={total_usage.output_tokens}"
        )

    async def process_stream_web(
        self,
        content: str,
        member_id: str = "admin",
        images: list[dict] | None = None,
        session_id: str = "default",
        cancel_event: asyncio.Event | None = None,
        target_type: str = "ai",
        target_id: str = "",
    ):
        """Web 面板流式对话接口

        使用 Anthropic streaming API，逐块 yield 事件。
        每个成员有独立的会话历史，使用真实身份构建上下文。

        Args:
            content: 用户消息
            member_id: 成员 ID，用于独立会话和身份识别
            session_id: 会话 ID，支持多会话
            target_type: "ai" for normal AI chat, "member" for member proxy chat
            target_id: target member id when target_type="member"

        Yields:
            dict: {"type": "text_delta", "text": "..."} |
                  {"type": "tool_use", "name": "..."} |
                  {"type": "tool_result", "name": "...", "result": "..."} |
                  {"type": "thinking"}
        """
        log.info(f"[web] 开始处理流式请求: member_id={member_id}, session_id={session_id}, content_len={len(content) if content else 0}, target_type={target_type}, target_id={target_id}")
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

        # 设置目标成员和调用者信息（用于 AI 员工聊天场景）
        ctx.target_member_id = target_id or ""
        ctx.caller_member_id = member_id

        if (not content or not content.strip()) and not images:
            log.warning(f"[web] 空消息，跳过处理: member_id={member_id}, session_id={session_id}")
            return

        direct_action = await self._maybe_handle_direct_channel_send(ctx, content)
        if direct_action:
            messages = await self._sessions.get_messages(ctx.channel, ctx.user_id, session_id)
            user_content = self._build_user_content(content, images or [])
            messages.append({"role": "user", "content": user_content})
            messages.append({"role": "assistant", "content": [{"type": "text", "text": direct_action["reply_text"]}]})
            await self._sessions.save_messages(ctx.channel, ctx.user_id, messages, session_id)
            yield {"type": "tool_use", "name": direct_action["tool_name"], "id": "direct-channel-send"}
            yield {"type": "tool_result", "name": direct_action["tool_name"], "result": direct_action["tool_result"]}
            yield {"type": "text", "text": direct_action["reply_text"]}
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

        # Build system prompt: member proxy chats use a standalone persona prompt
        if target_type == "member" and target_id:
            system = await self._build_member_chat_context(target_id)
        else:
            system = self._system_prompt + sender_context

        action_hint = self._build_action_hint(content)
        if action_hint:
            system += f"\n\n# 当前操作提示\n\n{action_hint}"
        plugin_prompts = self._registry.get_system_prompt_extension()
        if plugin_prompts:
            system += "\n\n" + plugin_prompts
        if onboarding_hints:
            system += "\n\n# 插件引导（优先处理）\n\n" + "\n\n".join(onboarding_hints)

        tools = self._registry.to_claude_tools(permissions=ctx.permissions if ctx.permissions else {"*"})
        if blocked_tools:
            tools = [t for t in tools if t["name"] not in blocked_tools]
        tools = self._prioritize_tools_for_intent(content, tools)

        max_rounds = 10
        current_text = ""
        total_usage = Usage()
        completed = False
        interrupted = False
        any_tool_called = False
        correction_injected = False
        try:
            for _ in range(max_rounds):
                if cancel_event and cancel_event.is_set():
                    interrupted = True
                    break
                try:
                    collected_content = []
                    async with self._llm.stream(
                        system=system, messages=messages,
                        tools=tools if tools else None,
                    ) as stream:
                        async for event in stream:
                            if cancel_event and cancel_event.is_set():
                                interrupted = True
                                break
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

                        if interrupted:
                            break
                        response = await stream.get_final_message()
                        total_usage.input_tokens += response.usage.input_tokens
                        total_usage.output_tokens += response.usage.output_tokens
                        total_usage.cache_creation_input_tokens += response.usage.cache_creation_input_tokens
                        total_usage.cache_read_input_tokens += response.usage.cache_read_input_tokens
                except asyncio.CancelledError:
                    interrupted = True
                    break
                except Exception as e:
                    log.error(f"[web] LLM API 流式调用失败: member_id={member_id}, session_id={session_id}, error={e}")
                    reason = self._extract_error_reason(e)
                    error_text = f"抱歉，AI 服务暂时不可用：{reason}\n请稍后再试。"
                    yield {"type": "text", "text": error_text}
                    messages.append({"role": "assistant", "content": [{"type": "text", "text": error_text}]})
                    await self._sessions.save_messages(ctx.channel, ctx.user_id, messages, session_id)
                    completed = True
                    return
                if interrupted:
                    break

                if not response.content:
                    log.warning(f"[web] LLM 返回空响应: member_id={member_id}, session_id={session_id}, model={self._llm.primary_model}")
                    error_text = "抱歉，AI 服务返回了空响应，请稍后再试。"
                    current_text = error_text
                    yield {"type": "text", "text": error_text}
                    messages.append({"role": "assistant", "content": [{"type": "text", "text": error_text}]})
                    await self._sessions.save_messages(ctx.channel, ctx.user_id, messages, session_id)
                    completed = True
                    return

                messages.append({"role": "assistant", "content": self._serialize_content(response.content)})

                if response.stop_reason != "tool_use":
                    if (not any_tool_called and not correction_injected
                            and self._requires_channel_send_tool(content)):
                        log.warning("[web] 检测到通道发消息请求未调用工具，注入纠正提示重试")
                        correction_injected = True
                        current_text = ""
                        yield {"type": "text", "text": ""}
                        messages.append({
                            "role": "user",
                            "content": self._CHANNEL_SEND_ACTION_CORRECTION,
                        })
                        continue
                    if (not any_tool_called and not correction_injected
                            and self._text_claims_action(current_text)):
                        log.warning("[web] 检测到空操作：模型声称已完成但未调用工具，注入纠正提示重试")
                        correction_injected = True
                        current_text = ""
                        yield {"type": "text", "text": ""}
                        messages.append({
                            "role": "user",
                            "content": self._EMPTY_ACTION_CORRECTION,
                        })
                        continue
                    break

                any_tool_called = True
                tool_results = []
                
                # 获取用户当前输入（用于确认操作场景）
                current_user_input = content
                
                for block in response.content:
                    if getattr(block, "type", None) == "tool_use":
                        log.info(f"[web] 调用工具: {block.name}({block.input})")
                        tool_input = dict(block.input)
                        tool_input["_caller_id"] = ctx.user_id
                        tool_input["_target_member_id"] = getattr(ctx, "target_member_id", "") or ""
                        tool_input["_caller_member_id"] = getattr(ctx, "caller_member_id", "") or ctx.user_id
                        # 注入用户输入（用于确认操作场景）
                        tool_input["_user_input"] = current_user_input
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
                        # Accumulate full CLI output for persistence
                        accumulated_output: list[str] = []
                        while not tool_task.done():
                            if cancel_event and cancel_event.is_set():
                                interrupted = True
                                tool_task.cancel()
                                try:
                                    await tool_task
                                except asyncio.CancelledError:
                                    pass
                                break
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
                                    accumulated_output.append(output_chunk)
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
                        if interrupted:
                            break
                        if tool_task.cancelled():
                            interrupted = True
                            break
                        result = tool_task.result()

                        log.info(f"[web] 工具结果: {result[:500] if len(result) > 500 else result}")
                        yield {"type": "tool_result", "name": block.name, "result": result}
                        # Persist full CLI conversation in chat history: prefer accumulated live output,
                        # fall back to the final result string if no live output was produced.
                        full_output = "\n".join(accumulated_output).strip()
                        persisted_content = full_output or result
                        tool_results.append({
                            "type": "tool_result",
                            "tool_use_id": block.id,
                            "content": persisted_content,
                        })

                if interrupted:
                    break
                messages.append({"role": "user", "content": tool_results})

            if interrupted:
                saved_text = f"{current_text}..." if current_text else ""
                if saved_text and (not messages or messages[-1].get("role") != "assistant"):
                    messages.append({"role": "assistant", "content": [{"type": "text", "text": saved_text}]})
                elif saved_text and messages and messages[-1].get("role") == "assistant":
                    for block in messages[-1].get("content", []):
                        if isinstance(block, dict) and block.get("type") == "text":
                            block["text"] = saved_text
                            break
                return

            # Save and yield usage on normal completion
            await self._sessions.save_messages(ctx.channel, ctx.user_id, messages, session_id)
            self._sessions.add_usage(
                ctx.channel, ctx.user_id, total_usage.input_tokens, total_usage.output_tokens,
                session_id,
                cache_creation_tokens=total_usage.cache_creation_input_tokens,
                cache_read_tokens=total_usage.cache_read_input_tokens,
            )
            completed = True
            log.info(f"[web] 流式请求完成: member_id={member_id}, session_id={session_id}, input={total_usage.input_tokens}, output={total_usage.output_tokens}")

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

    # Action-claim keywords for empty-action detection
    _ACTION_CLAIMS = (
        "已完成", "已创建", "已添加", "已修改", "已删除", "已更新",
        "已建好", "已加好", "已改好", "已搞定", "已处理", "已配置",
        "已提交", "已推送", "已部署", "已执行", "已生成", "已写入",
        "完成了", "创建了", "添加了", "修改了", "删除了", "更新了",
        "已开始并完成", "已经完成", "已经创建", "已经添加",
        "操作完成", "执行完毕", "处理完毕",
    )

    _EMPTY_ACTION_CORRECTION = (
        "[系统自动检查] 严重错误：你声称已完成操作，但你没有调用任何工具。"
        "用户要求的操作必须通过工具调用来执行。"
        "请重新检查用户的请求，从可用工具中选择合适的工具并立即调用。"
        "如果没有合适的工具，请明确告知用户当前无法执行该操作及原因。"
    )
    _CHANNEL_SEND_ACTION_CORRECTION = (
        "[系统自动检查] 用户当前是在要求你主动通过 IM 发消息，这是执行操作，不是知识问答。"
        "如果可用工具中有 `feishu_send_message`、`feishu_send_voice`、`wecom_send_message`、`wecom_send_voice`、`dingtalk_send_message` 或 `dingtalk_send_voice`，你必须立即调用对应工具。"
        "当用户说“给我的飞书/企微/钉钉发消息”时，可省略 user_id，让工具默认发送给当前用户已绑定的账号。"
        "如果当前用户没有绑定对应账号，也要通过工具返回真实错误，不要只做解释。"
    )

    @classmethod
    def _text_claims_action(cls, text: str) -> bool:
        """Check if text claims to have completed an action."""
        if not text:
            return False
        return any(claim in text for claim in cls._ACTION_CLAIMS)

    @staticmethod
    def _requires_channel_send_tool(text: str) -> bool:
        """Detect requests that should use IM channel send tools."""
        if not text:
            return False
        normalized = "".join(text.split())
        if any(keyword in normalized for keyword in ("怎么", "如何", "为什么", "能不能", "可不可以")):
            return False
        mentions_channel = any(keyword in normalized for keyword in ("飞书", "企微", "企业微信", "钉钉"))
        mentions_send = any(keyword in normalized for keyword in ("发消息", "发送消息", "发一条", "发个", "通知", "提醒", "代发", "主动发", "发语音", "语音提醒", "语音通知"))
        mentions_target = any(keyword in normalized for keyword in ("给我", "给我的", "帮我", "替我", "给", "发给"))
        return mentions_channel and mentions_send and mentions_target

    @classmethod
    def _build_action_hint(cls, text: str) -> str:
        if not cls._requires_channel_send_tool(text):
            return ""
        return (
            "用户当前是在要求你主动通过飞书/企微发送消息。"
            "这类请求必须调用对应的通道工具执行，不要只回复说明文字。"
        )

    @classmethod
    def _prioritize_tools_for_intent(cls, text: str, tools: list[dict]) -> list[dict]:
        if not cls._requires_channel_send_tool(text):
            return tools

        normalized = "".join((text or "").split())
        tool_map = {tool["name"]: tool for tool in tools}
        prioritized_names: list[str] = []

        if "飞书" in normalized:
            if "语音" in normalized:
                prioritized_names.append("feishu_send_voice")
            prioritized_names.extend(["feishu_send_message"] if "语音" in normalized else ["feishu_send_message", "feishu_send_voice"])
        if "企微" in normalized or "企业微信" in normalized:
            if "语音" in normalized:
                prioritized_names.append("wecom_send_voice")
            prioritized_names.extend(["wecom_send_message", "wecom_send_voice"])
        if "钉钉" in normalized:
            if "语音" in normalized:
                prioritized_names.append("dingtalk_send_voice")
            prioritized_names.extend(["dingtalk_send_message", "dingtalk_send_voice"])

        prioritized_names.append("contacts_search")
        prioritized = [tool_map[name] for name in prioritized_names if name in tool_map]
        return prioritized or tools

    async def _maybe_handle_direct_channel_send(self, ctx: RequestContext, text: str) -> dict | None:
        """Handle simple 'send a message to my bound IM account' requests without relying on LLM routing."""
        parsed = self._parse_direct_channel_send_request(text)
        if not parsed:
            return None

        log.info(f"命中直发通道消息兜底: tool={parsed['tool_name']} text={text[:80]}")
        tool_name = parsed["tool_name"]
        payload_key = "text" if tool_name in {"wecom_send_voice", "feishu_send_voice"} else "content"
        tool_input = {
            payload_key: parsed["message"],
            "_caller_id": ctx.user_id,
            "_caller_member_id": getattr(ctx, "caller_member_id", "") or ctx.user_id,
            "_target_member_id": getattr(ctx, "target_member_id", "") or "",
        }
        if ctx.member:
            tool_input["_member_id"] = ctx.member.id

        tool_result = await self._registry.execute_tool(tool_name, tool_input)
        log.info(f"直发通道消息结果: tool={tool_name} result={tool_result[:200]}")
        reply_text = self._format_direct_channel_send_reply(tool_result)
        return {
            "tool_name": tool_name,
            "tool_result": tool_result,
            "reply_text": reply_text,
        }

    @classmethod
    def _parse_direct_channel_send_request(cls, text: str) -> dict | None:
        if not text:
            return None
        normalized = "".join(text.split())
        if not cls._requires_channel_send_tool(normalized):
            return None
        if not any(keyword in normalized for keyword in ("给我的", "给我", "我的飞书", "我的企微", "我的企业微信")):
            return None

        tool_name = ""
        if "飞书" in normalized:
            tool_name = "feishu_send_voice" if "语音" in normalized else "feishu_send_message"
        elif "企微" in normalized or "企业微信" in normalized:
            tool_name = "wecom_send_voice" if "语音" in normalized else "wecom_send_message"
        elif "钉钉" in normalized:
            tool_name = "dingtalk_send_voice" if "语音" in normalized else "dingtalk_send_message"
        if not tool_name:
            return None

        message = cls._extract_direct_channel_message(text)
        if not message:
            return None
        return {"tool_name": tool_name, "message": message}

    @staticmethod
    def _extract_direct_channel_message(text: str) -> str:
        patterns = [
            r"发(?:一条|条|个|一下)?[\"“']?(?P<msg>.+?)[\"”']?(?:的)?(?:消息|信息)",
            r"发送(?:一条|条|个)?[\"“']?(?P<msg>.+?)[\"”']?(?:的)?(?:消息|信息)",
            r"发(?:个|一下)?语音(?:提醒|通知)?[\"“']?(?P<msg>.+?)[\"”']?$",
            r"发送语音(?:提醒|通知)?[\"“']?(?P<msg>.+?)[\"”']?$",
            r"说[\"“']?(?P<msg>.+?)[\"”']?$",
        ]
        for pattern in patterns:
            match = re.search(pattern, text)
            if not match:
                continue
            message = (match.group("msg") or "").strip().strip("“”\"'")
            if message:
                return message
        return ""

    @staticmethod
    def _format_direct_channel_send_reply(tool_result: str) -> str:
        try:
            payload = json.loads(tool_result)
        except json.JSONDecodeError:
            return tool_result
        if isinstance(payload, dict):
            return str(payload.get("message") or tool_result)
        return tool_result

    def _detect_empty_action(self, response: LLMResponse) -> bool:
        """Check if LLM response claims completion without having called tools."""
        return self._text_claims_action(self._extract_text(response))

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

    async def _build_member_chat_context(self, target_id: str) -> str:
        """Build a complete standalone system prompt for member proxy chat.

        Returns a full persona prompt (NOT a fragment to append) so the AI
        fully embodies this member instead of acting as an AI assistant.
        Two styles: minimal (no bio) vs rich (with bio).
        Falls back to the default SYSTEM_PROMPT on error.
        """
        try:
            from openvort.web.deps import get_db_session_factory
            from openvort.contacts.models import Member

            session_factory = get_db_session_factory()
            if not session_factory:
                return self._system_prompt

            async with session_factory() as db:
                m = await db.get(Member, target_id)
                if not m:
                    return self._system_prompt

            remote_node_info = await self._get_remote_node_info(m)

            if m.bio:
                return self._build_rich_member_prompt(m, [], remote_node_info)
            else:
                return self._build_minimal_member_prompt(m, remote_node_info)
        except Exception as e:
            log.warning(f"[web] 构建成员对话上下文失败: {e}")
            return self._system_prompt

    async def _get_remote_node_info(self, member) -> dict | None:
        """Look up the remote work node bound to this member, if any."""
        node_id = getattr(member, "remote_node_id", "") or ""
        if not node_id:
            return None
        try:
            from openvort.web.deps import get_db_session_factory
            from openvort.db.models import RemoteNode

            sf = get_db_session_factory()
            if not sf:
                return None
            async with sf() as db:
                node = await db.get(RemoteNode, node_id)
                if not node:
                    return None
                return {"name": node.name, "gateway_url": node.gateway_url, "status": node.status}
        except Exception:
            return None

    @staticmethod
    def _build_minimal_member_prompt(member, remote_node_info: dict | None = None) -> str:
        """Persona prompt for a member without skills/bio — a friendly colleague."""
        if member.position:
            parts = [f"你是「{member.name}」，团队的{member.position}。你正在通过 IM 跟同事聊天。"]
        else:
            parts = [f"你是「{member.name}」，团队的一名成员。你正在通过 IM 跟同事聊天。"]

        info_lines = [f"- 姓名: {member.name}"]
        if member.position:
            info_lines.append(f"- 职位: {member.position}")
        if member.email:
            info_lines.append(f"- 邮箱: {member.email}")
        if member.phone:
            info_lines.append(f"- 手机: {member.phone}")
        parts.append("\n## 基本信息\n" + "\n".join(info_lines))

        if remote_node_info:
            parts.append(AgentRuntime._build_remote_node_prompt_section(remote_node_info))

        parts.append(AgentRuntime._build_async_task_prompt())

        parts.append(f"""
## 行为准则
- 像正常同事聊天一样说话，简洁自然，不要太正式
- 如果对方只是打招呼，就简短地回应，不需要自我介绍
- 如果被问到不了解的领域，坦诚说不太清楚，建议找更合适的人
- 回答要符合你的职位角色，从你的职位专业视角出发
- 可以使用工具查询你的任务、代码提交等工作数据
- 绝对不要提到你是 AI、助手或机器人，也不要罗列你的能力
- 用中文回复""")
        return "\n".join(parts)

    @staticmethod
    def _build_rich_member_prompt(member, skill_contents: list[str], remote_node_info: dict | None = None) -> str:
        """Persona prompt for a member with skills/bio — a domain expert."""
        if member.position:
            parts = [f"你是「{member.name}」，团队的{member.position}。"]
        else:
            parts = [f"你是「{member.name}」。"]

        if member.bio:
            parts.append(f"\n## 个人简介\n{member.bio}")

        info_lines = []
        if member.position:
            info_lines.append(f"- 职位: {member.position}")
        if member.email:
            info_lines.append(f"- 邮箱: {member.email}")
        if member.phone:
            info_lines.append(f"- 手机: {member.phone}")
        if info_lines:
            parts.append("\n## 基本信息\n" + "\n".join(info_lines))

        if skill_contents:
            parts.append("\n## 专业技能与背景知识\n" + "\n\n".join(skill_contents))

        if remote_node_info:
            parts.append(AgentRuntime._build_remote_node_prompt_section(remote_node_info))

        parts.append(AgentRuntime._build_async_task_prompt())

        parts.append(f"""
## 行为准则
- 完全以{member.name}的身份交流，就像真正的{member.name}在跟同事说话
- 在你擅长的领域自信地分享见解和建议
- 不擅长的领域诚实说不太了解，可以推荐找谁问
- 语气自然随和，像同事间的日常对话
- 如果对方只是打招呼，就简短回应，不需要自我介绍或展示能力
- 可以使用工具查询任务、代码提交等工作数据来支撑回答
- 绝对不要提到你是 AI、助手或机器人
- 用中文回复""")
        return "\n".join(parts)

    @staticmethod
    def _build_remote_node_prompt_section(info: dict) -> str:
        """Build system prompt section describing remote work capability."""
        node_name = info.get("name", "远程节点")
        status = info.get("status", "unknown")
        status_label = {"online": "在线", "offline": "离线"}.get(status, "未知")
        return f"""
## 远程工作环境

你拥有一台远程工作电脑「{node_name}」（当前状态: {status_label}），可以通过 `remote_work` 工具在上面执行实际操作。

**使用场景**: 当同事要求你执行编码、运行命令、操作文件、部署、调试等需要在电脑上完成的任务时，使用 `remote_work` 工具将指令发送到远程电脑执行。

**触发关键词**: 当对话中出现「远程」「在你电脑上」「帮我跑一下」「执行」「部署」「写代码」「改代码」「运行」等意图时，主动使用此工具。

**使用方式**: 调用 `remote_work` 工具，在 `instruction` 参数中用自然语言描述要执行的任务。远程电脑会理解并执行指令，返回结果。

**登录与认证**: 如果远程执行结果显示需要登录网站、授权第三方服务、输入验证码等需要人工交互的操作，你应该：
1. 告知同事需要先在远程电脑「{node_name}」上手动完成登录/授权
2. 说明具体需要登录哪个网站或服务
3. 等同事确认登录完成后，再继续执行原任务"""

    @staticmethod
    def _build_async_task_prompt() -> str:
        return """
## 任务执行模式

当同事要求你执行需要多步操作或预计耗时较长的任务时（如执行代码、远程操作、查询数据等），请先用一句简短的话确认你已接手（如"好的，我来处理，完成后通知你"），然后继续执行。这样同事可以放心去做其他事。

对于快速问答（不涉及工具调用的简单对话），直接正常回复即可，不需要确认。"""

    @staticmethod
    def _build_user_content(text: str, images: list[dict]) -> str | list[dict]:
        """构建用户消息 content（纯文本或多模态）

        无图片时返回纯字符串（节省 token），有图片时返回 content blocks。
        同时把 pic_url 写入文本，确保后续轮次 AI 也能引用图片 URL。
        file_url is persisted in image blocks for history recovery.
        """
        normalized_text = AgentRuntime._normalize_user_text(text)
        if not images:
            return normalized_text

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

        if normalized_text and normalized_text.strip():
            blocks.append({"type": "text", "text": normalized_text + url_hint})
        else:
            blocks.append({"type": "text", "text": "请看图片" + url_hint})

        return blocks

    @staticmethod
    def _normalize_user_text(text: str) -> str:
        """Normalize special channel markers before sending them to the LLM."""
        value = text or ""
        if value.startswith("[语音消息]"):
            spoken_text = value[len("[语音消息]"):].lstrip("\n").strip()
            if spoken_text:
                return (
                    "[系统说明] 以下内容来自一条已经完成 ASR 转写的语音消息，"
                    "请直接按用户原话理解并回答，不要再说无法识别语音。\n"
                    f"{spoken_text}"
                )
        return value
