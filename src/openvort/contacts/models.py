"""
通讯录数据模型

以 Member 为中心，通过 PlatformIdentity 实现多平台身份映射。
"""

import uuid
from datetime import datetime

from sqlalchemy import DateTime, Float, ForeignKey, Integer, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from openvort.db.engine import Base


def _uuid() -> str:
    return uuid.uuid4().hex


class Member(Base):
    """成员 — 通讯录核心实体，以人为单位"""

    __tablename__ = "members"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_uuid)
    name: Mapped[str] = mapped_column(String(64), index=True)
    email: Mapped[str] = mapped_column(String(128), default="", index=True)
    phone: Mapped[str] = mapped_column(String(32), default="", index=True)
    avatar_url: Mapped[str] = mapped_column(String(512), default="")
    status: Mapped[str] = mapped_column(String(16), default="active")  # active / inactive
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())

    # 关联
    identities: Mapped[list["PlatformIdentity"]] = relationship(back_populates="member", cascade="all, delete-orphan")

    def __repr__(self) -> str:
        return f"<Member {self.id[:8]} {self.name}>"


class PlatformIdentity(Base):
    """平台身份 — 成员在某个外部平台上的账号信息"""

    __tablename__ = "platform_identities"
    __table_args__ = (
        UniqueConstraint("platform", "platform_user_id", name="uq_platform_user"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    member_id: Mapped[str] = mapped_column(String(32), ForeignKey("members.id"), index=True)
    platform: Mapped[str] = mapped_column(String(32), index=True)  # wecom / dingtalk / feishu / zentao / gitee
    platform_user_id: Mapped[str] = mapped_column(String(128))  # 平台侧唯一 ID
    platform_username: Mapped[str] = mapped_column(String(64), default="")  # 账号名
    platform_display_name: Mapped[str] = mapped_column(String(64), default="")  # 平台显示名
    platform_email: Mapped[str] = mapped_column(String(128), default="")
    platform_phone: Mapped[str] = mapped_column(String(32), default="")
    platform_position: Mapped[str] = mapped_column(String(64), default="")  # 职位
    platform_department: Mapped[str] = mapped_column(String(128), default="")  # 部门
    raw_data: Mapped[str] = mapped_column(Text, default="{}")  # JSON，完整原始数据
    synced_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    # 关联
    member: Mapped["Member"] = relationship(back_populates="identities")

    def __repr__(self) -> str:
        return f"<PlatformIdentity {self.platform}:{self.platform_user_id}>"


class MatchSuggestion(Base):
    """匹配建议 — 新平台同步时，智能匹配产生的待确认关联"""

    __tablename__ = "match_suggestions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    source_identity_id: Mapped[int] = mapped_column(Integer, ForeignKey("platform_identities.id"), index=True)
    target_member_id: Mapped[str] = mapped_column(String(32), ForeignKey("members.id"), index=True)
    match_type: Mapped[str] = mapped_column(String(16))  # email / phone / name
    confidence: Mapped[float] = mapped_column(Float, default=0.0)  # 0.0 ~ 1.0
    status: Mapped[str] = mapped_column(String(16), default="pending")  # pending / accepted / rejected
    resolved_by: Mapped[str] = mapped_column(String(64), default="")
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    # 关联
    source_identity: Mapped["PlatformIdentity"] = relationship()
    target_member: Mapped["Member"] = relationship()

    def __repr__(self) -> str:
        return f"<MatchSuggestion {self.match_type} conf={self.confidence:.2f} {self.status}>"


class Department(Base):
    """部门 — 来源于某个平台的组织架构"""

    __tablename__ = "departments"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(128))
    parent_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("departments.id"), nullable=True)
    platform: Mapped[str] = mapped_column(String(32), index=True)  # 来源平台
    platform_dept_id: Mapped[str] = mapped_column(String(128), default="")  # 平台侧部门 ID
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    def __repr__(self) -> str:
        return f"<Department {self.platform}:{self.name}>"
