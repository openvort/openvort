"""
数据库模型

v0.1 基础模型：消息记录、调度任务。
"""

from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from openvort.db.engine import Base


class MessageLog(Base):
    """消息日志"""

    __tablename__ = "message_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    channel: Mapped[str] = mapped_column(String(32), index=True)
    user_id: Mapped[str] = mapped_column(String(64), index=True)
    user_name: Mapped[str] = mapped_column(String(64), default="")
    direction: Mapped[str] = mapped_column(String(8))  # "in" / "out"
    msg_type: Mapped[str] = mapped_column(String(16), default="text")
    content: Mapped[str] = mapped_column(Text, default="")
    response: Mapped[str] = mapped_column(Text, default="")
    input_tokens: Mapped[int] = mapped_column(Integer, default=0)
    output_tokens: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class ChannelConfig(Base):
    """通道配置持久化"""

    __tablename__ = "channel_configs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    channel_name: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    config_data: Mapped[str] = mapped_column(Text, default="{}")  # JSON
    enabled: Mapped[bool] = mapped_column(default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())


class PluginConfig(Base):
    """插件配置持久化"""

    __tablename__ = "plugin_configs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    plugin_name: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    config_data: Mapped[str] = mapped_column(Text, default="{}")  # JSON
    enabled: Mapped[bool] = mapped_column(default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())


class ChatSession(Base):
    """聊天会话持久化（完整 Claude messages 列表）"""

    __tablename__ = "chat_sessions"
    __table_args__ = (
        UniqueConstraint("channel", "user_id", "session_id", name="uq_chat_session_channel_user_session"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    channel: Mapped[str] = mapped_column(String(32), index=True)
    user_id: Mapped[str] = mapped_column(String(64), index=True)
    session_id: Mapped[str] = mapped_column(String(64), index=True, default="default")
    title: Mapped[str] = mapped_column(String(200), default="新对话")
    messages: Mapped[str] = mapped_column(Text, default="[]")  # JSON
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())


class SystemConfig(Base):
    """系统配置（key-value 存储，Web 面板写入，优先级高于 .env）"""

    __tablename__ = "system_configs"

    key: Mapped[str] = mapped_column(String(128), primary_key=True)
    value: Mapped[str] = mapped_column(Text, default="")
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())


class ScheduleJob(Base):
    """调度任务持久化"""

    __tablename__ = "schedule_jobs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    job_id: Mapped[str] = mapped_column(String(128), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(128))
    description: Mapped[str] = mapped_column(Text, default="")

    # 归属
    owner_id: Mapped[str] = mapped_column(String(32), ForeignKey("members.id"), index=True)
    scope: Mapped[str] = mapped_column(String(16), default="personal")  # personal | team

    # 调度
    schedule_type: Mapped[str] = mapped_column(String(16), default="cron")  # cron | interval | once
    schedule: Mapped[str] = mapped_column(String(64))  # cron 表达式 / 秒数 / ISO 时间
    timezone: Mapped[str] = mapped_column(String(64), default="Asia/Shanghai")

    # 执行动作
    action_type: Mapped[str] = mapped_column(String(32), default="agent_chat")  # agent_chat
    action_config: Mapped[str] = mapped_column(Text, default="{}")  # JSON: {"prompt": "..."}

    # 可见性（团队任务是否对成员展示）
    visible: Mapped[bool] = mapped_column(Boolean, default=True)

    # 状态
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    last_run_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    last_status: Mapped[str] = mapped_column(String(16), default="pending")  # success | failed | pending
    last_result: Mapped[str] = mapped_column(Text, default="")

    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())
