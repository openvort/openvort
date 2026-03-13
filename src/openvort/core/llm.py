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
    cache_creation_input_tokens: int = 0
    cache_read_input_tokens: int = 0


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


@dataclass
class ThinkingBlock:
    thinking: str = ""
    type: str = "thinking"


@dataclass
class ThinkingDelta:
    type: str = "thinking_delta"
    thinking: str = ""


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
        import httpx
        # connect=15s (fast fail on unreachable), read=timeout (streaming needs long read)
        http_timeout = httpx.Timeout(timeout, connect=15.0)
        kwargs: dict[str, Any] = {"api_key": api_key, "timeout": http_timeout, "max_retries": 1}
        is_official = not api_base or api_base.rstrip("/") == "https://api.anthropic.com"
        if not is_official:
            base = api_base.rstrip("/")
            if base.endswith("/v1"):
                base = base[:-3]
            kwargs["base_url"] = base
        self._client = anthropic.AsyncAnthropic(**kwargs)
        self._enable_caching = is_official

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
        if self._enable_caching:
            self._apply_caching(kwargs)
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
        if self._enable_caching:
            self._apply_caching(kwargs)
        return AnthropicStreamWrapper(self._client, kwargs)

    async def close(self) -> None:
        pass

    @staticmethod
    def _apply_caching(kwargs: dict) -> None:
        """Add cache_control breakpoints to system prompt and tools."""
        system = kwargs.get("system", "")
        if system:
            kwargs["system"] = [
                {"type": "text", "text": system, "cache_control": {"type": "ephemeral"}}
            ]

        tools = kwargs.get("tools")
        if tools:
            tools = [dict(t) for t in tools]
            tools[-1] = {**tools[-1], "cache_control": {"type": "ephemeral"}}
            kwargs["tools"] = tools

    @staticmethod
    def _convert_response(resp) -> LLMResponse:
        content = []
        for block in resp.content:
            if block.type == "text":
                content.append(TextBlock(text=block.text))
            elif block.type == "tool_use":
                content.append(ToolUseBlock(id=block.id, name=block.name, input=block.input))
            elif block.type == "thinking":
                content.append(ThinkingBlock(thinking=getattr(block, "thinking", "")))
        usage = Usage(
            input_tokens=getattr(resp.usage, "input_tokens", 0),
            output_tokens=getattr(resp.usage, "output_tokens", 0),
            cache_creation_input_tokens=getattr(resp.usage, "cache_creation_input_tokens", 0) or 0,
            cache_read_input_tokens=getattr(resp.usage, "cache_read_input_tokens", 0) or 0,
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
                elif block.type == "thinking":
                    yield ContentBlockStart(content_block=ThinkingBlock())
            elif event.type == "content_block_delta":
                delta = event.delta
                if delta.type == "text_delta":
                    yield ContentBlockDelta(delta=TextDelta(text=delta.text))
                elif delta.type == "input_json_delta":
                    yield ContentBlockDelta(delta=InputJsonDelta(partial_json=delta.partial_json))
                elif delta.type == "thinking_delta":
                    yield ContentBlockDelta(delta=ThinkingDelta(thinking=delta.thinking))

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
        base = api_base.rstrip("/")
        if not base.endswith("/v1"):
            base = base + "/v1"
        self._api_base = base
        self._headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }
        self._http = httpx.AsyncClient(timeout=timeout, headers=self._headers)

    async def create(self, *, model: str, max_tokens: int, system: str,
                     messages: list[dict], tools: list[dict] | None = None,
                     thinking: dict | None = None) -> LLMResponse:
        oai_messages = self._convert_messages(system, messages, model)
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
        oai_messages = self._convert_messages(system, messages, model)
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
    def _supports_vision(model: str) -> bool:
        """按模型名推断是否支持视觉输入。"""
        model_lower = model.lower()

        # 明确不支持视觉的常见推理模型
        no_vision_markers = ("reasoner", "r1", "o1", "o3")
        if any(marker in model_lower for marker in no_vision_markers):
            return False

        # 常见视觉模型命名
        vision_markers = (
            "gpt-4o",
            "gpt-4.1",
            "gpt-4",
            "gpt-5",
            "claude",
            "vision",
            "qwen-vl",
            "vl-",
            "glm-4v",
            "gemini",
        )
        return any(marker in model_lower for marker in vision_markers)

    @staticmethod
    def _anthropic_image_to_data_url(block: dict) -> str | None:
        """将 Anthropic image block 转为 data URL。"""
        source = block.get("source")
        if not isinstance(source, dict):
            return None

        source_type = source.get("type")
        if source_type == "base64":
            data = source.get("data")
            if not data:
                return None
            media_type = source.get("media_type", "image/jpeg")
            return f"data:{media_type};base64,{data}"

        if source_type == "url":
            url = source.get("url")
            return url if isinstance(url, str) and url else None

        return None

    def _convert_user_content_for_model(self, content: list[dict], model: str) -> Any:
        """将用户多模态 content 按模型能力转换到 OpenAI 兼容格式。"""
        image_count = sum(1 for b in content if isinstance(b, dict) and b.get("type") == "image")
        supports_vision = self._supports_vision(model)
        if image_count > 0:
            log.info(f"OpenAI-compatible 多模态转换: model={model}, images={image_count}, supports_vision={supports_vision}")

        if supports_vision:
            multimodal_parts: list[dict] = []
            for block in content:
                if not isinstance(block, dict):
                    continue
                block_type = block.get("type")
                if block_type == "text":
                    multimodal_parts.append({"type": "text", "text": block.get("text", "")})
                elif block_type == "image":
                    data_url = self._anthropic_image_to_data_url(block)
                    if data_url:
                        multimodal_parts.append({
                            "type": "image_url",
                            "image_url": {"url": data_url},
                        })

            if multimodal_parts:
                if image_count > 0:
                    log.info(f"OpenAI-compatible 多模态已保留图片: model={model}, parts={len(multimodal_parts)}")
                return multimodal_parts

        # 不支持视觉或转换失败时，退化为文本并明确标记图片被省略
        text_parts = [b.get("text", "") for b in content if isinstance(b, dict) and b.get("type") == "text"]
        text = "\n".join(text_parts).strip()
        if image_count > 0:
            suffix = f"\n\n[附带图片 {image_count} 张，当前模型按文本模式处理]"
            text = (text + suffix).strip() if text else suffix.strip()
            log.warning(f"OpenAI-compatible 多模态降级为文本: model={model}, images={image_count}")
        return text or str(content)

    def _convert_messages(self, system: str, messages: list[dict], model: str) -> list[dict]:
        """将 Anthropic 格式消息转为 OpenAI 格式，并按模型处理多模态。"""
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
                        # 多模态内容 — 按模型能力转换
                        oai.append({
                            "role": "user",
                            "content": self._convert_user_content_for_model(content, model),
                        })
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
                    assistant_content = "\n".join(text_parts)
                    msg_dict: dict[str, Any] = {"role": "assistant", "content": assistant_content}
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
        cached = (usage_data.get("prompt_tokens_details") or {}).get("cached_tokens", 0)
        usage = Usage(
            input_tokens=usage_data.get("prompt_tokens", 0),
            output_tokens=usage_data.get("completion_tokens", 0),
            cache_read_input_tokens=cached,
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
        self._response = self._http.stream("POST", self._url, json=self._body)
        self._stream = await self._response.__aenter__()
        if self._stream.status_code >= 400:
            error_text = ""
            async for chunk in self._stream.aiter_text():
                error_text += chunk
                if len(error_text) > 1000:
                    break
            raise RuntimeError(
                f"Chat Completions HTTP {self._stream.status_code}: {error_text[:500]}"
            )
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
            if "error" in chunk:
                err = chunk["error"]
                msg = err.get("message", "") if isinstance(err, dict) else str(err)
                raise RuntimeError(f"Chat Completions stream error: {msg}")
            choices = chunk.get("choices") or []
            if not choices:
                if chunk.get("usage"):
                    self._final_usage = self._parse_stream_usage(chunk["usage"])
                continue
            delta = choices[0].get("delta", {})
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
                self._final_usage = self._parse_stream_usage(chunk["usage"])
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

    @staticmethod
    def _parse_stream_usage(u: dict) -> Usage:
        cached = (u.get("prompt_tokens_details") or {}).get("cached_tokens", 0)
        return Usage(
            input_tokens=u.get("prompt_tokens", 0),
            output_tokens=u.get("completion_tokens", 0),
            cache_read_input_tokens=cached,
        )

    async def get_final_message(self) -> LLMResponse:
        stop = "tool_use" if any(isinstance(b, ToolUseBlock) for b in self._final_content) else "end_turn"
        return LLMResponse(content=self._final_content, stop_reason=stop, usage=self._final_usage)


# ============ OpenAI Responses API Provider ============


class OpenAIResponsesProvider(LLMProvider):
    """OpenAI Responses API Provider (/v1/responses) for GPT-5/Codex models.

    Converts between Anthropic message format and Responses API format.
    Uses streaming internally for broader gateway compatibility.
    """

    def __init__(self, api_key: str, api_base: str = "https://api.openai.com/v1",
                 timeout: int = 120):
        import httpx
        base = api_base.rstrip("/")
        if not base.endswith("/v1"):
            base = base + "/v1"
        self._api_base = base
        self._headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }
        self._http = httpx.AsyncClient(timeout=timeout, headers=self._headers)

    async def create(self, *, model: str, max_tokens: int, system: str,
                     messages: list[dict], tools: list[dict] | None = None,
                     thinking: dict | None = None) -> LLMResponse:
        wrapper = self.stream(
            model=model, max_tokens=max_tokens, system=system,
            messages=messages, tools=tools, thinking=thinking,
        )
        async with wrapper as s:
            async for _ in s:
                pass
            return await s.get_final_message()

    def stream(self, *, model: str, max_tokens: int, system: str,
               messages: list[dict], tools: list[dict] | None = None,
               thinking: dict | None = None):
        input_items = self._convert_messages(messages)
        body: dict[str, Any] = {
            "model": model,
            "input": input_items,
            "stream": True,
        }
        if system:
            body["instructions"] = system
        if max_tokens:
            body["max_output_tokens"] = max_tokens
        if tools:
            body["tools"] = self._convert_tools(tools)
        return OpenAIResponsesStreamWrapper(
            self._http, f"{self._api_base}/responses", body,
        )

    async def close(self) -> None:
        await self._http.aclose()

    @staticmethod
    def _convert_messages(messages: list[dict]) -> list[dict]:
        """Convert Anthropic-style messages to Responses API input items."""
        items: list[dict] = []
        for msg in messages:
            role = msg.get("role", "user")
            content = msg.get("content", "")

            if role == "user":
                if isinstance(content, str):
                    items.append({"role": "user", "content": content})
                elif isinstance(content, list):
                    if content and isinstance(content[0], dict) and content[0].get("type") == "tool_result":
                        for tr in content:
                            output = tr.get("content", "")
                            if isinstance(output, list):
                                texts = [b.get("text", "") for b in output
                                         if isinstance(b, dict) and b.get("type") == "text"]
                                output = "\n".join(texts)
                            items.append({
                                "type": "function_call_output",
                                "call_id": tr.get("tool_use_id", ""),
                                "output": str(output),
                            })
                    else:
                        text_parts = [b.get("text", "") for b in content
                                      if isinstance(b, dict) and b.get("type") == "text"]
                        combined = "\n".join(text_parts).strip()
                        if combined:
                            items.append({"role": "user", "content": combined})

            elif role == "assistant":
                if isinstance(content, str):
                    if content:
                        items.append({"role": "assistant", "content": content})
                elif isinstance(content, list):
                    text_parts: list[str] = []
                    for block in content:
                        if not isinstance(block, dict):
                            continue
                        if block.get("type") == "text":
                            text_parts.append(block.get("text", ""))
                        elif block.get("type") == "tool_use":
                            if text_parts:
                                items.append({"role": "assistant", "content": "\n".join(text_parts)})
                                text_parts = []
                            args = block.get("input", {})
                            call_id = block.get("id", "")
                            items.append({
                                "type": "function_call",
                                "call_id": call_id,
                                "name": block.get("name", ""),
                                "arguments": json.dumps(args) if isinstance(args, dict) else str(args),
                            })
                    if text_parts:
                        items.append({"role": "assistant", "content": "\n".join(text_parts)})

        return items

    @staticmethod
    def _convert_tools(tools: list[dict]) -> list[dict]:
        """Convert Claude tool definitions to Responses API format."""
        return [
            {
                "type": "function",
                "name": t["name"],
                "description": t.get("description", ""),
                "parameters": t.get("input_schema", {}),
            }
            for t in tools
        ]


