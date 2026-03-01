"""VortGit ORM models"""

import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from openvort.db.engine import Base


def _uuid() -> str:
    return uuid.uuid4().hex


class GitProvider(Base):
    """Git platform configuration (Gitee, GitHub, GitLab, etc.)"""

    __tablename__ = "git_providers"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_uuid)
    name: Mapped[str] = mapped_column(String(64))
    platform: Mapped[str] = mapped_column(String(32), index=True)  # gitee/github/gitlab/generic
    api_base: Mapped[str] = mapped_column(String(512), default="")
    access_token: Mapped[str] = mapped_column(Text, default="")  # Fernet encrypted
    owner_id: Mapped[str | None] = mapped_column(String(32), ForeignKey("members.id"), nullable=True)
    is_default: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())


class GitRepo(Base):
    """Repository registry"""

    __tablename__ = "git_repos"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_uuid)
    provider_id: Mapped[str] = mapped_column(String(32), ForeignKey("git_providers.id"), index=True)
    project_id: Mapped[str | None] = mapped_column(
        String(32), ForeignKey("flow_projects.id"), nullable=True, index=True
    )
    name: Mapped[str] = mapped_column(String(128))
    full_name: Mapped[str] = mapped_column(String(256), unique=True)
    clone_url: Mapped[str] = mapped_column(String(512), default="")
    ssh_url: Mapped[str] = mapped_column(String(512), default="")
    default_branch: Mapped[str] = mapped_column(String(64), default="main")
    description: Mapped[str] = mapped_column(Text, default="")
    language: Mapped[str] = mapped_column(String(64), default="")
    repo_type: Mapped[str] = mapped_column(String(16), default="other")  # frontend/backend/mobile/docs/infra/other
    is_private: Mapped[bool] = mapped_column(Boolean, default=False)
    webhook_secret: Mapped[str] = mapped_column(String(128), default="")
    last_synced_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())


class GitRepoMember(Base):
    """Repository member access control"""

    __tablename__ = "git_repo_members"
    __table_args__ = (
        UniqueConstraint("repo_id", "member_id", name="uq_git_repo_member"),
    )

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_uuid)
    repo_id: Mapped[str] = mapped_column(String(32), ForeignKey("git_repos.id"), index=True)
    member_id: Mapped[str] = mapped_column(String(32), ForeignKey("members.id"), index=True)
    access_level: Mapped[str] = mapped_column(String(16), default="read")  # read/write/admin
    platform_username: Mapped[str] = mapped_column(String(64), default="")


class GitWorkspace(Base):
    """Per-member cloned workspace for AI coding"""

    __tablename__ = "git_workspaces"
    __table_args__ = (
        UniqueConstraint("repo_id", "member_id", name="uq_git_workspace"),
    )

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_uuid)
    repo_id: Mapped[str] = mapped_column(String(32), ForeignKey("git_repos.id"), index=True)
    member_id: Mapped[str] = mapped_column(String(32), ForeignKey("members.id"), index=True)
    local_path: Mapped[str] = mapped_column(String(512), default="")
    current_branch: Mapped[str] = mapped_column(String(128), default="")
    status: Mapped[str] = mapped_column(String(16), default="idle")  # idle/busy/error
    disk_usage_mb: Mapped[int] = mapped_column(Integer, default=0)
    last_used_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)


class GitCodeTask(Base):
    """AI coding task history for auditing"""

    __tablename__ = "git_code_tasks"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_uuid)
    repo_id: Mapped[str] = mapped_column(String(32), ForeignKey("git_repos.id"), index=True)
    member_id: Mapped[str] = mapped_column(String(32), ForeignKey("members.id"), index=True)
    story_id: Mapped[str | None] = mapped_column(String(32), nullable=True)
    task_id: Mapped[str | None] = mapped_column(String(32), nullable=True)
    bug_id: Mapped[str | None] = mapped_column(String(32), nullable=True)
    cli_tool: Mapped[str] = mapped_column(String(32), default="")
    task_description: Mapped[str] = mapped_column(Text, default="")
    branch_name: Mapped[str] = mapped_column(String(128), default="")
    status: Mapped[str] = mapped_column(String(16), default="pending", index=True)  # pending/running/success/failed/review
    pr_url: Mapped[str] = mapped_column(String(512), default="")
    files_changed: Mapped[str] = mapped_column(Text, default="[]")  # JSON
    diff_summary: Mapped[str] = mapped_column(Text, default="")
    cli_stdout: Mapped[str] = mapped_column(Text, default="")
    cli_stderr: Mapped[str] = mapped_column(Text, default="")
    duration_seconds: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
