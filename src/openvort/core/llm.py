"""
统一 LLM 调用层

支持多 Provider（Anthropic / OpenAI 兼容），failover 链，统一响应格式。
Agent 代码只依赖此模块，不直接引用具体 SDK。
"""

from __future__ import annotations

import json
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any

from openvort.utils.logging import get_logger

log = get_logger("core.llm")


# ============ 统一响应模型（兼容 Anthropic 属性访问风格） ============


@dataclass
class TextBlock:
    text: str = ""
    type: str = "text"


@dataclass
class ToolUseBlock:
    id: str = ""
    name: str = ""
    input: dict = field(default_factory=dict)
    type: str = "tool_use"


@dataclass
class Usage:
    input_tokens: int = 0
    output_tokens: int = 0


@dataclass
class LLMResponse:
    content: list = field(default_factory=list)
    stop_reason: str = "end_turn"
    usage: Usage = field(default_factory=Usage)


# ============ 流式事件模型 ============


@dataclass
class ContentBlockStart:
    type: str = "content_block_start"
    content_block: Any = None


@dataclass
class ContentBlockDelta:
    type: str = "content_block_delta"
    delta: Any = None


@dataclass
class TextDelta:
    type: str = "text_delta"
    text: str = ""


@dataclass
class InputJsonDelta:
    type: str = "input_json_delta"
    partial_json: str = ""


# ============ Provider 基类 ============


class LLMProvider(ABC):
    """LLM Provider 抽象基类"""

    @abstractmethod
    async def create(self, *, model: str, max_tokens: int, system: str,
                     messages: list[dict], tools: list[dict] | None = None,
                     thinking: dict | None = None) -> LLMResponse:
        """同步调用 LLM，返回完整响应"""
        ...

    @abstractmethod
    def stream(self, *, model: str, max_tokens: int, system: str,
               messages: list[dict], tools: list[dict] | None = None,
               thinking: dict | None = None):
        """流式调用 LLM，返回 async context manager"""
        ...

    @abstractmethod
    async def close(self) -> None:
        ...


# ============ Anthropic Provider ============


class AnthropicProvider(LLMProvider):
    """Anthropic Claude Provider"""

    def __init__(self, api_key: str, api_base: str = "", timeout: int = 120):
        import anthropic
        kwargs: dict[str, Any] = {"api_key": api_key, "timeout": timeout}
        if api_base and api_base != "https://api.anthropic.com":
            kwargs["base_url"] = api_base
        self._client = anthropic.AsyncAnthropic(**kwargs)

    async def create(self, *, model: str, max_tokens: int, system: str,
                     messages: list[dict], tools: list[dict] | None = None,
                     thinking: dict | None = None) -> LLMResponse:
        kwargs: dict[str, Any] = {
            "model": model, "max_tokens": max_tokens,
            "system": system, "messages": messages,
        }
        if tools:
            kwargs["tools"] = tools
        if thinking:
            kwargs["thinking"] = thinking
        resp = await self._client.messages.create(**kwargs)
        return self._convert_response(resp)

    def stream(self, *, model: str, max_tokens: int, system: str,
               messages: list[dict], tools: list[dict] | None = None,
               thinking: dict | None = None):
        kwargs: dict[str, Any] = {
            "model": model, "max_tokens": max_tokens,
            "system": system, "messages": messages,
        }
        if tools:
            kwargs["tools"] = tools
        if thinking:
            kwargs["thinking"] = thinking
        return AnthropicStreamWrapper(self._client, kwargs)

    async def close(self) -> None:
        pass

    @staticmethod
    def _convert_response(resp) -> LLMResponse:
        content = []
        for block in resp.content:
            if block.type == "text":
                content.append(TextBlock(text=block.text))
            elif block.type == "tool_use":
                content.append(ToolUseBlock(id=block.id, name=block.name, input=block.input))
        usage = Usage(
            input_tokens=getattr(resp.usage, "input_tokens", 0),
            output_tokens=getattr(resp.usage, "output_tokens", 0),
        )
        return LLMResponse(content=content, stop_reason=resp.stop_reason or "end_turn", usage=usage)


