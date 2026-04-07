"""
汇报插件数据模型

ReportTemplate — 汇报模板
ReportRule — 汇报规则（一条规则关联多人）
ReportRuleMember — 规则-成员关联
Report — 汇报实例
"""

import uuid
from datetime import date, datetime

from sqlalchemy import Boolean, Date, DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from openvort.db.engine import Base


def _uuid() -> str:
    return uuid.uuid4().hex


class ReportTemplate(Base):
    """汇报模板"""

    __tablename__ = "report_templates"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_uuid)
    name: Mapped[str] = mapped_column(String(128))
    description: Mapped[str] = mapped_column(String(512), default="")
    report_type: Mapped[str] = mapped_column(String(16))  # daily / weekly / monthly / quarterly
    content_schema: Mapped[str] = mapped_column(Text, default="{}")
    auto_collect: Mapped[str] = mapped_column(Text, default='{"git": true, "vortflow": true}')
    owner_id: Mapped[str] = mapped_column(String(32), ForeignKey("members.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())

    rules: Mapped[list["ReportRule"]] = relationship(back_populates="template", cascade="all, delete-orphan")

    def __repr__(self) -> str:
        return f"<ReportTemplate {self.name} ({self.report_type})>"


class ReportRule(Base):
    """汇报规则 — 一条规则关联多个成员"""

    __tablename__ = "report_rules"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_uuid)
    name: Mapped[str] = mapped_column(String(128), default="")
    template_id: Mapped[str] = mapped_column(String(32), ForeignKey("report_templates.id"), index=True)
    reviewer_id: Mapped[str] = mapped_column(String(32), ForeignKey("members.id"), nullable=True)
    deadline_cron: Mapped[str] = mapped_column(String(64), default="0 18 * * 1-5")
    workdays_only: Mapped[bool] = mapped_column(Boolean, default=True)
    reminder_minutes: Mapped[int] = mapped_column(Integer, default=30)
    escalation_minutes: Mapped[int] = mapped_column(Integer, default=120)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    # Legacy columns kept for migration compatibility (not used in new code)
    scope: Mapped[str] = mapped_column(String(16), default="member", nullable=True)
    target_id: Mapped[str] = mapped_column(String(32), default="", nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())

    template: Mapped["ReportTemplate"] = relationship(back_populates="rules")
    members: Mapped[list["ReportRuleMember"]] = relationship(back_populates="rule", cascade="all, delete-orphan")

    def __repr__(self) -> str:
        return f"<ReportRule {self.name or self.id[:8]} tmpl={self.template_id[:8]}>"


class ReportRuleMember(Base):
    """规则-成员关联表"""

    __tablename__ = "report_rule_members"

    rule_id: Mapped[str] = mapped_column(String(32), ForeignKey("report_rules.id", ondelete="CASCADE"), primary_key=True)
    member_id: Mapped[str] = mapped_column(String(32), ForeignKey("members.id"), primary_key=True)

    rule: Mapped["ReportRule"] = relationship(back_populates="members")

    def __repr__(self) -> str:
        return f"<ReportRuleMember rule={self.rule_id[:8]} member={self.member_id[:8]}>"


class Report(Base):
    """汇报实例"""

    __tablename__ = "reports"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_uuid)
    rule_id: Mapped[str | None] = mapped_column(String(32), ForeignKey("report_rules.id"), nullable=True)
    template_id: Mapped[str | None] = mapped_column(String(32), ForeignKey("report_templates.id"), nullable=True)
    reporter_id: Mapped[str] = mapped_column(String(32), ForeignKey("members.id"), index=True)
    reviewer_id: Mapped[str | None] = mapped_column(String(32), ForeignKey("members.id"), nullable=True)
    report_date: Mapped[date] = mapped_column(Date, index=True)
    report_type: Mapped[str] = mapped_column(String(16))
    title: Mapped[str] = mapped_column(String(256), default="")
    content: Mapped[str] = mapped_column(Text, default="")
    status: Mapped[str] = mapped_column(String(16), default="draft")
    auto_generated: Mapped[bool] = mapped_column(Boolean, default=False)
    submitted_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    reviewer_comment: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())

    def __repr__(self) -> str:
        return f"<Report {self.report_type} {self.report_date} by={self.reporter_id[:8]} status={self.status}>"
