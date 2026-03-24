"""VortSketch data models — sketches + pages (+ legacy sketch_versions)."""

import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from openvort.db.engine import Base


def _uuid() -> str:
    return uuid.uuid4().hex


class Sketch(Base):
    """UI prototype sketch — pure container for pages."""

    __tablename__ = "sketches"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_uuid)
    name: Mapped[str] = mapped_column(String(200))
    description: Mapped[str] = mapped_column(Text, default="")
    project_id: Mapped[str | None] = mapped_column(
        String(32), ForeignKey("flow_projects.id", ondelete="SET NULL"), nullable=True, index=True
    )
    story_id: Mapped[str | None] = mapped_column(String(32), nullable=True, index=True)
    story_type: Mapped[str] = mapped_column(String(20), default="")
    created_by: Mapped[str] = mapped_column(String(32), ForeignKey("members.id"), index=True)
    current_version: Mapped[int] = mapped_column(Integer, default=0)
    is_archived: Mapped[bool] = mapped_column(default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())


class SketchPage(Base):
    """A single page within a sketch."""

    __tablename__ = "sketch_pages"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_uuid)
    sketch_id: Mapped[str] = mapped_column(
        String(32), ForeignKey("sketches.id", ondelete="CASCADE"), index=True
    )
    name: Mapped[str] = mapped_column(String(200))
    html_content: Mapped[str] = mapped_column(Text, default="")
    sort_order: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())


class SketchVersion(Base):
    """Legacy — kept for backward compatibility."""

    __tablename__ = "sketch_versions"
    __table_args__ = (UniqueConstraint("sketch_id", "version", name="uq_sketch_version"),)

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_uuid)
    sketch_id: Mapped[str] = mapped_column(
        String(32), ForeignKey("sketches.id", ondelete="CASCADE"), index=True
    )
    version: Mapped[int] = mapped_column(Integer)
    html_content: Mapped[str] = mapped_column(Text, default="")
    instruction: Mapped[str] = mapped_column(Text, default="")
    ai_summary: Mapped[str] = mapped_column(String(500), default="")
    thumbnail_url: Mapped[str] = mapped_column(String(500), default="")
    parent_version: Mapped[int | None] = mapped_column(Integer, nullable=True)
    tokens_used: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
