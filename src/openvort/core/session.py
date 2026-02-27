"""
Session Store

管理每个用户的对话历史，支持持久化到数据库。
内存缓存 + DB 持久化混合模式：内存保证运行时性能，DB 保证重启恢复。
"""

import json
import time
from dataclasses import dataclass, field

from openvort.utils.logging import get_logger

log = get_logger("core.session")


@dataclass
class Session:
    """单个会话"""

    channel: str
    user_id: str
    messages: list[dict] = field(default_factory=list)
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)
    # per-session 设置
    thinking_level: str = ""  # off|low|medium|high — 空字符串表示不启用
    usage_mode: str = "off"  # off|tokens|full — 用量显示模式
    total_input_tokens: int = 0
    total_output_tokens: int = 0

    @property
    def key(self) -> str:
        return f"{self.channel}:{self.user_id}"


class SessionStore:
    """会话存储

    支持纯内存模式（CLI）和 DB 持久化模式（Web/服务）。
    传入 session_factory 则启用 DB 持久化，否则退化为纯内存。
    自动裁剪过长的对话历史，避免 token 溢出。
    """

    def __init__(self, max_messages: int = 50, max_age: int = 3600, session_factory=None):
        """
        Args:
            max_messages: 每个 session 最多保留的消息数
            max_age: session 最大存活时间（秒），超时则清空
            session_factory: SQLAlchemy async session factory（可选，传入则启用 DB 持久化）
        """
        self._sessions: dict[str, Session] = {}
        self._max_messages = max_messages
        self._max_age = max_age
        self._session_factory = session_factory

    async def get_messages(self, channel: str, user_id: str) -> list[dict]:
        """获取用户的对话历史（内存优先，未命中则从 DB 加载）"""
        key = f"{channel}:{user_id}"
        session = self._sessions.get(key)

        if session is None and self._session_factory:
            # 内存未命中，尝试从 DB 加载
            session = await self._load_from_db(channel, user_id)

        if session is None:
            session = Session(channel=channel, user_id=user_id)
            self._sessions[key] = session

        # 超时则清空
        if time.time() - session.updated_at > self._max_age:
            session.messages = []
            log.info(f"Session {session.key} 已超时，清空历史")

        return session.messages

    def append(self, channel: str, user_id: str, message: dict) -> None:
        """追加一条消息（仅内存，不触发 DB 写入）"""
        session = self._get_or_create(channel, user_id)
        session.messages.append(message)
        session.updated_at = time.time()
        self._trim(session)

    async def save_messages(self, channel: str, user_id: str, messages: list[dict]) -> None:
        """替换整个对话历史（写内存 + 异步写 DB）"""
        session = self._get_or_create(channel, user_id)
        session.messages = messages
        session.updated_at = time.time()
        self._trim(session)

        if self._session_factory:
            await self._save_to_db(channel, user_id, session.messages)

    async def clear(self, channel: str, user_id: str) -> None:
        """清空用户会话（清内存 + 删 DB 记录）"""
        key = f"{channel}:{user_id}"
        self._sessions.pop(key, None)

        if self._session_factory:
            await self._delete_from_db(channel, user_id)

    async def compact(self, channel: str, user_id: str, llm_client=None, keep_recent: int = 10) -> str:
        """压缩会话历史：用 LLM 生成摘要替换旧消息，保留最近 N 条

        Args:
            channel: 渠道
            user_id: 用户 ID
            llm_client: LLMClient 实例（用于生成摘要）
            keep_recent: 保留最近多少条消息

        Returns:
            压缩结果描述
        """
        key = f"{channel}:{user_id}"
        session = self._sessions.get(key)
        if not session or len(session.messages) <= keep_recent + 2:
            return "会话较短，无需压缩"

        old_count = len(session.messages)
        old_messages = session.messages[:-keep_recent]
        recent_messages = session.messages[-keep_recent:]

        # 生成摘要
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

        # 用摘要消息 + 最近消息替换
        compact_msg = {
            "role": "user",
            "content": f"[以下是之前对话的摘要]\n\n{summary}\n\n[摘要结束，以下是最近的对话]",
        }
        session.messages = [compact_msg] + recent_messages
        session.updated_at = time.time()

        if self._session_factory:
            await self._save_to_db(channel, user_id, session.messages)

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
        return "\n".join(parts[-30:])  # 最多取 30 条构建摘要输入

    def get_session_info(self, channel: str, user_id: str) -> dict:
        """获取会话信息（消息数、更新时间、设置等）"""
        key = f"{channel}:{user_id}"
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
            "exists": True,
        }

    def set_thinking_level(self, channel: str, user_id: str, level: str) -> None:
        """设置会话的 thinking 级别"""
        session = self._get_or_create(channel, user_id)
        session.thinking_level = level

    def get_thinking_level(self, channel: str, user_id: str) -> str:
        """获取会话的 thinking 级别"""
        key = f"{channel}:{user_id}"
        session = self._sessions.get(key)
        return session.thinking_level if session else ""

    def set_usage_mode(self, channel: str, user_id: str, mode: str) -> None:
        """设置用量显示模式"""
        session = self._get_or_create(channel, user_id)
        session.usage_mode = mode

    def get_usage_mode(self, channel: str, user_id: str) -> str:
        """获取用量显示模式"""
        key = f"{channel}:{user_id}"
        session = self._sessions.get(key)
        return session.usage_mode if session else "off"

    def add_usage(self, channel: str, user_id: str, input_tokens: int, output_tokens: int) -> None:
        """累加 token 用量"""
        session = self._get_or_create(channel, user_id)
        session.total_input_tokens += input_tokens
        session.total_output_tokens += output_tokens

    def _get_or_create(self, channel: str, user_id: str) -> Session:
        key = f"{channel}:{user_id}"
        if key not in self._sessions:
            self._sessions[key] = Session(channel=channel, user_id=user_id)
        return self._sessions[key]

    def _trim(self, session: Session) -> None:
        """裁剪过长的对话历史"""
        msgs = session.messages
        if len(msgs) <= self._max_messages:
            return
        session.messages = msgs[-self._max_messages:]
        log.debug(f"Session {session.key} 裁剪到 {self._max_messages} 条")

    # ---- DB 持久化 ----

    async def _load_from_db(self, channel: str, user_id: str) -> Session | None:
        """从 DB 加载会话"""
        try:
            from sqlalchemy import select
            from openvort.db.models import ChatSession

            async with self._session_factory() as db:
                stmt = select(ChatSession).where(
                    ChatSession.channel == channel,
                    ChatSession.user_id == user_id,
                )
                result = await db.execute(stmt)
                row = result.scalar_one_or_none()

            if row is None:
                return None

            messages = json.loads(row.messages) if row.messages else []
            updated_at = row.updated_at.timestamp() if row.updated_at else time.time()

            session = Session(
                channel=channel,
                user_id=user_id,
                messages=messages,
                updated_at=updated_at,
            )
            self._sessions[session.key] = session
            log.debug(f"从 DB 恢复 Session {session.key}，{len(messages)} 条消息")
            return session
        except Exception as e:
            log.warning(f"从 DB 加载 Session 失败 ({channel}:{user_id}): {e}")
            return None

    async def _save_to_db(self, channel: str, user_id: str, messages: list[dict]) -> None:
        """写入 DB（upsert）"""
        try:
            from sqlalchemy import select
            from openvort.db.models import ChatSession

            async with self._session_factory() as db:
                stmt = select(ChatSession).where(
                    ChatSession.channel == channel,
                    ChatSession.user_id == user_id,
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
                        messages=messages_json,
                    ))
                await db.commit()
        except Exception as e:
            log.warning(f"保存 Session 到 DB 失败 ({channel}:{user_id}): {e}")

    async def _delete_from_db(self, channel: str, user_id: str) -> None:
        """从 DB 删除会话"""
        try:
            from sqlalchemy import delete
            from openvort.db.models import ChatSession

            async with self._session_factory() as db:
                stmt = delete(ChatSession).where(
                    ChatSession.channel == channel,
                    ChatSession.user_id == user_id,
                )
                await db.execute(stmt)
                await db.commit()
        except Exception as e:
            log.warning(f"从 DB 删除 Session 失败 ({channel}:{user_id}): {e}")
