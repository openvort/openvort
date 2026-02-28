"""VortFlow ORM 模型"""

import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from openvort.db.engine import Base


def _uuid() -> str:
    return uuid.uuid4().hex


class FlowProject(Base):
    """项目"""

    __tablename__ = "flow_projects"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_uuid)
    name: Mapped[str] = mapped_column(String(200))
    description: Mapped[str] = mapped_column(Text, default="")
    product: Mapped[str] = mapped_column(String(200), default="")
    iteration: Mapped[str] = mapped_column(String(200), default="")
    version: Mapped[str] = mapped_column(String(64), default="")
    owner_id: Mapped[str] = mapped_column(String(32), ForeignKey("members.id"), nullable=True)
    start_date: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    end_date: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())


class FlowStory(Base):
    """需求"""

    __tablename__ = "flow_stories"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_uuid)
    project_id: Mapped[str] = mapped_column(String(32), ForeignKey("flow_projects.id"), index=True)
    title: Mapped[str] = mapped_column(String(500))
    description: Mapped[str] = mapped_column(Text, default="")
    state: Mapped[str] = mapped_column(String(32), default="intake", index=True)
    priority: Mapped[int] = mapped_column(Integer, default=3)  # 1=紧急 2=高 3=中 4=低
    submitter_id: Mapped[str | None] = mapped_column(String(32), ForeignKey("members.id"), nullable=True)
    pm_id: Mapped[str | None] = mapped_column(String(32), ForeignKey("members.id"), nullable=True)
    designer_id: Mapped[str | None] = mapped_column(String(32), ForeignKey("members.id"), nullable=True)
    reviewer_id: Mapped[str | None] = mapped_column(String(32), ForeignKey("members.id"), nullable=True)
    deadline: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())


class FlowTask(Base):
    """子任务"""

    __tablename__ = "flow_tasks"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_uuid)
    story_id: Mapped[str] = mapped_column(String(32), ForeignKey("flow_stories.id"), index=True)
    title: Mapped[str] = mapped_column(String(500))
    description: Mapped[str] = mapped_column(Text, default="")
    task_type: Mapped[str] = mapped_column(String(32), default="fullstack")  # frontend/backend/fullstack/test
    state: Mapped[str] = mapped_column(String(32), default="todo", index=True)
    assignee_id: Mapped[str | None] = mapped_column(String(32), ForeignKey("members.id"), nullable=True)
    estimate_hours: Mapped[float | None] = mapped_column(nullable=True)
    actual_hours: Mapped[float | None] = mapped_column(nullable=True)
    deadline: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())


class FlowBug(Base):
    """缺陷"""

    __tablename__ = "flow_bugs"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_uuid)
    story_id: Mapped[str | None] = mapped_column(String(32), ForeignKey("flow_stories.id"), nullable=True, index=True)
    task_id: Mapped[str | None] = mapped_column(String(32), ForeignKey("flow_tasks.id"), nullable=True)
    title: Mapped[str] = mapped_column(String(500))
    description: Mapped[str] = mapped_column(Text, default="")
    severity: Mapped[int] = mapped_column(Integer, default=3)  # 1=致命 2=严重 3=一般 4=轻微
    state: Mapped[str] = mapped_column(String(32), default="open", index=True)
    reporter_id: Mapped[str | None] = mapped_column(String(32), ForeignKey("members.id"), nullable=True)
    assignee_id: Mapped[str | None] = mapped_column(String(32), ForeignKey("members.id"), nullable=True)
    developer_id: Mapped[str | None] = mapped_column(String(32), ForeignKey("members.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())


class FlowMilestone(Base):
    """里程碑"""

    __tablename__ = "flow_milestones"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_uuid)
    project_id: Mapped[str] = mapped_column(String(32), ForeignKey("flow_projects.id"), index=True)
    story_id: Mapped[str | None] = mapped_column(String(32), ForeignKey("flow_stories.id"), nullable=True)
    name: Mapped[str] = mapped_column(String(200))
    due_date: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class FlowEvent(Base):
    """事件日志（审计追踪）"""

    __tablename__ = "flow_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    entity_type: Mapped[str] = mapped_column(String(32), index=True)  # project/story/task/bug
    entity_id: Mapped[str] = mapped_column(String(32), index=True)
    action: Mapped[str] = mapped_column(String(64))  # created/state_changed/assigned/...
    actor_id: Mapped[str | None] = mapped_column(String(32), ForeignKey("members.id"), nullable=True)
    detail: Mapped[str] = mapped_column(Text, default="")  # JSON 补充信息
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class FlowProjectMember(Base):
    """项目成员 — 记录成员在项目中的角色"""

    __tablename__ = "flow_project_members"
    __table_args__ = (
        UniqueConstraint("project_id", "member_id", name="uq_flow_project_member"),
    )

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_uuid)
    project_id: Mapped[str] = mapped_column(String(32), ForeignKey("flow_projects.id"), index=True)
    member_id: Mapped[str] = mapped_column(String(32), ForeignKey("members.id"), index=True)
    role: Mapped[str] = mapped_column(String(32), default="member")  # owner/pm/dev/tester/viewer
    joined_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class FlowExternalMapping(Base):
    """外部系统映射（双向同步用）"""

    __tablename__ = "flow_external_mappings"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_uuid)
    local_type: Mapped[str] = mapped_column(String(32), index=True)  # story/task/bug
    local_id: Mapped[str] = mapped_column(String(32), index=True)
    adapter: Mapped[str] = mapped_column(String(32), index=True)  # zentao/jira
    external_id: Mapped[str] = mapped_column(String(128))
    sync_cursor: Mapped[str] = mapped_column(String(128), default="")
    conflict_state: Mapped[str] = mapped_column(String(16), default="ok")  # ok/conflict/pending
    last_synced_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
