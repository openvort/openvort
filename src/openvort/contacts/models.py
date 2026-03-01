"""
组织管理数据模型

以 Member 为中心，通过 PlatformIdentity 实现多平台身份映射。
包含汇报关系（ReportingRelation）和企业日历（OrgCalendar）。
"""

import uuid
from datetime import date, datetime

from sqlalchemy import Boolean, Date, DateTime, Float, ForeignKey, Integer, String, Text, UniqueConstraint, func
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
    bio: Mapped[str] = mapped_column(Text, default="")  # 个人简介
    password_hash: Mapped[str] = mapped_column(String(128), default="")  # 独立密码哈希，为空时 fallback 到 default_password
    is_account: Mapped[bool] = mapped_column(Boolean, default=False)  # 是否为可登录账号
    status: Mapped[str] = mapped_column(String(16), default="active")  # active / inactive
    notification_prefs: Mapped[str] = mapped_column(Text, default="{}")  # JSON: 通知偏好
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())

    # 关联
    identities: Mapped[list["PlatformIdentity"]] = relationship(back_populates="member", cascade="all, delete-orphan")
    department_links: Mapped[list["MemberDepartment"]] = relationship(back_populates="member", cascade="all, delete-orphan")

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
    order: Mapped[int] = mapped_column(Integer, default=0)  # 排序权重
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    # 关联
    children: Mapped[list["Department"]] = relationship(back_populates="parent", cascade="all, delete-orphan")
    parent: Mapped["Department | None"] = relationship(back_populates="children", remote_side=[id])
    member_links: Mapped[list["MemberDepartment"]] = relationship(back_populates="department", cascade="all, delete-orphan")

    def __repr__(self) -> str:
        return f"<Department {self.platform}:{self.name}>"


class MemberDepartment(Base):
    """成员-部门关联"""

    __tablename__ = "member_departments"
    __table_args__ = (
        UniqueConstraint("member_id", "department_id", name="uq_member_dept"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    member_id: Mapped[str] = mapped_column(String(32), ForeignKey("members.id"), index=True)
    department_id: Mapped[int] = mapped_column(Integer, ForeignKey("departments.id"), index=True)
    is_primary: Mapped[bool] = mapped_column(Boolean, default=False)  # 主部门标记

    # 关联
    member: Mapped["Member"] = relationship(back_populates="department_links")
    department: Mapped["Department"] = relationship(back_populates="member_links")

    def __repr__(self) -> str:
        return f"<MemberDepartment member={self.member_id[:8]} dept={self.department_id}>"


class ReportingRelation(Base):
    """汇报关系 — 谁向谁汇报"""

    __tablename__ = "reporting_relations"
    __table_args__ = (
        UniqueConstraint("reporter_id", "supervisor_id", name="uq_reporter_supervisor"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    reporter_id: Mapped[str] = mapped_column(String(32), ForeignKey("members.id"), index=True)
    supervisor_id: Mapped[str] = mapped_column(String(32), ForeignKey("members.id"), index=True)
    relation_type: Mapped[str] = mapped_column(String(16), default="direct")  # direct / dotted / functional
    is_primary: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    reporter: Mapped["Member"] = relationship(foreign_keys=[reporter_id])
    supervisor: Mapped["Member"] = relationship(foreign_keys=[supervisor_id])

    def __repr__(self) -> str:
        return f"<ReportingRelation {self.reporter_id[:8]}→{self.supervisor_id[:8]} {self.relation_type}>"


class OrgCalendar(Base):
    """企业日历 — 节假日与调休"""

    __tablename__ = "org_calendar"
    __table_args__ = (
        UniqueConstraint("date", name="uq_org_calendar_date"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    date: Mapped[date] = mapped_column(Date, index=True)
    day_type: Mapped[str] = mapped_column(String(16))  # workday (调休上班) / holiday (放假)
    name: Mapped[str] = mapped_column(String(64), default="")  # "国庆节" / "中秋调休补班"
    year: Mapped[int] = mapped_column(Integer, index=True)

    def __repr__(self) -> str:
        return f"<OrgCalendar {self.date} {self.day_type} {self.name}>"
