"""聊天路由 — SSE 流式，使用真实成员身份，支持多会话"""

import asyncio
import base64
import json
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from fastapi import APIRouter, Request
from pydantic import BaseModel
from sse_starlette.sse import EventSourceResponse

from openvort.web.app import require_auth
from openvort.web.deps import get_agent, get_session_store, get_build_context_fn
from openvort.utils.logging import get_logger

log = get_logger("web.chat")

MEDIA_EXT_MAP = {
    "image/jpeg": "jpg", "image/jpg": "jpg", "image/png": "png",
    "image/gif": "gif", "image/webp": "webp",
}


def _get_chat_upload_dir() -> Path:
    from openvort.config.settings import get_settings
    d = get_settings().data_dir / "uploads" / "chat"
    d.mkdir(parents=True, exist_ok=True)
    return d


def _save_chat_image(data_b64: str, media_type: str) -> str:
    """Save base64 image to disk and return the URL path."""
    upload_dir = _get_chat_upload_dir()
    ext = MEDIA_EXT_MAP.get(media_type, "png")
    filename = f"{uuid.uuid4().hex}.{ext}"
    (upload_dir / filename).write_bytes(base64.b64decode(data_b64))
    return f"/uploads/chat/{filename}"

router = APIRouter()

# 内存中暂存待处理的消息
_pending_messages: dict[str, dict] = {}


@dataclass
class RunningMessage:
    message_id: str
    member_id: str
    session_id: str
    cancel_event: asyncio.Event
    stream_task: asyncio.Task[Any] | None = None


# 内存中追踪正在流式中的消息（用于取消）
_running_messages: dict[str, RunningMessage] = {}


class ImageItem(BaseModel):
    data: str  # base64 encoded
    media_type: str = "image/png"


class SendRequest(BaseModel):
    content: str
    images: list[ImageItem] = []
    session_id: str = "default"
    target_type: str = "ai"
    target_id: str = ""


class SendResponse(BaseModel):
    message_id: str


class AbortRequest(BaseModel):
    message_id: str


# ---- 对话管理接口 ----


@router.get("/sessions")
async def list_sessions(request: Request, target_type: str = ""):
    """获取用户的对话列表（可选按 target_type 过滤）"""
    payload = require_auth(request)
    member_id = payload.get("sub", "")
    session_store = get_session_store()
    sessions = await session_store.list_sessions("web", member_id, target_type=target_type)
    return {"sessions": sessions}


class CreateSessionRequest(BaseModel):
    title: str = "新对话"
    target_type: str = "ai"
    target_id: str = ""


@router.post("/sessions")
async def create_session(req: CreateSessionRequest, request: Request):
    """新建对话"""
    payload = require_auth(request)
    member_id = payload.get("sub", "")
    session_store = get_session_store()
    session_id = await session_store.create_session(
        "web", member_id, req.title,
        target_type=req.target_type, target_id=req.target_id,
    )
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
    images = []
    for img in req.images:
        d = img.model_dump()
        try:
            d["file_url"] = _save_chat_image(img.data, img.media_type)
        except Exception:
            pass
        images.append(d)
    _pending_messages[message_id] = {
        "content": req.content,
        "images": images,
        "member_id": payload.get("sub", ""),
        "name": payload.get("name", ""),
        "roles": payload.get("roles", []),
        "session_id": req.session_id,
        "target_type": req.target_type,
        "target_id": req.target_id,
    }
    return SendResponse(message_id=message_id)


@router.post("/abort")
async def abort_message(req: AbortRequest, request: Request):
    """中断当前消息生成（支持 pending/running 两种状态）"""
    payload = require_auth(request)
    member_id = payload.get("sub", "")

    pending = _pending_messages.get(req.message_id)
    if pending:
        if pending.get("member_id") != member_id:
            return {"success": False, "error": "无权限中断该消息"}
        _pending_messages.pop(req.message_id, None)
        return {"success": True, "status": "aborted_pending"}

    running = _running_messages.get(req.message_id)
    if running:
        if running.member_id != member_id:
            return {"success": False, "error": "无权限中断该消息"}
        running.cancel_event.set()
        if running.stream_task and not running.stream_task.done():
            running.stream_task.cancel()
        return {"success": True, "status": "aborting"}

    return {"success": False, "error": "消息不存在或已结束"}


