"""Knowledge Base data models — kb_folders + kb_documents + kb_chunks (pgvector)."""

import uuid
from datetime import datetime

from pgvector.sqlalchemy import Vector
from sqlalchemy import DateTime, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from openvort.db.engine import Base


def _uuid() -> str:
    return uuid.uuid4().hex


class KBFolder(Base):
    """Knowledge base folder for organizing documents."""

    __tablename__ = "kb_folders"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_uuid)
    name: Mapped[str] = mapped_column(String(200))
    parent_id: Mapped[str] = mapped_column(String(32), default="", index=True)
    description: Mapped[str] = mapped_column(Text, default="")
    sort_order: Mapped[int] = mapped_column(Integer, default=0)
    owner_id: Mapped[str] = mapped_column(String(32), default="", index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())


class KBDocument(Base):
    """Knowledge base document metadata."""

    __tablename__ = "kb_documents"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_uuid)
    title: Mapped[str] = mapped_column(String(200))
    folder_id: Mapped[str] = mapped_column(String(32), default="", index=True)
    file_name: Mapped[str] = mapped_column(String(500), default="")
    file_type: Mapped[str] = mapped_column(String(20), index=True)  # pdf / docx / md / txt / qa / git
    file_size: Mapped[int] = mapped_column(Integer, default=0)
    content: Mapped[str] = mapped_column(Text, default="")
    status: Mapped[str] = mapped_column(String(20), default="pending", index=True)  # pending / processing / ready / error
    error_message: Mapped[str] = mapped_column(Text, default="")
    chunk_count: Mapped[int] = mapped_column(Integer, default=0)
    owner_id: Mapped[str] = mapped_column(String(32), default="", index=True)
    git_repo_id: Mapped[str] = mapped_column(String(32), default="")
    git_branch: Mapped[str] = mapped_column(String(200), default="")
    git_path: Mapped[str] = mapped_column(String(500), default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())


class KBChunk(Base):
    """Knowledge base document chunk with embedding vector."""

    __tablename__ = "kb_chunks"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_uuid)
    document_id: Mapped[str] = mapped_column(String(32), index=True)
    chunk_index: Mapped[int] = mapped_column(Integer, default=0)
    content: Mapped[str] = mapped_column(Text, default="")
    embedding = mapped_column(Vector(1024), nullable=True)
    token_count: Mapped[int] = mapped_column(Integer, default=0)
    metadata_json: Mapped[str] = mapped_column(Text, default="{}")
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
