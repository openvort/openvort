"""
权限模型

核心 RBAC：Role（角色）、Permission（权限）、MemberRole（成员-角色绑定）、RolePermission（角色-权限绑定）。
支持核心内置角色和插件扩展角色。
"""

from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from openvort.db.engine import Base


class Role(Base):
    """角色"""

    __tablename__ = "roles"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(32), unique=True)  # admin / manager / member / guest / zentao_pm
    display_name: Mapped[str] = mapped_column(String(64), default="")
    source: Mapped[str] = mapped_column(String(32), default="core")  # core / plugin_name
    is_builtin: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    def __repr__(self) -> str:
        return f"<Role {self.name}>"


class Permission(Base):
    """权限"""

    __tablename__ = "permissions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    code: Mapped[str] = mapped_column(String(64), unique=True)  # contacts.sync / zentao.create_task
    display_name: Mapped[str] = mapped_column(String(64), default="")
    source: Mapped[str] = mapped_column(String(32), default="core")  # core / plugin_name
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    def __repr__(self) -> str:
        return f"<Permission {self.code}>"


class MemberRole(Base):
    """成员-角色绑定"""

    __tablename__ = "member_roles"
    __table_args__ = (
        UniqueConstraint("member_id", "role_id", name="uq_member_role"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    member_id: Mapped[str] = mapped_column(String(32), ForeignKey("members.id"), index=True)
    role_id: Mapped[int] = mapped_column(Integer, ForeignKey("roles.id"), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class RolePermission(Base):
    """角色-权限绑定"""

    __tablename__ = "role_permissions"
    __table_args__ = (
        UniqueConstraint("role_id", "permission_id", name="uq_role_permission"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    role_id: Mapped[int] = mapped_column(Integer, ForeignKey("roles.id"), index=True)
    permission_id: Mapped[int] = mapped_column(Integer, ForeignKey("permissions.id"), index=True)
