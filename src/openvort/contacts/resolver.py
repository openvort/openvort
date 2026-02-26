"""
身份解析器

提供 platform + user_id -> Member 的快速解析，带内存缓存。
Agent Runtime 和 Plugin Tool 的核心依赖。
"""

from sqlalchemy import select
from sqlalchemy.orm import selectinload

from openvort.contacts.models import Member, PlatformIdentity
from openvort.utils.logging import get_logger

log = get_logger("contacts.resolver")


class IdentityResolver:
    """身份解析器 — 将平台用户 ID 解析为 OpenVort 成员"""

    def __init__(self, session_factory):
        """
        Args:
            session_factory: 返回 AsyncSession 的可调用对象（如 get_session）
        """
        self._session_factory = session_factory
        # 正向缓存: (platform, platform_user_id) -> member_id
        self._cache: dict[tuple[str, str], str] = {}
        # 反向缓存: (member_id, platform) -> platform_user_id
        self._reverse_cache: dict[tuple[str, str], str] = {}
        self._max_cache = 1024

    async def resolve(self, platform: str, platform_user_id: str) -> Member | None:
        """根据平台 + 用户 ID 解析成员

        Args:
            platform: 平台标识 (wecom / dingtalk / zentao ...)
            platform_user_id: 平台侧用户 ID

        Returns:
            Member 实例，未找到返回 None
        """
        # 查缓存
        cache_key = (platform, platform_user_id)
        if cache_key in self._cache:
            member_id = self._cache[cache_key]
            async with self._session_factory() as session:
                result = await session.execute(select(Member).where(Member.id == member_id))
                return result.scalar_one_or_none()

        # 查数据库
        async with self._session_factory() as session:
            stmt = (
                select(PlatformIdentity)
                .options(selectinload(PlatformIdentity.member))
                .where(
                    PlatformIdentity.platform == platform,
                    PlatformIdentity.platform_user_id == platform_user_id,
                )
            )
            result = await session.execute(stmt)
            identity = result.scalar_one_or_none()

            if identity and identity.member:
                self._put_cache(platform, platform_user_id, identity.member.id)
                return identity.member

        return None

    async def get_platform_id(self, member_id: str, platform: str) -> str | None:
        """反向查找：成员在某平台的用户 ID

        Args:
            member_id: OpenVort 成员 ID
            platform: 目标平台标识

        Returns:
            平台侧用户 ID，未找到返回 None
        """
        # 查缓存
        reverse_key = (member_id, platform)
        if reverse_key in self._reverse_cache:
            return self._reverse_cache[reverse_key]

        # 查数据库
        async with self._session_factory() as session:
            stmt = select(PlatformIdentity.platform_user_id).where(
                PlatformIdentity.member_id == member_id,
                PlatformIdentity.platform == platform,
            )
            result = await session.execute(stmt)
            row = result.scalar_one_or_none()

            if row:
                self._reverse_cache[reverse_key] = row
                return row

        return None

    def invalidate(self, platform: str, platform_user_id: str) -> None:
        """清除指定身份的缓存"""
        cache_key = (platform, platform_user_id)
        member_id = self._cache.pop(cache_key, None)
        if member_id:
            self._reverse_cache.pop((member_id, platform), None)

    def clear_cache(self) -> None:
        """清空全部缓存"""
        self._cache.clear()
        self._reverse_cache.clear()

    def _put_cache(self, platform: str, platform_user_id: str, member_id: str) -> None:
        """写入缓存，超限时清空重建"""
        if len(self._cache) >= self._max_cache:
            self._cache.clear()
            self._reverse_cache.clear()
        self._cache[(platform, platform_user_id)] = member_id
        self._reverse_cache[(member_id, platform)] = platform_user_id