class AnthropicStreamWrapper:
    """Anthropic 流式调用包装器，提供统一的 async iteration 接口"""

    def __init__(self, client, kwargs: dict):
        self._client = client
        self._kwargs = kwargs
        self._stream = None

    async def __aenter__(self):
        self._stream = self._client.messages.stream(**self._kwargs)
        self._inner = await self._stream.__aenter__()
        return self

    async def __aexit__(self, *args):
        if self._stream:
            await self._stream.__aexit__(*args)

    async def __aiter__(self):
        async for event in self._inner:
            if event.type == "content_block_start":
                block = event.content_block
                if block.type == "text":
                    yield ContentBlockStart(content_block=TextBlock())
                elif block.type == "tool_use":
                    yield ContentBlockStart(
                        content_block=ToolUseBlock(id=block.id, name=block.name)
                    )
            elif event.type == "content_block_delta":
                delta = event.delta
                if delta.type == "text_delta":
                    yield ContentBlockDelta(delta=TextDelta(text=delta.text))
                elif delta.type == "input_json_delta":
                    yield ContentBlockDelta(delta=InputJsonDelta(partial_json=delta.partial_json))

    async def get_final_message(self) -> LLMResponse:
        resp = await self._inner.get_final_message()
        return AnthropicProvider._convert_response(resp)


# ============ OpenAI-Compatible Provider ============


class OpenAICompatibleProvider(LLMProvider):
    """OpenAI 兼容 Provider（支持 OpenAI / DeepSeek / 通义千问等）

    将 Claude tool_use 格式转换为 OpenAI function_calling 格式。
    """

    def __init__(self, api_key: str, api_base: str = "https://api.openai.com/v1",
                 timeout: int = 120):
        import httpx
        self._api_base = api_base.rstrip("/")
        self._headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }
        self._http = httpx.AsyncClient(timeout=timeout, headers=self._headers)

    async def create(self, *, model: str, max_tokens: int, system: str,
                     messages: list[dict], tools: list[dict] | None = None,
                     thinking: dict | None = None) -> LLMResponse:
        oai_messages = self._convert_messages(system, messages)
        body: dict[str, Any] = {
            "model": model, "max_tokens": max_tokens, "messages": oai_messages,
        }
        if tools:
            body["tools"] = self._convert_tools(tools)
        resp = await self._http.post(f"{self._api_base}/chat/completions", json=body)
        resp.raise_for_status()
        return self._parse_response(resp.json())

    def stream(self, *, model: str, max_tokens: int, system: str,
               messages: list[dict], tools: list[dict] | None = None,
               thinking: dict | None = None):
        oai_messages = self._convert_messages(system, messages)
        body: dict[str, Any] = {
            "model": model, "max_tokens": max_tokens,
            "messages": oai_messages, "stream": True,
        }
        if tools:
            body["tools"] = self._convert_tools(tools)
        return OpenAIStreamWrapper(self._http, f"{self._api_base}/chat/completions", body)

    async def close(self) -> None:
        await self._http.aclose()

    @staticmethod
    def _convert_messages(system: str, messages: list[dict]) -> list[dict]:
        """将 Anthropic 格式消息转为 OpenAI 格式"""
        oai = [{"role": "system", "content": system}]
        for msg in messages:
            role = msg["role"]
            content = msg.get("content", "")
            if role == "user":
                if isinstance(content, list):
                    # tool_result 列表
                    if content and isinstance(content[0], dict) and content[0].get("type") == "tool_result":
                        for tr in content:
                            oai.append({
                                "role": "tool",
                                "tool_call_id": tr.get("tool_use_id", ""),
                                "content": tr.get("content", ""),
                            })
                    else:
                        # 多模态内容 — 简化为纯文本
                        text_parts = [b.get("text", "") for b in content if isinstance(b, dict) and b.get("type") == "text"]
                        oai.append({"role": "user", "content": "\n".join(text_parts) or str(content)})
                else:
                    oai.append({"role": "user", "content": content})
            elif role == "assistant":
                if isinstance(content, list):
                    text_parts = []
                    tool_calls = []
                    for block in content:
                        if isinstance(block, dict):
                            if block.get("type") == "text":
                                text_parts.append(block.get("text", ""))
                            elif block.get("type") == "tool_use":
                                tool_calls.append({
                                    "id": block.get("id", ""),
                                    "type": "function",
                                    "function": {
                                        "name": block.get("name", ""),
                                        "arguments": json.dumps(block.get("input", {})),
                                    },
                                })
                    msg_dict: dict[str, Any] = {"role": "assistant", "content": "\n".join(text_parts) or None}
                    if tool_calls:
                        msg_dict["tool_calls"] = tool_calls
                    oai.append(msg_dict)
                else:
                    oai.append({"role": "assistant", "content": content})
        return oai

    @staticmethod
    def _convert_tools(tools: list[dict]) -> list[dict]:
        """将 Claude tool 格式转为 OpenAI function 格式"""
        return [
            {
                "type": "function",
                "function": {
                    "name": t["name"],
                    "description": t.get("description", ""),
                    "parameters": t.get("input_schema", {}),
                },
            }
            for t in tools
        ]

    @staticmethod
    def _parse_response(data: dict) -> LLMResponse:
        choice = data.get("choices", [{}])[0]
        msg = choice.get("message", {})
        content: list = []
        if msg.get("content"):
            content.append(TextBlock(text=msg["content"]))
        for tc in msg.get("tool_calls", []):
            fn = tc.get("function", {})
            try:
                args = json.loads(fn.get("arguments", "{}"))
            except json.JSONDecodeError:
                args = {}
            content.append(ToolUseBlock(id=tc.get("id", ""), name=fn.get("name", ""), input=args))
        stop = choice.get("finish_reason", "stop")
        stop_reason = "tool_use" if stop == "tool_calls" else "end_turn"
        usage_data = data.get("usage", {})
        usage = Usage(
            input_tokens=usage_data.get("prompt_tokens", 0),
            output_tokens=usage_data.get("completion_tokens", 0),
        )
        return LLMResponse(content=content, stop_reason=stop_reason, usage=usage)


