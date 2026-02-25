"""
Agent Runtime

基于 Claude tool use 的 agentic loop。
不依赖 LangChain 等框架，保持轻量可控。
"""

import anthropic

from openvort.config.settings import LLMSettings
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
        self._client = anthropic.AsyncAnthropic(
            api_key=llm_settings.api_key,
            base_url=llm_settings.api_base if llm_settings.api_base != "https://api.anthropic.com" else None,
            timeout=llm_settings.timeout,
        )
        self._model = llm_settings.model
        self._max_tokens = llm_settings.max_tokens
        self._registry = registry
        self._sessions = session_store
        self._system_prompt = system_prompt

    async def process(self, channel: str, user_id: str, content: str) -> str:
        """处理一条用户消息，返回回复文本

        Args:
            channel: 来源通道标识（如 "wecom"）
            user_id: 用户 ID
            content: 消息内容

        Returns:
            AI 回复文本
        """
        # 1. 加载对话历史，追加用户消息
        messages = self._sessions.get_messages(channel, user_id)
        messages.append({"role": "user", "content": content})

        # 2. 获取可用工具
        tools = self._registry.to_claude_tools()

        # 3. Agentic loop
        max_rounds = 10  # 防止无限循环
        for _ in range(max_rounds):
            try:
                kwargs = {
                    "model": self._model,
                    "max_tokens": self._max_tokens,
                    "system": self._system_prompt,
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
                    result = await self._registry.execute_tool(block.name, block.input)
                    log.info(f"工具结果: {result[:200]}")
                    tool_results.append({
                        "type": "tool_result",
                        "tool_use_id": block.id,
                        "content": result,
                    })

            # 回传工具结果
            messages.append({"role": "user", "content": tool_results})

        # 4. 保存对话历史
        self._sessions.save_messages(channel, user_id, messages)

        # 5. 提取文本回复
        return self._extract_text(response)

    async def chat(self, content: str) -> str:
        """简单对话接口（无 channel/user 上下文，用于 CLI 调试）"""
        return await self.process("cli", "debug", content)

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
