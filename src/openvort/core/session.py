"""
Session Store

管理每个用户的对话历史，支持持久化到数据库。
内存缓存 + DB 持久化混合模式：内存保证运行时性能，DB 保证重启恢复。
支持多会话：每个用户可以有多个独立对话（session_id 区分）。
"""

import json
import time
import uuid
from dataclasses import dataclass, field

from openvort.utils.logging import get_logger

log = get_logger("core.session")


@dataclass
class Session:
    """单个会话"""

    channel: str
    user_id: str
    session_id: str = "default"
    title: str = "新对话"
    messages: list[dict] = field(default_factory=list)
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)
    # per-session 设置
    thinking_level: str = ""  # off|low|medium|high — 空字符串表示不启用
    usage_mode: str = "off"  # off|tokens|full — 用量显示模式
    total_input_tokens: int = 0
    total_output_tokens: int = 0
    total_cache_creation_tokens: int = 0
    total_cache_read_tokens: int = 0
    # contact targeting
    target_type: str = "ai"  # "ai" | "member"
    target_id: str = ""  # target member id when target_type="member"
    pinned: bool = False
    hidden: bool = False

    @property
    def key(self) -> str:
        return f"{self.channel}:{self.user_id}:{self.session_id}"


class SessionStore:
    """会话存储

    支持纯内存模式（CLI）和 DB 持久化模式（Web/服务）。
    传入 session_factory 则启用 DB 持久化，否则退化为纯内存。
    自动裁剪过长的对话历史，避免 token 溢出。
    """

    def __init__(self, max_messages: int = 50, max_age: int = 3600, session_factory=None):
        self._sessions: dict[str, Session] = {}
        self._max_messages = max_messages
        self._max_age = max_age
        self._session_factory = session_factory

    # ---- 核心消息操作 ----

    async def get_messages(self, channel: str, user_id: str, session_id: str = "default") -> list[dict]:
        """获取用户的对话历史（内存优先，未命中则从 DB 加载）"""
        key = f"{channel}:{user_id}:{session_id}"
        session = self._sessions.get(key)

        if session is None and self._session_factory:
            session = await self._load_from_db(channel, user_id, session_id)

        if session is None:
            session = Session(channel=channel, user_id=user_id, session_id=session_id)
            self._sessions[key] = session

        # 超时则清空（仅纯内存模式；DB 持久化模式下对话由用户主动管理）
        if not self._session_factory and time.time() - session.updated_at > self._max_age:
            session.messages = []
            log.info(f"Session {session.key} 已超时，清空历史")

        return session.messages

    def append(self, channel: str, user_id: str, message: dict, session_id: str = "default") -> None:
        """追加一条消息（仅内存，不触发 DB 写入）"""
        session = self._get_or_create(channel, user_id, session_id)
        session.messages.append(message)
        session.updated_at = time.time()
        self._trim(session)

    async def save_messages(self, channel: str, user_id: str, messages: list[dict], session_id: str = "default") -> None:
        """替换整个对话历史（写内存 + 异步写 DB）"""
        session = self._get_or_create(channel, user_id, session_id)
        session.messages = messages
        session.updated_at = time.time()
        self._trim(session)

        if self._session_factory:
            await self._save_to_db(channel, user_id, session.messages, session_id)

    async def clear(self, channel: str, user_id: str, session_id: str = "default") -> None:
        """清空用户会话（清内存 + 删 DB 记录）"""
        key = f"{channel}:{user_id}:{session_id}"
        self._sessions.pop(key, None)

        if self._session_factory:
            await self._delete_from_db(channel, user_id, session_id)

    async def compact(self, channel: str, user_id: str, llm_client=None, keep_recent: int = 10, session_id: str = "default") -> str:
        """压缩会话历史：用 LLM 生成摘要替换旧消息，保留最近 N 条"""
        key = f"{channel}:{user_id}:{session_id}"
        session = self._sessions.get(key)
        if not session or len(session.messages) <= keep_recent + 2:
            return "会话较短，无需压缩"

        old_count = len(session.messages)
        old_messages = session.messages[:-keep_recent]
        recent_messages = session.messages[-keep_recent:]

        summary = self._build_summary_text(old_messages)
        if llm_client:
            try:
                from openvort.core.llm import LLMResponse
                resp = await llm_client.create(
                    system="你是一个对话摘要助手。请将以下对话历史压缩为简洁的摘要，保留关键信息（用户需求、重要决策、工具调用结果等）。用中文输出，不超过 500 字。",
                    messages=[{"role": "user", "content": summary}],
                )
                summary_text = ""
                for block in resp.content:
                    if getattr(block, "type", None) == "text":
                        summary_text += block.text
                if summary_text:
                    summary = summary_text
            except Exception as e:
                log.warning(f"LLM 摘要生成失败，使用简单摘要: {e}")
                summary = self._build_summary_text(old_messages)

        compact_msg = {
            "role": "user",
            "content": f"[以下是之前对话的摘要]\n\n{summary}\n\n[摘要结束，以下是最近的对话]",
        }
        session.messages = [compact_msg] + recent_messages
        session.updated_at = time.time()

        if self._session_factory:
            await self._save_to_db(channel, user_id, session.messages, session_id)

        new_count = len(session.messages)
        log.info(f"Session {key} 已压缩: {old_count} → {new_count} 条")
        return f"已压缩: {old_count} 条 → {new_count} 条（摘要 + 最近 {keep_recent} 条）"

    @staticmethod
    def _build_summary_text(messages: list[dict]) -> str:
        """从消息列表构建简单文本摘要（fallback，不依赖 LLM）"""
        parts = []
        for msg in messages:
            role = msg.get("role", "")
            content = msg.get("content", "")
            if isinstance(content, str):
                text = content[:200]
            elif isinstance(content, list):
                text_parts = []
                for block in content:
                    if isinstance(block, dict):
                        if block.get("type") == "text":
                            text_parts.append(block.get("text", "")[:100])
                        elif block.get("type") == "tool_result":
                            text_parts.append(f"[工具结果: {block.get('content', '')[:80]}]")
                        elif block.get("type") == "tool_use":
                            text_parts.append(f"[调用工具: {block.get('name', '')}]")
                text = " ".join(text_parts)
            else:
                text = str(content)[:200]
            if text.strip():
                label = "用户" if role == "user" else "助手"
                parts.append(f"{label}: {text}")
        return "\n".join(parts[-30:])

    # ---- Session 信息与设置 ----

    def get_session_info(self, channel: str, user_id: str, session_id: str = "default") -> dict:
        """获取会话信息"""
        key = f"{channel}:{user_id}:{session_id}"
        session = self._sessions.get(key)
        if not session:
            return {"message_count": 0, "exists": False}
        return {
            "message_count": len(session.messages),
            "updated_at": session.updated_at,
            "thinking_level": session.thinking_level,
            "usage_mode": session.usage_mode,
            "total_input_tokens": session.total_input_tokens,
            "total_output_tokens": session.total_output_tokens,
            "total_cache_creation_tokens": session.total_cache_creation_tokens,
            "total_cache_read_tokens": session.total_cache_read_tokens,
            "exists": True,
        }

    def set_thinking_level(self, channel: str, user_id: str, level: str, session_id: str = "default") -> None:
        session = self._get_or_create(channel, user_id, session_id)
        session.thinking_level = level

    def get_thinking_level(self, channel: str, user_id: str, session_id: str = "default") -> str:
        key = f"{channel}:{user_id}:{session_id}"
        session = self._sessions.get(key)
        return session.thinking_level if session else ""

    def set_usage_mode(self, channel: str, user_id: str, mode: str, session_id: str = "default") -> None:
        session = self._get_or_create(channel, user_id, session_id)
        session.usage_mode = mode

    def get_usage_mode(self, channel: str, user_id: str, session_id: str = "default") -> str:
        key = f"{channel}:{user_id}:{session_id}"
        session = self._sessions.get(key)
        return session.usage_mode if session else "off"

    def add_usage(self, channel: str, user_id: str, input_tokens: int, output_tokens: int,
                  session_id: str = "default", cache_creation_tokens: int = 0, cache_read_tokens: int = 0) -> None:
        session = self._get_or_create(channel, user_id, session_id)
        session.total_input_tokens += input_tokens
        session.total_output_tokens += output_tokens
        session.total_cache_creation_tokens += cache_creation_tokens
        session.total_cache_read_tokens += cache_read_tokens

    # ---- 多会话管理 ----

    async def list_sessions(
        self, channel: str, user_id: str, target_type: str = "",
        limit: int = 20, offset: int = 0,
    ) -> dict:
        """列出用户对话（分页，可选按 target_type 过滤）"""
        if not self._session_factory:
            prefix = f"{channel}:{user_id}:"
            result = []
            for key, s in self._sessions.items():
                if key.startswith(prefix):
                    if target_type and s.target_type != target_type:
                        continue
                    result.append({
                        "session_id": s.session_id,
                        "title": s.title,
                        "created_at": s.created_at,
                        "updated_at": s.updated_at,
                        "target_type": s.target_type,
                        "target_id": s.target_id,
                        "pinned": s.pinned,
                    })
            result.sort(key=lambda x: x["updated_at"], reverse=True)
            total = len(result)
            return {"sessions": result[offset:offset + limit], "total": total}

        try:
            from sqlalchemy import select, func
            from openvort.db.models import ChatSession

            async with self._session_factory() as db:
                base = select(ChatSession).where(
                    ChatSession.channel == channel, ChatSession.user_id == user_id,
                )
                if target_type:
                    base = base.where(ChatSession.target_type == target_type)

                count_result = await db.execute(select(func.count()).select_from(base.subquery()))
                total = count_result.scalar() or 0

                stmt = base.order_by(ChatSession.updated_at.desc()).offset(offset).limit(limit)
                result = await db.execute(stmt)
                rows = result.scalars().all()

            sessions = [
                {
                    "session_id": row.session_id,
                    "title": row.title,
                    "created_at": row.created_at.timestamp() if row.created_at else 0,
                    "updated_at": row.updated_at.timestamp() if row.updated_at else 0,
                    "target_type": row.target_type or "ai",
                    "target_id": row.target_id or "",
                    "pinned": row.pinned if hasattr(row, "pinned") else False,
                }
                for row in rows
            ]
            return {"sessions": sessions, "total": total}
        except Exception as e:
            log.warning(f"列出会话失败 ({channel}:{user_id}): {e}")
            return {"sessions": [], "total": 0}

    async def create_session(self, channel: str, user_id: str, title: str = "新对话",
                             target_type: str = "ai", target_id: str = "") -> str:
        """创建新会话，返回 session_id"""
        session_id = str(uuid.uuid4())[:8]
        key = f"{channel}:{user_id}:{session_id}"
        session = Session(
            channel=channel, user_id=user_id, session_id=session_id,
            title=title, target_type=target_type, target_id=target_id,
        )
        self._sessions[key] = session

        if self._session_factory:
            try:
                from openvort.db.models import ChatSession
                async with self._session_factory() as db:
                    db.add(ChatSession(
                        channel=channel,
                        user_id=user_id,
                        session_id=session_id,
                        title=title,
                        messages="[]",
                        target_type=target_type,
                        target_id=target_id,
                    ))
                    await db.commit()
            except Exception as e:
                log.warning(f"创建会话到 DB 失败: {e}")

        return session_id

    async def get_or_create_member_session(self, channel: str, user_id: str,
                                           target_id: str, title: str = "") -> str:
        """Get existing member session or create a new one. Returns session_id."""
        if self._session_factory:
            try:
                from sqlalchemy import select
                from openvort.db.models import ChatSession

                async with self._session_factory() as db:
                    stmt = select(ChatSession).where(
                        ChatSession.channel == channel,
                        ChatSession.user_id == user_id,
                        ChatSession.target_type == "member",
                        ChatSession.target_id == target_id,
                        ChatSession.hidden == False,  # noqa: E712
                    )
                    result = await db.execute(stmt)
                    row = result.scalar_one_or_none()
                    if row:
                        return row.session_id
            except Exception as e:
                log.warning(f"查找成员会话失败: {e}")

        # Fallback: check memory
        prefix = f"{channel}:{user_id}:"
        for key, s in self._sessions.items():
            if key.startswith(prefix) and s.target_type == "member" and s.target_id == target_id and not s.hidden:
                return s.session_id

        return await self.create_session(channel, user_id, title=title or "新对话",
                                         target_type="member", target_id=target_id)

    async def set_pinned(self, channel: str, user_id: str, session_id: str, pinned: bool) -> None:
        """Set pinned state for a session."""
        key = f"{channel}:{user_id}:{session_id}"
        session = self._sessions.get(key)
        if session:
            session.pinned = pinned

        if self._session_factory:
            try:
                from sqlalchemy import select
                from openvort.db.models import ChatSession
                async with self._session_factory() as db:
                    stmt = select(ChatSession).where(
                        ChatSession.channel == channel,
                        ChatSession.user_id == user_id,
                        ChatSession.session_id == session_id,
                    )
                    result = await db.execute(stmt)
                    row = result.scalar_one_or_none()
                    if row:
                        row.pinned = pinned
                        await db.commit()
            except Exception as e:
                log.warning(f"设置置顶状态失败: {e}")

    async def set_hidden(self, channel: str, user_id: str, session_id: str, hidden: bool) -> None:
        """Set hidden state for a session (hide from contact list without deleting)."""
        key = f"{channel}:{user_id}:{session_id}"
        session = self._sessions.get(key)
        if session:
            session.hidden = hidden

        if self._session_factory:
            try:
                from sqlalchemy import select
                from openvort.db.models import ChatSession
                async with self._session_factory() as db:
                    stmt = select(ChatSession).where(
                        ChatSession.channel == channel,
                        ChatSession.user_id == user_id,
                        ChatSession.session_id == session_id,
                    )
                    result = await db.execute(stmt)
                    row = result.scalar_one_or_none()
                    if row:
                        row.hidden = hidden
                        await db.commit()
            except Exception as e:
                log.warning(f"设置隐藏状态失败: {e}")

    async def delete_session(self, channel: str, user_id: str, session_id: str) -> None:
        """删除单个会话"""
        key = f"{channel}:{user_id}:{session_id}"
        self._sessions.pop(key, None)

        if self._session_factory:
            await self._delete_from_db(channel, user_id, session_id)

    async def batch_delete_sessions(self, channel: str, user_id: str, session_ids: list[str]) -> int:
        """批量删除会话，返回删除数量"""
        count = 0
        for sid in session_ids:
            key = f"{channel}:{user_id}:{sid}"
            if self._sessions.pop(key, None) is not None:
                count += 1

        if self._session_factory:
            try:
                from sqlalchemy import delete
                from openvort.db.models import ChatSession
                async with self._session_factory() as db:
                    stmt = delete(ChatSession).where(
                        ChatSession.channel == channel,
                        ChatSession.user_id == user_id,
                        ChatSession.session_id.in_(session_ids),
                    )
                    result = await db.execute(stmt)
                    await db.commit()
                    count = result.rowcount
            except Exception as e:
                log.warning(f"批量删除会话失败: {e}")

        return count

    async def rename_session(self, channel: str, user_id: str, session_id: str, title: str) -> None:
        """重命名会话"""
        key = f"{channel}:{user_id}:{session_id}"
        session = self._sessions.get(key)
        if session:
            session.title = title

        if self._session_factory:
            try:
                from sqlalchemy import select
                from openvort.db.models import ChatSession
                async with self._session_factory() as db:
                    stmt = select(ChatSession).where(
                        ChatSession.channel == channel,
                        ChatSession.user_id == user_id,
                        ChatSession.session_id == session_id,
                    )
                    result = await db.execute(stmt)
                    row = result.scalar_one_or_none()
                    if row:
                        row.title = title
                        await db.commit()
            except Exception as e:
                log.warning(f"重命名会话失败: {e}")

    async def auto_title(self, channel: str, user_id: str, session_id: str,
                         llm_client=None) -> str:
        """Use LLM to generate a concise title from conversation context."""
        messages = await self.get_messages(channel, user_id, session_id)
        if not messages:
            return "新对话"

        context_parts: list[str] = []
        for msg in messages[:12]:
            role = msg.get("role", "")
            content = msg.get("content", "")
            if isinstance(content, str) and content.strip():
                label = "用户" if role == "user" else "助手"
                context_parts.append(f"{label}: {content[:200]}")
            elif isinstance(content, list):
                for block in content:
                    if isinstance(block, dict) and block.get("type") == "text":
                        text = block.get("text", "").strip()
                        if text:
                            label = "用户" if role == "user" else "助手"
                            context_parts.append(f"{label}: {text[:200]}")
                        break

        if not context_parts:
            return "新对话"

        title = ""
        if llm_client:
            try:
                resp = await llm_client.create(
                    system="根据以下对话内容，生成一个简洁的对话标题（不超过15个字）。只输出标题本身，不要引号、标点或任何额外内容。",
                    messages=[{"role": "user", "content": "\n".join(context_parts)}],
                )
                for block in resp.content:
                    if getattr(block, "type", None) == "text":
                        title += block.text
                title = title.strip().strip('"\'""''').replace("\n", " ")[:30]
            except Exception as e:
                log.warning(f"LLM 生成标题失败，使用截取: {e}")

        if not title:
            for msg in messages:
                if msg.get("role") != "user":
                    continue
                c = msg.get("content", "")
                if isinstance(c, str) and c.strip():
                    title = c.strip().replace("\n", " ")[:15]
                    break
                if isinstance(c, list):
                    for block in c:
                        if isinstance(block, dict) and block.get("type") == "text":
                            title = block.get("text", "").strip().replace("\n", " ")[:15]
                            break
                    if title:
                        break

        if not title:
            title = "新对话"

        await self.rename_session(channel, user_id, session_id, title)
        return title

    # ---- 内部方法 ----

    def _get_or_create(self, channel: str, user_id: str, session_id: str = "default") -> Session:
        key = f"{channel}:{user_id}:{session_id}"
        if key not in self._sessions:
            self._sessions[key] = Session(channel=channel, user_id=user_id, session_id=session_id)
        return self._sessions[key]

    def _trim(self, session: Session) -> None:
        msgs = session.messages
        if len(msgs) <= self._max_messages:
            return
        trimmed = msgs[-self._max_messages:]
        # Skip orphaned messages at the start to keep tool_use / tool_result pairs intact.
        # A valid start is a plain user text message (not a tool_result list).
        start = 0
        while start < len(trimmed):
            msg = trimmed[start]
            role = msg.get("role", "")
            content = msg.get("content", "")
            if role == "user" and isinstance(content, list):
                if content and isinstance(content[0], dict) and content[0].get("type") == "tool_result":
                    start += 1
                    continue
            if role == "assistant":
                if isinstance(content, list) and any(
                    isinstance(b, dict) and b.get("type") == "tool_use" for b in content
                ):
                    start += 1
                    continue
            if role == "user":
                break
            start += 1
        session.messages = trimmed[start:]
        log.debug(f"Session {session.key} 裁剪到 {len(session.messages)} 条 (跳过 {start} 条孤立消息)")

    # ---- DB 持久化 ----

    async def _load_from_db(self, channel: str, user_id: str, session_id: str = "default") -> Session | None:
        try:
            from sqlalchemy import select
            from openvort.db.models import ChatSession

            async with self._session_factory() as db:
                stmt = select(ChatSession).where(
                    ChatSession.channel == channel,
                    ChatSession.user_id == user_id,
                    ChatSession.session_id == session_id,
                )
                result = await db.execute(stmt)
                row = result.scalar_one_or_none()

            if row is None:
                return None

            messages = json.loads(row.messages) if row.messages else []
            updated_at = row.updated_at.timestamp() if row.updated_at else time.time()
            created_at = row.created_at.timestamp() if row.created_at else updated_at

            session = Session(
                channel=channel,
                user_id=user_id,
                session_id=session_id,
                title=row.title or "新对话",
                messages=messages,
                created_at=created_at,
                updated_at=updated_at,
                target_type=getattr(row, "target_type", None) or "ai",
                target_id=getattr(row, "target_id", None) or "",
                pinned=getattr(row, "pinned", False) or False,
                hidden=getattr(row, "hidden", False) or False,
            )
            self._sessions[session.key] = session
            log.debug(f"从 DB 恢复 Session {session.key}，{len(messages)} 条消息")
            return session
        except Exception as e:
            log.warning(f"从 DB 加载 Session 失败 ({channel}:{user_id}:{session_id}): {e}")
            return None

    async def _save_to_db(self, channel: str, user_id: str, messages: list[dict], session_id: str = "default") -> None:
        try:
            from sqlalchemy import select
            from openvort.db.models import ChatSession

            async with self._session_factory() as db:
                stmt = select(ChatSession).where(
                    ChatSession.channel == channel,
                    ChatSession.user_id == user_id,
                    ChatSession.session_id == session_id,
                )
                result = await db.execute(stmt)
                row = result.scalar_one_or_none()

                messages_json = json.dumps(messages, ensure_ascii=False)

                if row:
                    row.messages = messages_json
                else:
                    db.add(ChatSession(
                        channel=channel,
                        user_id=user_id,
                        session_id=session_id,
                        messages=messages_json,
                    ))
                await db.commit()
        except Exception as e:
            log.warning(f"保存 Session 到 DB 失败 ({channel}:{user_id}:{session_id}): {e}")

    async def _delete_from_db(self, channel: str, user_id: str, session_id: str = "default") -> None:
        try:
            from sqlalchemy import delete
            from openvort.db.models import ChatSession

            async with self._session_factory() as db:
                stmt = delete(ChatSession).where(
                    ChatSession.channel == channel,
                    ChatSession.user_id == user_id,
                    ChatSession.session_id == session_id,
                )
                await db.execute(stmt)
                await db.commit()
        except Exception as e:
            log.warning(f"从 DB 删除 Session 失败 ({channel}:{user_id}:{session_id}): {e}")

