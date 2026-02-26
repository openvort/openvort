"""
身份智能匹配

新平台同步时，根据 email > phone > 姓名相似度 自动匹配已有成员。
高置信度自动关联，低置信度生成 MatchSuggestion 待管理员确认。
"""

from difflib import SequenceMatcher

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from openvort.contacts.models import MatchSuggestion, Member, PlatformIdentity
from openvort.contacts.sync import PlatformContact
from openvort.utils.logging import get_logger

log = get_logger("contacts.matcher")


class IdentityMatcher:
    """身份智能匹配器"""

    def __init__(self, session: AsyncSession, auto_threshold: float = 0.9):
        self._session = session
        self._auto_threshold = auto_threshold

    async def find_matches(self, contact: PlatformContact) -> list[MatchSuggestion]:
        """为一个平台联系人查找可能匹配的已有成员

        匹配优先级: email(1.0) > phone(0.9) > name 相似度(0.0~0.8)
        同时查 Member 表和 PlatformIdentity 表的 email/phone。

        Returns:
            匹配建议列表（可能为空）
        """
        matches: list[MatchSuggestion] = []

        # 1. email 精确匹配（Member 表 + PlatformIdentity 表）
        if contact.email:
            member = await self._match_by_field("email", contact.email)
            if not member:
                member = await self._match_by_identity_field("email", contact.email)
            if member:
                log.debug(f"email 匹配: {contact.display_name} -> {member.name}")
                return [self._make_suggestion(member.id, "email", 1.0)]

        # 2. phone 精确匹配（Member 表 + PlatformIdentity 表）
        if contact.phone:
            member = await self._match_by_field("phone", contact.phone)
            if not member:
                member = await self._match_by_identity_field("phone", contact.phone)
            if member:
                log.debug(f"phone 匹配: {contact.display_name} -> {member.name}")
                return [self._make_suggestion(member.id, "phone", 0.9)]

        # 3. 姓名相似度匹配
        if contact.display_name:
            name_matches = await self._match_by_name(contact.display_name)
            matches.extend(name_matches)

        return matches

    async def _match_by_field(self, field: str, value: str) -> Member | None:
        """按 Member 表字段精确匹配"""
        stmt = select(Member).where(
            getattr(Member, field) == value,
            Member.status == "active",
        )
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def _match_by_identity_field(self, field: str, value: str) -> Member | None:
        """按 PlatformIdentity 的 email/phone 匹配，返回关联的 Member"""
        pi_field = f"platform_{field}"  # platform_email / platform_phone
        stmt = (
            select(PlatformIdentity)
            .options(selectinload(PlatformIdentity.member))
            .where(getattr(PlatformIdentity, pi_field) == value)
        )
        result = await self._session.execute(stmt)
        identity = result.scalars().first()
        if identity and identity.member and identity.member.status == "active":
            return identity.member
        return None

    async def _match_by_name(self, name: str) -> list[MatchSuggestion]:
        """按姓名相似度匹配"""
        stmt = select(Member).where(Member.status == "active")
        result = await self._session.execute(stmt)
        members = result.scalars().all()

        suggestions = []
        for member in members:
            ratio = SequenceMatcher(None, name, member.name).ratio()
            if ratio >= 0.8:
                suggestions.append(self._make_suggestion(member.id, "name", round(ratio * 0.8, 2)))

        # 按置信度降序
        suggestions.sort(key=lambda s: s.confidence, reverse=True)
        return suggestions

    @staticmethod
    def _make_suggestion(member_id: str, match_type: str, confidence: float) -> MatchSuggestion:
        """构造匹配建议（尚未设置 source_identity_id，由调用方补充）"""
        return MatchSuggestion(
            target_member_id=member_id,
            match_type=match_type,
            confidence=confidence,
            status="pending",
        )
