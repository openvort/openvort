"""
通讯录服务

CRUD、同步编排、搜索。所有通讯录操作的统一入口。
"""

import json
from datetime import datetime

from sqlalchemy import func as sa_func
from sqlalchemy import or_, select

from openvort.contacts.matcher import IdentityMatcher
from openvort.contacts.models import Department, MatchSuggestion, Member, PlatformIdentity
from openvort.contacts.sync import ContactSyncProvider, PlatformContact, PlatformDepartment
from openvort.utils.logging import get_logger

log = get_logger("contacts.service")


class ContactService:
    """通讯录服务 — 统一管理成员、身份映射、同步"""

    def __init__(self, session_factory, auto_match_threshold: float = 0.9, auth_service=None):
        self._session_factory = session_factory
        self._auto_threshold = auto_match_threshold
        self._auth = auth_service

    # ---- 成员 CRUD ----

    async def get_member(self, member_id: str) -> Member | None:
        async with self._session_factory() as session:
            result = await session.execute(select(Member).where(Member.id == member_id))
            return result.scalar_one_or_none()

    async def list_members(self, status: str = "active") -> list[Member]:
        async with self._session_factory() as session:
            stmt = select(Member).where(Member.status == status).order_by(Member.name)
            result = await session.execute(stmt)
            return list(result.scalars().all())

    async def search_members(self, keyword: str) -> list[Member]:
        """按姓名/邮箱/手机模糊搜索"""
        pattern = f"%{keyword}%"
        async with self._session_factory() as session:
            stmt = select(Member).where(
                Member.status == "active",
                or_(
                    Member.name.ilike(pattern),
                    Member.email.ilike(pattern),
                    Member.phone.ilike(pattern),
                ),
            )
            result = await session.execute(stmt)
            return list(result.scalars().all())

    async def get_member_identities(self, member_id: str) -> list[PlatformIdentity]:
        """获取成员的所有平台身份"""
        async with self._session_factory() as session:
            stmt = select(PlatformIdentity).where(PlatformIdentity.member_id == member_id)
            result = await session.execute(stmt)
            return list(result.scalars().all())

    # ---- 同步编排 ----

    async def sync_from_provider(self, provider: ContactSyncProvider) -> dict:
        """从指定平台同步通讯录

        Returns:
            同步统计: {"created": N, "updated": N, "matched": N, "pending": N}
        """
        platform = provider.platform
        log.info(f"开始同步通讯录: {platform}")

        stats = {"created": 0, "updated": 0, "matched": 0, "pending": 0}

        # 1. 同步部门
        try:
            departments = await provider.fetch_departments()
            await self._sync_departments(platform, departments)
            log.info(f"已同步 {len(departments)} 个部门 ({platform})")
        except Exception as e:
            log.warning(f"同步部门失败 ({platform}): {e}")

        # 2. 同步成员
        contacts = await provider.fetch_members()
        log.info(f"拉取到 {len(contacts)} 个联系人 ({platform})")

        for contact in contacts:
            result = await self._sync_one_contact(platform, contact)
            stats[result] += 1

        log.info(
            f"同步完成 ({platform}): "
            f"新建 {stats['created']}, 更新 {stats['updated']}, "
            f"自动关联 {stats['matched']}, 待确认 {stats['pending']}"
        )

        # 3. 自动映射组织角色
        if self._auth:
            mapped = await self._map_roles_from_position(contacts)
            if mapped:
                log.info(f"角色映射: {mapped} 人已分配角色 ({platform})")

        return stats

    async def _sync_one_contact(self, platform: str, contact: PlatformContact) -> str:
        """同步单个联系人，返回操作类型"""
        async with self._session_factory() as session:
            # 检查 PlatformIdentity 是否已存在
            stmt = select(PlatformIdentity).where(
                PlatformIdentity.platform == platform,
                PlatformIdentity.platform_user_id == contact.user_id,
            )
            result = await session.execute(stmt)
            existing = result.scalar_one_or_none()

            if existing:
                # 已存在，更新信息
                self._update_identity_from_contact(existing, contact)
                existing.synced_at = datetime.now()

                # 回填 Member 的 email/phone（如果 Member 缺失但 contact 有值）
                member = await session.get(Member, existing.member_id)
                if member:
                    self._backfill_member_info(member, contact)

                await session.commit()
                return "updated"

            # 不存在，尝试智能匹配
            matcher = IdentityMatcher(session, self._auto_threshold)
            suggestions = await matcher.find_matches(contact)

            if suggestions:
                best = suggestions[0]
                if best.confidence >= self._auto_threshold:
                    # 高置信度，自动关联
                    identity = self._create_identity(best.target_member_id, contact)
                    session.add(identity)
                    await session.commit()
                    return "matched"
                else:
                    # 低置信度，创建 identity 挂到新 member，同时生成建议
                    member = self._create_member_from_contact(contact)
                    session.add(member)
                    await session.flush()

                    identity = self._create_identity(member.id, contact)
                    session.add(identity)
                    await session.flush()

                    for s in suggestions:
                        s.source_identity_id = identity.id
                        session.add(s)

                    await session.commit()
                    return "pending"

            # 无匹配，创建新成员
            member = self._create_member_from_contact(contact)
            session.add(member)
            await session.flush()

            identity = self._create_identity(member.id, contact)
            session.add(identity)
            await session.commit()
            return "created"

    async def _sync_departments(self, platform: str, departments: list[PlatformDepartment]) -> None:
        """同步部门列表"""
        async with self._session_factory() as session:
            for dept in departments:
                stmt = select(Department).where(
                    Department.platform == platform,
                    Department.platform_dept_id == dept.dept_id,
                )
                result = await session.execute(stmt)
                existing = result.scalar_one_or_none()

                if existing:
                    existing.name = dept.name
                else:
                    session.add(Department(
                        name=dept.name,
                        platform=platform,
                        platform_dept_id=dept.dept_id,
                    ))
            await session.commit()

    # ---- 匹配建议管理 ----

    async def list_pending_suggestions(self) -> list[MatchSuggestion]:
        """列出所有待确认的匹配建议"""
        async with self._session_factory() as session:
            stmt = (
                select(MatchSuggestion)
                .where(MatchSuggestion.status == "pending")
                .order_by(MatchSuggestion.confidence.desc())
            )
            result = await session.execute(stmt)
            return list(result.scalars().all())

    async def accept_suggestion(self, suggestion_id: int, resolved_by: str = "") -> bool:
        """接受匹配建议：将 source identity 关联到 target member"""
        async with self._session_factory() as session:
            result = await session.execute(
                select(MatchSuggestion).where(MatchSuggestion.id == suggestion_id)
            )
            suggestion = result.scalar_one_or_none()
            if not suggestion or suggestion.status != "pending":
                return False

            # 将 identity 的 member_id 改为 target
            identity_result = await session.execute(
                select(PlatformIdentity).where(PlatformIdentity.id == suggestion.source_identity_id)
            )
            identity = identity_result.scalar_one_or_none()
            if not identity:
                return False

            old_member_id = identity.member_id
            identity.member_id = suggestion.target_member_id

            # 标记建议为已接受
            suggestion.status = "accepted"
            suggestion.resolved_by = resolved_by
            suggestion.resolved_at = datetime.now()

            # 删除自动创建的空 member（如果没有其他 identity 引用它）
            other_count_result = await session.execute(
                select(sa_func.count()).select_from(PlatformIdentity).where(
                    PlatformIdentity.member_id == old_member_id,
                    PlatformIdentity.id != identity.id,
                )
            )
            if other_count_result.scalar() == 0:
                old_member_result = await session.execute(
                    select(Member).where(Member.id == old_member_id)
                )
                old_member = old_member_result.scalar_one_or_none()
                if old_member:
                    await session.delete(old_member)

            await session.commit()
            return True

    async def reject_suggestion(self, suggestion_id: int, resolved_by: str = "") -> bool:
        """拒绝匹配建议"""
        async with self._session_factory() as session:
            result = await session.execute(
                select(MatchSuggestion).where(MatchSuggestion.id == suggestion_id)
            )
            suggestion = result.scalar_one_or_none()
            if not suggestion or suggestion.status != "pending":
                return False

            suggestion.status = "rejected"
            suggestion.resolved_by = resolved_by
            suggestion.resolved_at = datetime.now()
            await session.commit()
            return True

    # ---- 内部工具方法 ----

    @staticmethod
    def _create_member_from_contact(contact: PlatformContact) -> Member:
        return Member(
            name=contact.display_name or contact.username or contact.user_id,
            email=contact.email,
            phone=contact.phone,
        )

    @staticmethod
    def _create_identity(member_id: str, contact: PlatformContact) -> PlatformIdentity:
        return PlatformIdentity(
            member_id=member_id,
            platform=contact.platform,
            platform_user_id=contact.user_id,
            platform_username=contact.username,
            platform_display_name=contact.display_name,
            platform_email=contact.email,
            platform_phone=contact.phone,
            platform_position=contact.position,
            platform_department=contact.department,
            raw_data=json.dumps(contact.raw_data, ensure_ascii=False) if contact.raw_data else "{}",
        )

    @staticmethod
    def _update_identity_from_contact(identity: PlatformIdentity, contact: PlatformContact) -> None:
        identity.platform_username = contact.username
        identity.platform_display_name = contact.display_name
        identity.platform_email = contact.email
        identity.platform_phone = contact.phone
        identity.platform_position = contact.position
        identity.platform_department = contact.department
        identity.raw_data = json.dumps(contact.raw_data, ensure_ascii=False) if contact.raw_data else "{}"

    @staticmethod
    def _backfill_member_info(member: Member, contact: PlatformContact) -> None:
        """回填 Member 缺失的 email/phone/name（从同步的联系人信息补充）"""
        if not member.email and contact.email:
            member.email = contact.email
        if not member.phone and contact.phone:
            member.phone = contact.phone
        if not member.name and contact.display_name:
            member.name = contact.display_name

    # ---- 角色映射 ----

    async def _map_roles_from_position(self, contacts: list[PlatformContact]) -> int:
        """根据职位自动映射组织角色，返回映射成功的人数"""
        from openvort.config.settings import get_settings
        settings = get_settings()

        # 解析映射规则: "总经理:admin,经理:manager" -> {"总经理": "admin", "经理": "manager"}
        mapping = {}
        for pair in settings.contacts.role_mapping.split(","):
            pair = pair.strip()
            if ":" in pair:
                position, role = pair.split(":", 1)
                mapping[position.strip()] = role.strip()

        if not mapping:
            return 0

        mapped_count = 0
        for contact in contacts:
            if not contact.position:
                continue

            # 匹配职位（支持包含匹配，如"技术总监"匹配"总监"）
            target_role = None
            for position_key, role_name in mapping.items():
                if position_key in contact.position:
                    target_role = role_name
                    break

            if not target_role:
                # 未匹配到，分配默认 member 角色
                target_role = "member"

            # 查找该联系人对应的 member_id
            async with self._session_factory() as session:
                stmt = select(PlatformIdentity.member_id).where(
                    PlatformIdentity.platform == contact.platform,
                    PlatformIdentity.platform_user_id == contact.user_id,
                )
                result = await session.execute(stmt)
                member_id = result.scalar_one_or_none()

            if member_id and self._auth:
                ok = await self._auth.assign_role(member_id, target_role)
                if ok:
                    mapped_count += 1

        return mapped_count
