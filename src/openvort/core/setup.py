"""
OpenVort 初始化状态管理

SetupState 表存储系统级配置（key-value），
提供初始化检测和标记的辅助函数。
"""

from datetime import datetime

from sqlalchemy import DateTime, String, Text, func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from sqlalchemy.orm import Mapped, mapped_column

from openvort.db.engine import Base
from openvort.utils.logging import get_logger

log = get_logger("core.setup")


class SetupState(Base):
    """系统配置 key-value 表"""

    __tablename__ = "setup_state"

    key: Mapped[str] = mapped_column(String(64), primary_key=True)
    value: Mapped[str] = mapped_column(Text, default="")
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())


async def is_initialized(session_factory: async_sessionmaker[AsyncSession]) -> bool:
    """检查 OpenVort 是否已完成初始化"""
    async with session_factory() as session:
        result = await session.execute(
            select(SetupState.value).where(SetupState.key == "initialized")
        )
        val = result.scalar_one_or_none()
        return val == "true"


async def get_setup_value(session_factory: async_sessionmaker[AsyncSession], key: str) -> str | None:
    """获取配置值"""
    async with session_factory() as session:
        result = await session.execute(
            select(SetupState.value).where(SetupState.key == key)
        )
        return result.scalar_one_or_none()


async def set_setup_value(session_factory: async_sessionmaker[AsyncSession], key: str, value: str) -> None:
    """设置配置值（upsert）"""
    async with session_factory() as session:
        result = await session.execute(
            select(SetupState).where(SetupState.key == key)
        )
        existing = result.scalar_one_or_none()
        if existing:
            existing.value = value
            existing.updated_at = datetime.now()
        else:
            session.add(SetupState(key=key, value=value))
        await session.commit()


async def mark_initialized(session_factory: async_sessionmaker[AsyncSession], admin_member_id: str) -> None:
    """标记系统已初始化"""
    await set_setup_value(session_factory, "initialized", "true")
    await set_setup_value(session_factory, "admin_member_id", admin_member_id)
    log.info(f"OpenVort 已初始化，管理员: {admin_member_id}")
