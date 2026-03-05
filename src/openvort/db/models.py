"""
数据库模型

v0.1 基础模型：消息记录、调度任务。
"""

import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from openvort.db.engine import Base


def _uuid() -> str:
    return uuid.uuid4().hex


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
    target_type: Mapped[str] = mapped_column(String(16), default="ai", index=True)  # "ai" | "member"
    target_id: Mapped[str] = mapped_column(String(32), default="")  # target member id when target_type="member"
    pinned: Mapped[bool] = mapped_column(Boolean, default=False)
    hidden: Mapped[bool] = mapped_column(Boolean, default=False)
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

    # AI 员工绑定（用于定时汇报）
    target_member_id: Mapped[str] = mapped_column(String(32), default="", nullable=True)  # 绑定的 AI 员工 ID

    # 可见性（团队任务是否对成员展示）
    visible: Mapped[bool] = mapped_column(Boolean, default=True)

    # 状态
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    last_run_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    last_status: Mapped[str] = mapped_column(String(16), default="pending")  # success | failed | pending
    last_result: Mapped[str] = mapped_column(Text, default="")

    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())


class Skill(Base):
    """技能知识条目 — 内置/公共/个人三级体系"""

    __tablename__ = "skills"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_uuid)
    name: Mapped[str] = mapped_column(String(100), index=True)
    description: Mapped[str] = mapped_column(Text, default="")
    content: Mapped[str] = mapped_column(Text, default="")  # markdown
    scope: Mapped[str] = mapped_column(String(16), index=True)  # builtin / public / personal
    skill_type: Mapped[str] = mapped_column(String(16), default="workflow")  # role / workflow / report / system
    owner_id: Mapped[str] = mapped_column(String(32), default="", index=True)  # personal → member.id
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    sort_order: Mapped[int] = mapped_column(Integer, default=0)
    created_by: Mapped[str] = mapped_column(String(32), default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())


class MemberSkill(Base):
    """成员订阅的公共 Skill"""

    __tablename__ = "member_skills"
    __table_args__ = (
        UniqueConstraint("member_id", "skill_id", name="uq_member_skill"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    member_id: Mapped[str] = mapped_column(String(32), ForeignKey("members.id"), index=True)
    skill_id: Mapped[str] = mapped_column(String(32), ForeignKey("skills.id"), index=True)
    source: Mapped[str] = mapped_column(String(32), default="personal")  # role:developer / personal / public
    custom_content: Mapped[str] = mapped_column(Text, default="")  # 自定义内容，覆盖 Skill.content
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class PostSkill(Base):
    """岗位-技能映射表"""

    __tablename__ = "role_skills"  # 保持向后兼容，暂不重命名表

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    role: Mapped[str] = mapped_column(String(32), index=True)  # 岗位标识：developer/pm/qa/designer/assistant (数据库用 role)
    post: Mapped[str] = mapped_column(String(32), index=True, nullable=True)  # 冗余字段，保持兼容
    skill_id: Mapped[str] = mapped_column(String(32), ForeignKey("skills.id"), index=True)
    priority: Mapped[int] = mapped_column(Integer, default=0)  # 越小越优先


class Post(Base):
    """AI 员工岗位元数据表"""

    __tablename__ = "virtual_roles"  # 保持向后兼容，暂不重命名表

    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    key: Mapped[str] = mapped_column(String(32), unique=True, index=True)  # developer/pm/qa/designer/assistant
    name: Mapped[str] = mapped_column(String(64))  # 开发工程师
    description: Mapped[str] = mapped_column(String(256), default="")  # 一句话描述
    icon: Mapped[str] = mapped_column(String(32), default="")  # 前端图标 key，如 Code/ClipboardList
    default_persona: Mapped[str] = mapped_column(Text, default="")  # 默认人设
    default_auto_report: Mapped[bool] = mapped_column(Boolean, default=False)
    default_report_frequency: Mapped[str] = mapped_column(String(16), default="daily")  # daily/weekly
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())


# 保留旧名称的别名，保持向后兼容
VirtualRole = Post
RoleSkill = PostSkill


class WorkAssignment(Base):
    """工作安排 - 记录 AI 员工被安排的工作任务"""

    __tablename__ = "work_assignments"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    # 任务基本信息
    title: Mapped[str] = mapped_column(String(256))  # 任务标题/一句话描述
    summary: Mapped[str] = mapped_column(Text, default="")  # 任务详细描述/AI 的理解
    plan: Mapped[str] = mapped_column(Text, default="")  # AI 员工"打算怎么做"的简短步骤

    # 归属与执行
    requested_by_member_id: Mapped[str] = mapped_column(String(32), ForeignKey("members.id"), index=True)  # 谁要求的
    assignee_member_id: Mapped[str] = mapped_column(String(32), ForeignKey("members.id"), index=True)  # 谁来执行（AI 员工）

    # 来源追踪
    source_type: Mapped[str] = mapped_column(String(16), default="manual")  # chat / code_task / schedule / manual
    source_id: Mapped[str] = mapped_column(String(64), default="")  # 来源ID（如 chat session id, code_task id 等）
    source_detail: Mapped[str] = mapped_column(Text, default="")  # 来源详情摘要

    # 关联的计划任务（可选，一个工作安排可以关联多个定时任务）
    related_schedule_id: Mapped[int] = mapped_column(Integer, ForeignKey("schedule_jobs.id"), nullable=True)

    # 状态
    status: Mapped[str] = mapped_column(String(16), default="pending")  # pending / in_progress / completed / ongoing
    priority: Mapped[str] = mapped_column(String(16), default="normal")  # low / normal / high / urgent

    # 时间戳
    due_date: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)  # 截止日期
    last_action_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)  # 最近一次行动/汇报时间
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())