class OpenAIStreamWrapper:
    """OpenAI SSE 流式包装器"""

    def __init__(self, http, url: str, body: dict):
        self._http = http
        self._url = url
        self._body = body
        self._response = None
        self._final_content: list = []
        self._final_usage = Usage()

    async def __aenter__(self):
        self._response = await self._http.stream("POST", self._url, json=self._body)
        self._stream = await self._response.__aenter__()
        return self

    async def __aexit__(self, *args):
        if self._response:
            await self._response.__aexit__(*args)

    async def __aiter__(self):
        current_text = ""
        tool_calls: dict[int, dict] = {}
        async for line in self._stream.aiter_lines():
            if not line.startswith("data: "):
                continue
            payload = line[6:]
            if payload == "[DONE]":
                break
            try:
                chunk = json.loads(payload)
            except json.JSONDecodeError:
                continue
            delta = chunk.get("choices", [{}])[0].get("delta", {})
            if delta.get("content"):
                current_text += delta["content"]
                yield ContentBlockDelta(delta=TextDelta(text=delta["content"]))
            for tc in delta.get("tool_calls", []):
                idx = tc.get("index", 0)
                if idx not in tool_calls:
                    tool_calls[idx] = {"id": tc.get("id", ""), "name": "", "arguments": ""}
                    fn = tc.get("function", {})
                    if fn.get("name"):
                        tool_calls[idx]["name"] = fn["name"]
                        yield ContentBlockStart(
                            content_block=ToolUseBlock(id=tc.get("id", ""), name=fn["name"])
                        )
                fn = tc.get("function", {})
                if fn.get("arguments"):
                    tool_calls[idx]["arguments"] += fn["arguments"]
            if chunk.get("usage"):
                u = chunk["usage"]
                self._final_usage = Usage(
                    input_tokens=u.get("prompt_tokens", 0),
                    output_tokens=u.get("completion_tokens", 0),
                )
        # 构建 final content
        if current_text:
            self._final_content.append(TextBlock(text=current_text))
        for tc_data in tool_calls.values():
            try:
                args = json.loads(tc_data["arguments"] or "{}")
            except json.JSONDecodeError:
                args = {}
            self._final_content.append(
                ToolUseBlock(id=tc_data["id"], name=tc_data["name"], input=args)
            )

    async def get_final_message(self) -> LLMResponse:
        stop = "tool_use" if any(isinstance(b, ToolUseBlock) for b in self._final_content) else "end_turn"
        return LLMResponse(content=self._final_content, stop_reason=stop, usage=self._final_usage)