class OpenAIResponsesStreamWrapper:
    """Streaming wrapper for OpenAI Responses API SSE events.

    Maps Responses API events to the unified streaming event model
    (ContentBlockStart / ContentBlockDelta / TextDelta / InputJsonDelta).
    """

    def __init__(self, http, url: str, body: dict):
        self._http = http
        self._url = url
        self._body = body
        self._response = None
        self._final_content: list = []
        self._final_usage = Usage()

    async def __aenter__(self):
        self._response = self._http.stream("POST", self._url, json=self._body)
        self._stream = await self._response.__aenter__()
        if self._stream.status_code >= 400:
            error_text = ""
            async for chunk in self._stream.aiter_text():
                error_text += chunk
                if len(error_text) > 1000:
                    break
            raise RuntimeError(
                f"Responses API HTTP {self._stream.status_code}: {error_text[:500]}"
            )
        return self

    async def __aexit__(self, *args):
        if self._response:
            await self._response.__aexit__(*args)

    async def __aiter__(self):
        current_text = ""
        # Keyed by item id (from SSE events); stores call_id for ToolUseBlock
        tool_calls: dict[str, dict] = {}

        async for line in self._stream.aiter_lines():
            if not line.startswith("data: "):
                continue
            payload = line[6:]
            if payload.strip() == "[DONE]":
                break
            try:
                ev = json.loads(payload)
            except json.JSONDecodeError:
                continue

            ev_type = ev.get("type", "")

            if ev_type == "response.output_text.delta":
                delta_text = ev.get("delta", "")
                if delta_text:
                    current_text += delta_text
                    yield ContentBlockDelta(delta=TextDelta(text=delta_text))

            elif ev_type == "response.output_item.added":
                item = ev.get("item", {})
                if item.get("type") == "function_call":
                    item_id = item.get("id", "")
                    call_id = item.get("call_id") or item_id
                    name = item.get("name", "")
                    tool_calls[item_id] = {
                        "call_id": call_id, "name": name, "arguments": "",
                    }
                    yield ContentBlockStart(
                        content_block=ToolUseBlock(id=call_id, name=name)
                    )

            elif ev_type == "response.function_call_arguments.delta":
                delta_args = ev.get("delta", "")
                item_id = ev.get("item_id", "")
                if delta_args:
                    tc = tool_calls.get(item_id)
                    if tc:
                        tc["arguments"] += delta_args
                    yield ContentBlockDelta(
                        delta=InputJsonDelta(partial_json=delta_args)
                    )

            elif ev_type == "response.completed":
                resp_data = ev.get("response", {})
                usage_data = resp_data.get("usage", {})
                cached = (
                    (usage_data.get("input_tokens_details") or {})
                    .get("cached_tokens", 0)
                )
                self._final_usage = Usage(
                    input_tokens=usage_data.get("input_tokens", 0),
                    output_tokens=usage_data.get("output_tokens", 0),
                    cache_read_input_tokens=cached,
                )

        if current_text:
            self._final_content.append(TextBlock(text=current_text))
        for tc_data in tool_calls.values():
            try:
                args = json.loads(tc_data["arguments"] or "{}")
            except json.JSONDecodeError:
                args = {}
            self._final_content.append(
                ToolUseBlock(
                    id=tc_data["call_id"], name=tc_data["name"], input=args,
                )
            )

    async def get_final_message(self) -> LLMResponse:
        has_tool_use = any(isinstance(b, ToolUseBlock) for b in self._final_content)
        stop = "tool_use" if has_tool_use else "end_turn"
        return LLMResponse(
            content=self._final_content, stop_reason=stop, usage=self._final_usage,
        )


