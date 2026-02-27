"""聊天路由 — SSE 流式，使用真实成员身份"""

import json
import uuid
from typing import AsyncGenerator

from fastapi import APIRouter, Request
from pydantic import BaseModel
from sse_starlette.sse import EventSourceResponse

from openvort.web.app import require_auth
from openvort.web.deps import get_agent, get_session_store, get_build_context_fn

router = APIRouter()

# 内存中暂存待处理的消息
_pending_messages: dict[str, dict] = {}


class ImageItem(BaseModel):
    data: str  # base64 encoded
    media_type: str = "image/png"


class SendRequest(BaseModel):
    content: str
    images: list[ImageItem] = []


class SendResponse(BaseModel):
    message_id: str


@router.post("/send", response_model=SendResponse)
async def send_message(req: SendRequest, request: Request):
    payload = require_auth(request)
    message_id = str(uuid.uuid4())
    _pending_messages[message_id] = {
        "content": req.content,
        "images": [img.model_dump() for img in req.images],
        "member_id": payload.get("sub", ""),
        "name": payload.get("name", ""),
        "roles": payload.get("roles", []),
    }
    return SendResponse(message_id=message_id)


@router.get("/stream/{message_id}")
async def stream_response(message_id: str, request: Request):
    """SSE 流式返回 AI 回复"""
    msg = _pending_messages.pop(message_id, None)
    if not msg:
        async def error_stream():
            yield {"event": "error", "data": "消息不存在或已过期"}
        return EventSourceResponse(error_stream())

    agent = get_agent()
    member_id = msg["member_id"]

    async def event_stream():
        try:
            yield {"event": "thinking", "data": "start"}

            async for event in agent.process_stream_web(
                msg["content"], member_id=member_id, images=msg.get("images", [])
            ):
                if await request.is_disconnected():
                    break

                event_type = event.get("type", "")
                if event_type == "text":
                    yield {"event": "text", "data": event["text"]}
                elif event_type == "tool_use":
                    yield {"event": "tool_use", "data": json.dumps(event, ensure_ascii=False)}
                elif event_type == "tool_result":
                    yield {"event": "tool_result", "data": json.dumps(event, ensure_ascii=False)}

            yield {"event": "done", "data": "ok"}
        except Exception as e:
            yield {"event": "error", "data": str(e)}

    return EventSourceResponse(event_stream())


@router.get("/history")
async def chat_history(request: Request, limit: int = 50):
    """获取当前用户的聊天历史"""
    payload = require_auth(request)
    member_id = payload.get("sub", "")

    session_store = get_session_store()
    messages = await session_store.get_messages("web", member_id)

    result = []
    for i, msg in enumerate(messages[-limit:]):
        role = msg.get("role", "user")
        content = ""
        if isinstance(msg.get("content"), str):
            content = msg["content"]
        elif isinstance(msg.get("content"), list):
            for block in msg["content"]:
                if isinstance(block, dict):
                    if block.get("type") == "text":
                        content += block.get("text", "")
                    elif block.get("type") == "tool_result":
                        continue
        if role in ("user", "assistant") and content:
            result.append({
                "id": str(i),
                "role": role,
                "content": content,
                "timestamp": 0,
            })

    return {"messages": result}
