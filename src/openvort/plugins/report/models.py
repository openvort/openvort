"""
汇报插件数据模型

ReportTemplate — 汇报模板
ReportRule — 汇报规则
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
    name: Mapped[str] = mapped_column(String(128))  # "技术团队日报"
    report_type: Mapped[str] = mapped_column(String(16))  # daily / weekly / monthly
    content_schema: Mapped[str] = mapped_column(Text, default="{}")  # JSON: required fields, format
    auto_collect: Mapped[str] = mapped_column(Text, default='{"git": true, "vortflow": true}')  # data sources
    owner_id: Mapped[str] = mapped_column(String(32), ForeignKey("members.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())

    rules: Mapped[list["ReportRule"]] = relationship(back_populates="template", cascade="all, delete-orphan")

    def __repr__(self) -> str:
        return f"<ReportTemplate {self.name} ({self.report_type})>"


class ReportRule(Base):
    """汇报规则 — 谁交什么报告"""

    __tablename__ = "report_rules"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_uuid)
    template_id: Mapped[str] = mapped_column(String(32), ForeignKey("report_templates.id"), index=True)
    scope: Mapped[str] = mapped_column(String(16), default="member")  # member / department
    target_id: Mapped[str] = mapped_column(String(32))  # member_id or department_id
    reviewer_id: Mapped[str] = mapped_column(String(32), ForeignKey("members.id"), nullable=True)
    deadline_cron: Mapped[str] = mapped_column(String(64), default="0 18 * * 1-5")  # 5-field cron
    reminder_minutes: Mapped[int] = mapped_column(Integer, default=30)
    escalation_minutes: Mapped[int] = mapped_column(Integer, default=120)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())

    template: Mapped["ReportTemplate"] = relationship(back_populates="rules")

    def __repr__(self) -> str:
        return f"<ReportRule {self.scope}:{self.target_id} tmpl={self.template_id[:8]}>"


class Report(Base):
    """汇报实例"""

    __tablename__ = "reports"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_uuid)
    rule_id: Mapped[str | None] = mapped_column(String(32), ForeignKey("report_rules.id"), nullable=True)
    template_id: Mapped[str | None] = mapped_column(String(32), ForeignKey("report_templates.id"), nullable=True)
    reporter_id: Mapped[str] = mapped_column(String(32), ForeignKey("members.id"), index=True)
    reviewer_id: Mapped[str | None] = mapped_column(String(32), ForeignKey("members.id"), nullable=True)
    report_date: Mapped[date] = mapped_column(Date, index=True)
    report_type: Mapped[str] = mapped_column(String(16))  # daily / weekly / monthly
    title: Mapped[str] = mapped_column(String(256), default="")
    content: Mapped[str] = mapped_column(Text, default="")  # Markdown
    status: Mapped[str] = mapped_column(String(16), default="draft")  # draft / submitted / reviewed / rejected
    auto_generated: Mapped[bool] = mapped_column(Boolean, default=False)
    submitted_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    reviewer_comment: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())

    def __repr__(self) -> str:
        return f"<Report {self.report_type} {self.report_date} by={self.reporter_id[:8]} status={self.status}>"
