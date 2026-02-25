"""
Session Store

管理每个用户的对话历史，支持持久化到数据库。
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

    @property
    def key(self) -> str:
        return f"{self.channel}:{self.user_id}"


class SessionStore:
    """会话存储

    v0.1 使用内存存储，后续可切换到数据库持久化。
    自动裁剪过长的对话历史，避免 token 溢出。
    """

    def __init__(self, max_messages: int = 50, max_age: int = 3600):
        """
        Args:
            max_messages: 每个 session 最多保留的消息数
            max_age: session 最大存活时间（秒），超时则清空
        """
        self._sessions: dict[str, Session] = {}
        self._max_messages = max_messages
        self._max_age = max_age

    def get_messages(self, channel: str, user_id: str) -> list[dict]:
        """获取用户的对话历史"""
        session = self._get_or_create(channel, user_id)

        # 超时则清空
        if time.time() - session.updated_at > self._max_age:
            session.messages = []
            log.info(f"Session {session.key} 已超时，清空历史")

        return session.messages

    def append(self, channel: str, user_id: str, message: dict) -> None:
        """追加一条消息"""
        session = self._get_or_create(channel, user_id)
        session.messages.append(message)
        session.updated_at = time.time()

        # 裁剪：保留 system 消息 + 最近 N 条
        self._trim(session)

    def save_messages(self, channel: str, user_id: str, messages: list[dict]) -> None:
        """替换整个对话历史"""
        session = self._get_or_create(channel, user_id)
        session.messages = messages
        session.updated_at = time.time()
        self._trim(session)

    def clear(self, channel: str, user_id: str) -> None:
        """清空用户会话"""
        key = f"{channel}:{user_id}"
        self._sessions.pop(key, None)

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

        # 保留最近的消息
        session.messages = msgs[-self._max_messages:]
        log.debug(f"Session {session.key} 裁剪到 {self._max_messages} 条")
