"""聊天路由 — SSE 流式，使用真实成员身份，支持多会话"""

import json
import uuid
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
    session_id: str = "default"


class SendResponse(BaseModel):
    message_id: str


# ---- 对话管理接口 ----


@router.get("/sessions")
async def list_sessions(request: Request):
    """获取用户的对话列表"""
    payload = require_auth(request)
    member_id = payload.get("sub", "")
    session_store = get_session_store()
    sessions = await session_store.list_sessions("web", member_id)
    return {"sessions": sessions}

class CreateSessionRequest(BaseModel):
    title: str = "新对话"


@router.post("/sessions")
async def create_session(req: CreateSessionRequest, request: Request):
    """新建对话"""
    payload = require_auth(request)
    member_id = payload.get("sub", "")
    session_store = get_session_store()
    session_id = await session_store.create_session("web", member_id, req.title)
    return {"session_id": session_id, "title": req.title}


class RenameSessionRequest(BaseModel):
    title: str


@router.put("/sessions/{session_id}")
async def rename_session(session_id: str, req: RenameSessionRequest, request: Request):
    """重命名对话"""
    payload = require_auth(request)
    member_id = payload.get("sub", "")
    session_store = get_session_store()
    await session_store.rename_session("web", member_id, session_id, req.title)
    return {"success": True}


@router.delete("/sessions/{session_id}")
async def delete_session(session_id: str, request: Request):
    """删除对话"""
    payload = require_auth(request)
    member_id = payload.get("sub", "")
    session_store = get_session_store()
    await session_store.delete_session("web", member_id, session_id)
    return {"success": True}


class BatchDeleteRequest(BaseModel):
    session_ids: list[str]


@router.post("/sessions/batch-delete")
async def batch_delete_sessions(req: BatchDeleteRequest, request: Request):
    """批量删除对话"""
    payload = require_auth(request)
    member_id = payload.get("sub", "")
    session_store = get_session_store()
    count = await session_store.batch_delete_sessions("web", member_id, req.session_ids)
    return {"success": True, "count": count}


# ---- 消息收发接口 ----


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
        "session_id": req.session_id,
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
    session_id = msg.get("session_id", "default")

    # 首条消息自动设置标题
    session_store = get_session_store()

    async def event_stream():
        try:
            yield {"event": "thinking", "data": "start"}

            async for event in agent.process_stream_web(
                msg["content"], member_id=member_id, images=msg.get("images", []),
                session_id=session_id,
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

            # 自动标题：前几轮对话动态更新标题
            if msg["content"].strip() and session_id != "default":
                info = session_store.get_session_info("web", member_id, session_id)
                msg_count = info.get("message_count", 0)
                if msg_count <= 6:
                    # 用最新的用户消息更新标题，取前15字符
                    title_text = msg["content"].strip().replace("\n", " ")[:15]
                    if title_text:
                        await session_store.rename_session("web", member_id, session_id, title_text)
                        yield {"event": "title_updated", "data": json.dumps({"session_id": session_id, "title": title_text}, ensure_ascii=False)}

            yield {"event": "done", "data": "ok"}
        except Exception as e:
            yield {"event": "error", "data": str(e)}

    return EventSourceResponse(event_stream())


@router.get("/history")
async def chat_history(request: Request, limit: int = 50, session_id: str = "default"):
    """获取当前用户的聊天历史"""
    payload = require_auth(request)
    member_id = payload.get("sub", "")

    session_store = get_session_store()
    messages = await session_store.get_messages("web", member_id, session_id)

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


@router.get("/session-info")
async def session_info(request: Request, session_id: str = "default"):
    """获取当前会话信息"""
    payload = require_auth(request)
    member_id = payload.get("sub", "")

    session_store = get_session_store()
    info = session_store.get_session_info("web", member_id, session_id)

    return {
        "thinking_level": info.get("thinking_level", "") or "off",
        "total_input_tokens": info.get("total_input_tokens", 0),
        "total_output_tokens": info.get("total_output_tokens", 0),
        "message_count": info.get("message_count", 0),
    }


class ThinkingRequest(BaseModel):
    level: str  # off|low|medium|high
    session_id: str = "default"


@router.post("/thinking")
async def set_thinking(req: ThinkingRequest, request: Request):
    """设置当前会话的 thinking 级别"""
    payload = require_auth(request)
    member_id = payload.get("sub", "")

    if req.level not in ("off", "low", "medium", "high"):
        return {"success": False, "error": "无效的 thinking 级别"}

    session_store = get_session_store()
    session_store.set_thinking_level("web", member_id, "" if req.level == "off" else req.level, req.session_id)

    return {"success": True, "level": req.level}


class CompactRequest(BaseModel):
    session_id: str = "default"


@router.post("/compact")
async def compact_session(req: CompactRequest, request: Request):
    """压缩当前会话上下文"""
    payload = require_auth(request)
    member_id = payload.get("sub", "")

    session_store = get_session_store()
    info = session_store.get_session_info("web", member_id, req.session_id)
    old_count = info.get("message_count", 0)

    if old_count < 4:
        return {"success": False, "error": "消息太少，无需压缩"}

    try:
        await session_store.compact("web", member_id, session_id=req.session_id)
        new_info = session_store.get_session_info("web", member_id, req.session_id)
        return {"success": True, "old_count": old_count, "new_count": new_info.get("message_count", 0)}
    except Exception as e:
        return {"success": False, "error": str(e)}


class ResetRequest(BaseModel):
    session_id: str = "default"


@router.post("/reset")
async def reset_session(req: ResetRequest, request: Request):
    """重置当前会话"""
    payload = require_auth(request)
    member_id = payload.get("sub", "")

    session_store = get_session_store()
    await session_store.clear("web", member_id, req.session_id)

    return {"success": True}

