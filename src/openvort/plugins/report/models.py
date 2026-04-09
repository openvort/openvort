"""
汇报插件数据模型 (v2)

ReportPublication — 发布的汇报（合并了模板+规则）
ReportPublicationSubmitter — 提交人
ReportPublicationWhitelist — 白名单（免提交）
ReportPublicationReceiver — 接收人
ReportReceiverFilter — 接收人过滤（指定接收哪些提交人的汇报）
Report — 汇报实例
"""

import uuid
from datetime import date, datetime

from sqlalchemy import Boolean, Date, DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from openvort.db.engine import Base


def _uuid() -> str:
    return uuid.uuid4().hex


class ReportPublication(Base):
    """发布的汇报 — 定义汇报模板内容 + 规则设置"""

    __tablename__ = "report_publications"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_uuid)
    name: Mapped[str] = mapped_column(String(128))
    description: Mapped[str] = mapped_column(String(512), default="")
    report_type: Mapped[str] = mapped_column(String(16), default="daily")
    content_schema: Mapped[str] = mapped_column(Text, default="{}")
    content_template: Mapped[str] = mapped_column(Text, default="")

    # Reporting schedule
    repeat_cycle: Mapped[str] = mapped_column(String(16), default="daily")
    deadline_time: Mapped[str] = mapped_column(String(32), default="次日 10:00")
    reminder_enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    reminder_time: Mapped[str] = mapped_column(String(16), default="10:00")
    skip_weekends: Mapped[bool] = mapped_column(Boolean, default=True)
    skip_holidays: Mapped[bool] = mapped_column(Boolean, default=True)

    # Submission rules
    allow_multiple: Mapped[bool] = mapped_column(Boolean, default=True)
    allow_edit: Mapped[bool] = mapped_column(Boolean, default=True)

    # Notification settings
    notify_summary: Mapped[bool] = mapped_column(Boolean, default=True)
    notify_on_receive: Mapped[bool] = mapped_column(Boolean, default=True)

    owner_id: Mapped[str | None] = mapped_column(String(32), ForeignKey("members.id"), nullable=True)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())

    submitters: Mapped[list["ReportPublicationSubmitter"]] = relationship(
        back_populates="publication", cascade="all, delete-orphan"
    )
    whitelist: Mapped[list["ReportPublicationWhitelist"]] = relationship(
        back_populates="publication", cascade="all, delete-orphan"
    )
    receivers: Mapped[list["ReportPublicationReceiver"]] = relationship(
        back_populates="publication", cascade="all, delete-orphan"
    )
    receiver_filters: Mapped[list["ReportReceiverFilter"]] = relationship(
        back_populates="publication", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<ReportPublication {self.name} ({self.report_type})>"


class ReportPublicationSubmitter(Base):
    """发布-提交人关联"""

    __tablename__ = "report_publication_submitters"

    publication_id: Mapped[str] = mapped_column(
        String(32), ForeignKey("report_publications.id", ondelete="CASCADE"), primary_key=True
    )
    member_id: Mapped[str] = mapped_column(String(32), ForeignKey("members.id"), primary_key=True)
    publication: Mapped["ReportPublication"] = relationship(back_populates="submitters")


class ReportPublicationWhitelist(Base):
    """发布-白名单关联（白名单成员无需提交）"""

    __tablename__ = "report_publication_whitelist"

    publication_id: Mapped[str] = mapped_column(
        String(32), ForeignKey("report_publications.id", ondelete="CASCADE"), primary_key=True
    )
    member_id: Mapped[str] = mapped_column(String(32), ForeignKey("members.id"), primary_key=True)
    publication: Mapped["ReportPublication"] = relationship(back_populates="whitelist")


class ReportPublicationReceiver(Base):
    """发布-接收人关联"""

    __tablename__ = "report_publication_receivers"

    publication_id: Mapped[str] = mapped_column(
        String(32), ForeignKey("report_publications.id", ondelete="CASCADE"), primary_key=True
    )
    member_id: Mapped[str] = mapped_column(String(32), ForeignKey("members.id"), primary_key=True)
    publication: Mapped["ReportPublication"] = relationship(back_populates="receivers")


class ReportReceiverFilter(Base):
    """接收人过滤：指定接收人只接收哪些提交人的汇报。
    无记录 = 接收全部提交人的汇报（默认行为）。
    """

    __tablename__ = "report_receiver_filters"

    publication_id: Mapped[str] = mapped_column(
        String(32), ForeignKey("report_publications.id", ondelete="CASCADE"), primary_key=True
    )
    receiver_id: Mapped[str] = mapped_column(String(32), ForeignKey("members.id"), primary_key=True)
    submitter_id: Mapped[str] = mapped_column(String(32), ForeignKey("members.id"), primary_key=True)
    publication: Mapped["ReportPublication"] = relationship(back_populates="receiver_filters")


class ReportRead(Base):
    """已读记录：接收人阅读了哪些汇报"""

    __tablename__ = "report_reads"

    report_id: Mapped[str] = mapped_column(
        String(32), ForeignKey("reports.id", ondelete="CASCADE"), primary_key=True
    )
    reader_id: Mapped[str] = mapped_column(String(32), ForeignKey("members.id"), primary_key=True)
    read_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class Report(Base):
    """汇报实例"""

    __tablename__ = "reports"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_uuid)
    publication_id: Mapped[str | None] = mapped_column(String(32), ForeignKey("report_publications.id"), nullable=True, index=True)
    reporter_id: Mapped[str] = mapped_column(String(32), ForeignKey("members.id"), index=True)
    report_date: Mapped[date] = mapped_column(Date, index=True)
    report_type: Mapped[str] = mapped_column(String(16))
    title: Mapped[str] = mapped_column(String(256), default="")
    content: Mapped[str] = mapped_column(Text, default="")
    status: Mapped[str] = mapped_column(String(16), default="draft")
    auto_generated: Mapped[bool] = mapped_column(Boolean, default=False)
    submitted_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())

    # Legacy columns kept for migration (not used in new code)
    rule_id: Mapped[str | None] = mapped_column(String(32), nullable=True)
    template_id: Mapped[str | None] = mapped_column(String(32), nullable=True)
    reviewer_id: Mapped[str | None] = mapped_column(String(32), nullable=True)
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    reviewer_comment: Mapped[str] = mapped_column(Text, default="")

    def __repr__(self) -> str:
        return f"<Report {self.report_type} {self.report_date} by={self.reporter_id[:8]} status={self.status}>"