# ============ Provider 工厂 + Failover 客户端 ============


def create_provider(provider: str, api_key: str, api_base: str = "",
                    timeout: int = 120) -> LLMProvider:
    """根据 provider 名称创建对应的 LLM Provider"""
    if provider == "anthropic":
        return AnthropicProvider(api_key=api_key, api_base=api_base, timeout=timeout)
    else:
        # openai / deepseek / moonshot / qwen 等均走 OpenAI 兼容协议
        base = api_base or _default_api_base(provider)
        return OpenAICompatibleProvider(api_key=api_key, api_base=base, timeout=timeout)


def _default_api_base(provider: str) -> str:
    """常见 Provider 的默认 API 地址"""
    defaults = {
        "openai": "https://api.openai.com/v1",
        "deepseek": "https://api.deepseek.com/v1",
        "moonshot": "https://api.moonshot.cn/v1",
        "qwen": "https://dashscope.aliyuncs.com/compatible-mode/v1",
        "zhipu": "https://open.bigmodel.cn/api/paas/v4",
    }
    return defaults.get(provider, "https://api.openai.com/v1")


class LLMClient:
    """带 Failover 的 LLM 客户端

    按配置的模型列表依次尝试，主模型失败时自动切换到备选模型。
    """

    def __init__(self, models: list[dict]):
        """
        Args:
            models: 模型配置列表，每项包含:
                provider, api_key, api_base, model, max_tokens, timeout
                第一个为主模型，后续为 fallback
        """
        self._models = models
        self._providers: dict[str, LLMProvider] = {}

    def _get_provider(self, cfg: dict) -> LLMProvider:
        key = f"{cfg['provider']}:{cfg.get('api_base', '')}"
        if key not in self._providers:
            self._providers[key] = create_provider(
                provider=cfg["provider"],
                api_key=cfg["api_key"],
                api_base=cfg.get("api_base", ""),
                timeout=cfg.get("timeout", 120),
            )
        return self._providers[key]

    async def create(self, *, system: str, messages: list[dict],
                     tools: list[dict] | None = None,
                     thinking: dict | None = None) -> LLMResponse:
        """调用 LLM（带 failover）"""
        last_error = None
        for cfg in self._models:
            provider = self._get_provider(cfg)
            try:
                return await provider.create(
                    model=cfg["model"],
                    max_tokens=cfg.get("max_tokens", 4096),
                    system=system, messages=messages,
                    tools=tools, thinking=thinking,
                )
            except Exception as e:
                last_error = e
                log.warning(f"模型 {cfg['model']} 调用失败: {e}，尝试 fallback...")
        raise last_error or RuntimeError("所有模型均不可用")

    def stream(self, *, system: str, messages: list[dict],
               tools: list[dict] | None = None,
               thinking: dict | None = None):
        """流式调用（使用主模型，不做 failover）"""
        cfg = self._models[0]
        provider = self._get_provider(cfg)
        return provider.stream(
            model=cfg["model"],
            max_tokens=cfg.get("max_tokens", 4096),
            system=system, messages=messages,
            tools=tools, thinking=thinking,
        )

    @property
    def primary_model(self) -> str:
        return self._models[0]["model"] if self._models else "unknown"

    async def close(self) -> None:
        for p in self._providers.values():
            await p.close()