# ============ Provider 工厂 + Failover 客户端 ============


def create_provider(provider: str, api_key: str, api_base: str = "",
                    timeout: int = 120, api_format: str = "auto") -> LLMProvider:
    """根据 provider 名称和 api_format 创建对应的 LLM Provider"""
    if provider == "anthropic":
        return AnthropicProvider(api_key=api_key, api_base=api_base, timeout=timeout)

    base = api_base or _default_api_base(provider)
    if api_format == "responses":
        return OpenAIResponsesProvider(api_key=api_key, api_base=base, timeout=timeout)
    # auto / chat_completions -> standard Chat Completions
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


class _FailoverStreamWrapper:
    """Wraps multiple model configs and tries each in order for streaming.

    On __aenter__, attempts to open a stream from each model config until
    one succeeds. If all fail, raises the last error.
    """

    def __init__(self, models, get_provider, **kwargs):
        self._models = models
        self._get_provider = get_provider
        self._kwargs = kwargs
        self._active_stream = None

    async def __aenter__(self):
        last_error = None
        for cfg in self._models:
            provider = self._get_provider(cfg)
            stream_ctx = provider.stream(
                model=cfg["model"],
                max_tokens=cfg.get("max_tokens", 4096),
                **self._kwargs,
            )
            try:
                self._active_stream = stream_ctx
                result = await stream_ctx.__aenter__()
                log.info(f"流式调用已连接: {cfg['model']}")
                return result
            except Exception as e:
                last_error = e
                log.warning(f"流式调用 {cfg['model']} 失败: {e}，尝试 fallback...")
                try:
                    await stream_ctx.__aexit__(type(e), e, e.__traceback__)
                except Exception:
                    pass
                self._active_stream = None
        raise last_error or RuntimeError("所有模型均不可用")

    async def __aexit__(self, *args):
        if self._active_stream:
            await self._active_stream.__aexit__(*args)


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
        fmt = cfg.get("api_format", "auto")
        key = f"{cfg['provider']}:{cfg.get('api_base', '')}:{fmt}"
        if key not in self._providers:
            self._providers[key] = create_provider(
                provider=cfg["provider"],
                api_key=cfg["api_key"],
                api_base=cfg.get("api_base", ""),
                timeout=cfg.get("timeout", 120),
                api_format=fmt,
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
        """流式调用（带 failover：主模型失败时自动尝试备选模型）"""
        return _FailoverStreamWrapper(
            models=self._models,
            get_provider=self._get_provider,
            system=system, messages=messages,
            tools=tools, thinking=thinking,
        )

    @property
    def primary_model(self) -> str:
        return self._models[0]["model"] if self._models else "unknown"

    async def close(self) -> None:
        for p in self._providers.values():
            await p.close()