@router.get("/stream/{message_id}")
async def stream_response(message_id: str, request: Request):
    """SSE 流式返回 AI 回复"""
    msg = _pending_messages.pop(message_id, None)
    if not msg:
        log.warning(f"消息不存在或已过期: message_id={message_id}")
        async def error_stream():
            yield {"event": "server_error", "data": "消息不存在或已过期"}
        return EventSourceResponse(error_stream())

    agent = get_agent()
    member_id = msg["member_id"]
    session_id = msg.get("session_id", "default")
    log.info(f"开始流式响应: message_id={message_id}, member_id={member_id}, session_id={session_id}")
    running = RunningMessage(
        message_id=message_id,
        member_id=member_id,
        session_id=session_id,
        cancel_event=asyncio.Event(),
        stream_task=None,
    )
    _running_messages[message_id] = running

    # 首条消息自动设置标题
    session_store = get_session_store()

    async def event_stream():
        disconnected = False
        running.stream_task = asyncio.current_task()
        try:
            yield {"event": "thinking", "data": "start"}

            async for event in agent.process_stream_web(
                msg["content"], member_id=member_id, images=msg.get("images", []),
                session_id=session_id,
                cancel_event=running.cancel_event,
                target_type=msg.get("target_type", "ai"),
                target_id=msg.get("target_id", ""),
            ):
                if running.cancel_event.is_set():
                    break
                if await request.is_disconnected():
                    log.warning(f"客户端断开连接: message_id={message_id}, member_id={member_id}, session_id={session_id}")
                    disconnected = True
                    running.cancel_event.set()
                    break

                event_type = event.get("type", "")
                if event_type == "text":
                    yield {"event": "text", "data": event["text"]}
                elif event_type == "tool_use":
                    yield {"event": "tool_use", "data": json.dumps(event, ensure_ascii=False)}
                elif event_type == "tool_output":
                    yield {"event": "tool_output", "data": json.dumps(event, ensure_ascii=False)}
                elif event_type == "tool_progress":
                    yield {"event": "tool_progress", "data": json.dumps(event, ensure_ascii=False)}
                elif event_type == "tool_result":
                    yield {"event": "tool_result", "data": json.dumps(event, ensure_ascii=False)}
                elif event_type == "usage":
                    yield {"event": "usage", "data": json.dumps(event, ensure_ascii=False)}

            if running.cancel_event.is_set():
                if not disconnected:
                    yield {"event": "interrupted", "data": "aborted"}
                return

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

            log.info(f"流式响应完成: message_id={message_id}, member_id={member_id}, session_id={session_id}")
            yield {"event": "done", "data": "ok"}
        except asyncio.CancelledError:
            if running.cancel_event.is_set() and not disconnected:
                yield {"event": "interrupted", "data": "aborted"}
                return
            raise
        except Exception as e:
            log.error(f"流式响应异常: message_id={message_id}, member_id={member_id}, session_id={session_id}, error={e}")
            yield {"event": "server_error", "data": str(e)}
        finally:
            _running_messages.pop(message_id, None)

    return EventSourceResponse(event_stream(), ping=15)


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
        images: list[str] = []
        if isinstance(msg.get("content"), str):
            content = msg["content"]
        elif isinstance(msg.get("content"), list):
            for block in msg["content"]:
                if isinstance(block, dict):
                    if block.get("type") == "text":
                        content += block.get("text", "")
                    elif block.get("type") == "image":
                        file_url = block.get("file_url", "")
                        if file_url:
                            images.append(file_url)
                    elif block.get("type") == "tool_result":
                        continue
        if role in ("user", "assistant") and (content or images):
            entry: dict = {
                "id": str(i),
                "role": role,
                "content": content,
                "timestamp": 0,
            }
            if images:
                entry["images"] = images
            result.append(entry)

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
        "total_cache_creation_tokens": info.get("total_cache_creation_tokens", 0),
        "total_cache_read_tokens": info.get("total_cache_read_tokens", 0),
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


@router.get("/members")
async def search_members(request: Request, keyword: str = "", limit: int = 20):
    """搜索成员列表（用于 @mention 提示）"""
    require_auth(request)
    from sqlalchemy import select
    from openvort.contacts.models import Member
    from openvort.web.deps import get_db_session_factory

    session_factory = get_db_session_factory()
    async with session_factory() as session:
        stmt = select(Member).where(Member.status == "active").order_by(Member.name)
        if keyword:
            pattern = f"%{keyword}%"
            stmt = stmt.where(
                (Member.name.ilike(pattern)) |
                (Member.email.ilike(pattern))
            )
        stmt = stmt.limit(limit)
        result = await session.execute(stmt)
        members = result.scalars().all()

        return {
            "members": [
                {
                    "id": m.id,
                    "name": m.name,
                    "avatar_url": m.avatar_url or "",
                    "email": m.email or "",
                }
                for m in members
            ]
        }


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


# ---- 联系人列表接口 ----


def _extract_last_message(messages_json: str) -> str:
    """Extract last assistant/user text from messages JSON for preview."""
    try:
        messages = json.loads(messages_json) if messages_json else []
    except (json.JSONDecodeError, TypeError):
        return ""
    for msg in reversed(messages):
        role = msg.get("role", "")
        if role not in ("user", "assistant"):
            continue
        content = msg.get("content", "")
        if isinstance(content, str):
            text = content.strip()
        elif isinstance(content, list):
            parts = []
            for block in content:
                if isinstance(block, dict) and block.get("type") == "text":
                    parts.append(block.get("text", ""))
            text = " ".join(parts).strip()
        else:
            text = str(content).strip()
        if text:
            return text[:50]
    return ""


@router.get("/contacts")
async def list_contacts(request: Request):
    """获取聊天联系人列表：AI助手置顶 + 有对话的成员按时间排序"""
    payload = require_auth(request)
    member_id = payload.get("sub", "")

    from sqlalchemy import select, func as sa_func, case
    from openvort.db.models import ChatSession
    from openvort.contacts.models import Member
    from openvort.web.deps import get_db_session_factory

    session_factory = get_db_session_factory()
    contacts = []

    async with session_factory() as db:
        # AI assistant entry: aggregate from all ai sessions
        ai_stmt = (
            select(ChatSession)
            .where(
                ChatSession.channel == "web",
                ChatSession.user_id == member_id,
                ChatSession.target_type == "ai",
            )
            .order_by(ChatSession.updated_at.desc())
        )
        ai_result = await db.execute(ai_stmt)
        ai_rows = ai_result.scalars().all()

        ai_last_message = ""
        ai_last_time = 0.0
        ai_session_count = len(ai_rows)
        for row in ai_rows:
            preview = _extract_last_message(row.messages)
            if preview:
                ai_last_message = preview
                ai_last_time = row.updated_at.timestamp() if row.updated_at else 0
                break
        if not ai_last_time and ai_rows:
            ai_last_time = ai_rows[0].updated_at.timestamp() if ai_rows[0].updated_at else 0

        contacts.append({
            "type": "ai",
            "id": "ai",
            "name": "AI 助手",
            "avatar_url": "",
            "last_message": ai_last_message,
            "last_message_time": ai_last_time,
            "unread": 0,
            "session_count": ai_session_count,
            "pinned": True,
        })

        # Member entries: one per target_id
        member_stmt = (
            select(ChatSession)
            .where(
                ChatSession.channel == "web",
                ChatSession.user_id == member_id,
                ChatSession.target_type == "member",
                ChatSession.hidden == False,  # noqa: E712
            )
            .order_by(ChatSession.updated_at.desc())
        )
        member_result = await db.execute(member_stmt)
        member_rows = member_result.scalars().all()

        target_ids = list({r.target_id for r in member_rows if r.target_id})
        members_map: dict[str, dict] = {}
        if target_ids:
            m_stmt = select(Member).where(Member.id.in_(target_ids))
            m_result = await db.execute(m_stmt)
            for m in m_result.scalars().all():
                members_map[m.id] = {
                    "name": m.name,
                    "avatar_url": m.avatar_url or "",
                    "email": m.email or "",
                    "position": m.position or "",
                }

        seen_targets: set[str] = set()
        for row in member_rows:
            tid = row.target_id
            if not tid or tid in seen_targets:
                continue
            seen_targets.add(tid)
            m_info = members_map.get(tid, {})
            contacts.append({
                "type": "member",
                "id": tid,
                "name": m_info.get("name", tid),
                "avatar_url": m_info.get("avatar_url", ""),
                "position": m_info.get("position", ""),
                "last_message": _extract_last_message(row.messages),
                "last_message_time": row.updated_at.timestamp() if row.updated_at else 0,
                "unread": 0,
                "session_id": row.session_id,
                "pinned": row.pinned,
            })

    # Sort: AI first (always), then pinned members, then by time
    ai_entry = contacts[0]
    member_entries = contacts[1:]
    member_entries.sort(key=lambda c: (not c.get("pinned", False), -(c.get("last_message_time", 0))))

    return {"contacts": [ai_entry] + member_entries}


class StartMemberChatRequest(BaseModel):
    member_id: str


@router.post("/contacts/start")
async def start_member_chat(req: StartMemberChatRequest, request: Request):
    """发起与成员的对话（获取或创建 session）"""
    payload = require_auth(request)
    user_id = payload.get("sub", "")

    from sqlalchemy import select
    from openvort.contacts.models import Member
    from openvort.web.deps import get_db_session_factory

    session_factory = get_db_session_factory()
    member_name = ""
    async with session_factory() as db:
        m = await db.get(Member, req.member_id)
        if m:
            member_name = m.name

    session_store = get_session_store()
    session_id = await session_store.get_or_create_member_session(
        "web", user_id, req.member_id, title=member_name or "成员对话",
    )
    return {"session_id": session_id, "member_name": member_name}


class PinContactRequest(BaseModel):
    pinned: bool


@router.put("/contacts/{session_id}/pin")
async def toggle_pin_contact(session_id: str, req: PinContactRequest, request: Request):
    """置顶/取消置顶联系人"""
    payload = require_auth(request)
    member_id = payload.get("sub", "")
    session_store = get_session_store()
    await session_store.set_pinned("web", member_id, session_id, req.pinned)
    return {"success": True}


@router.delete("/contacts/{session_id}")
async def hide_contact(session_id: str, request: Request):
    """从联系人列表隐藏（不删除聊天记录）"""
    payload = require_auth(request)
    member_id = payload.get("sub", "")
    session_store = get_session_store()
    await session_store.set_hidden("web", member_id, session_id, True)
    return {"success": True}



