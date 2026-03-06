"""
通讯录服务

CRUD、同步编排、搜索。所有通讯录操作的统一入口。
"""

import json
from datetime import datetime

from sqlalchemy import func as sa_func
from sqlalchemy import or_, select

from openvort.contacts.matcher import IdentityMatcher
from openvort.contacts.models import Department, MatchSuggestion, Member, MemberDepartment, PlatformIdentity
from openvort.contacts.sync import ContactSyncProvider, PlatformContact, PlatformDepartment
from openvort.utils.logging import get_logger

log = get_logger("contacts.service")


# Avatar source priority: higher value wins, "manual" always takes precedence
AVATAR_SOURCE_PRIORITY: dict[str, int] = {
    "": 0,
    "dingtalk": 10,
    "feishu": 10,
    "zentao": 10,
    "gitee": 10,
    "wecom": 20,
    "manual": 100,
}


def _avatar_priority(source: str) -> int:
    return AVATAR_SOURCE_PRIORITY.get(source, 10)


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

    async def search_members_by_name_prefix(self, prefix: str) -> list[Member]:
        """按姓名前缀搜索（用于称谓匹配场景，如 "杨" 匹配 "杨明" "杨强"）"""
        pattern = f"{prefix}%"
        async with self._session_factory() as session:
            stmt = select(Member).where(
                Member.status == "active",
                Member.name.ilike(pattern),
            ).order_by(Member.name)
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
                    # 同步部门关联
                    await self._sync_member_departments(session, member.id, platform, contact.department)

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
                    await session.flush()
                    await self._sync_member_departments(session, best.target_member_id, platform, contact.department)
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

                    await self._sync_member_departments(session, member.id, platform, contact.department)
                    await session.commit()
                    return "pending"

            # 无匹配，创建新成员
            member = self._create_member_from_contact(contact)
            session.add(member)
            await session.flush()

            identity = self._create_identity(member.id, contact)
            session.add(identity)
            await session.flush()

            await self._sync_member_departments(session, member.id, platform, contact.department)
            await session.commit()
            return "created"

    async def _sync_member_departments(
        self, session, member_id: str, platform: str, dept_str: str
    ) -> None:
        """根据同步的部门信息写入成员-部门关联

        dept_str 格式: 逗号分隔的平台部门 ID，如 "1,3,5"
        """
        if not dept_str:
            return

        dept_ids_str = [d.strip() for d in dept_str.split(",") if d.strip()]
        if not dept_ids_str:
            return

        # 查找本地部门
        for i, platform_dept_id in enumerate(dept_ids_str):
            stmt = select(Department).where(
                Department.platform == platform,
                Department.platform_dept_id == platform_dept_id,
            )
            result = await session.execute(stmt)
            dept = result.scalar_one_or_none()
            if not dept:
                continue

            # 检查是否已存在关联
            stmt = select(MemberDepartment).where(
                MemberDepartment.member_id == member_id,
                MemberDepartment.department_id == dept.id,
            )
            result = await session.execute(stmt)
            existing = result.scalar_one_or_none()
            if not existing:
                session.add(MemberDepartment(
                    member_id=member_id,
                    department_id=dept.id,
                    is_primary=(i == 0),  # 第一个部门为主部门
                ))
            elif i == 0 and not existing.is_primary:
                existing.is_primary = True

    async def _sync_departments(self, platform: str, departments: list[PlatformDepartment]) -> None:
        """同步部门列表（两遍扫描：先创建/更新，再映射 parent_id）"""
        async with self._session_factory() as session:
            # 第一遍：创建或更新部门
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
            await session.flush()

            # 第二遍：映射 parent_id（platform_dept_id -> 本地 id）
            for dept in departments:
                if not dept.parent_dept_id:
                    continue
                # 查本部门
                stmt = select(Department).where(
                    Department.platform == platform,
                    Department.platform_dept_id == dept.dept_id,
                )
                result = await session.execute(stmt)
                local_dept = result.scalar_one_or_none()
                if not local_dept:
                    continue

                # 查父部门
                stmt = select(Department).where(
                    Department.platform == platform,
                    Department.platform_dept_id == dept.parent_dept_id,
                )
                result = await session.execute(stmt)
                parent_dept = result.scalar_one_or_none()
                local_dept.parent_id = parent_dept.id if parent_dept else None

            await session.commit()

    # ---- 匹配建议管理 ----

    async def list_pending_suggestions(self) -> list[MatchSuggestion]:
        """列出所有待确认的匹配建议"""
        from sqlalchemy.orm import selectinload

        async with self._session_factory() as session:
            stmt = (
                select(MatchSuggestion)
                .options(
                    selectinload(MatchSuggestion.source_identity),
                    selectinload(MatchSuggestion.target_member),
                )
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

    async def merge_members(self, source_id: str, target_id: str) -> bool:
        """手动合并两个成员：将 source 的所有 identity 迁移到 target，然后删除 source"""
        from sqlalchemy import delete, update

        if source_id == target_id:
            return False
        async with self._session_factory() as session:
            # 确认两个 member 都存在
            source = await session.get(Member, source_id)
            target = await session.get(Member, target_id)
            if not source or not target:
                return False

            # 回填 target 缺失的信息
            if not target.email and source.email:
                target.email = source.email
            if not target.phone and source.phone:
                target.phone = source.phone
            if not target.position and source.position:
                target.position = source.position

            # 用 SQL 直接迁移 identity，绕过 cascade
            await session.execute(
                update(PlatformIdentity)
                .where(PlatformIdentity.member_id == source_id)
                .values(member_id=target_id)
            )

            # 将指向 source 的 suggestions 改指向 target
            await session.execute(
                update(MatchSuggestion)
                .where(MatchSuggestion.target_member_id == source_id)
                .values(target_member_id=target_id)
            )

            # 用 SQL 直接删除 source member
            await session.execute(
                delete(Member).where(Member.id == source_id)
            )

            await session.commit()
            log.info(f"合并成员: {source.name}({source_id[:8]}) -> {target.name}({target_id[:8]})")
            return True

    async def dedup_members(self) -> dict:
        """扫描同名 Member，直接自动合并完全同名的重复项。返回合并统计。"""
        from sqlalchemy import delete, update

        async with self._session_factory() as session:
            # 找出同名的 active member（按 name 分组，count > 1）
            stmt = (
                select(Member.name)
                .where(Member.status == "active")
                .group_by(Member.name)
                .having(sa_func.count() > 1)
            )
            result = await session.execute(stmt)
            dup_names = [row[0] for row in result.all()]

            merged = 0
            for name in dup_names:
                stmt = (
                    select(Member)
                    .where(Member.status == "active", Member.name == name)
                    .order_by(Member.created_at)
                )
                result = await session.execute(stmt)
                members = list(result.scalars().all())
                if len(members) < 2:
                    continue

                target = members[0]  # 最早创建的作为 target
                for source in members[1:]:
                    source_id = source.id
                    # 回填 target 缺失的信息
                    if not target.email and source.email:
                        target.email = source.email
                    if not target.phone and source.phone:
                        target.phone = source.phone
                    if not target.position and source.position:
                        target.position = source.position

                    # 用 SQL 直接迁移 identity，绕过 cascade
                    await session.execute(
                        update(PlatformIdentity)
                        .where(PlatformIdentity.member_id == source_id)
                        .values(member_id=target.id)
                    )

                    # 将指向 source 的 suggestions 改指向 target
                    await session.execute(
                        update(MatchSuggestion)
                        .where(MatchSuggestion.target_member_id == source_id)
                        .values(target_member_id=target.id, status="accepted", resolved_at=datetime.now())
                    )

                    # 用 SQL 直接删除 source member，绕过 cascade
                    await session.execute(
                        delete(Member).where(Member.id == source_id)
                    )

                    # 让 session 清除对已删除对象的跟踪
                    session.expire_all()

                    merged += 1
                    log.info(f"去重合并: {name}({source_id[:8]}) -> {name}({target.id[:8]})")

            await session.commit()
            log.info(f"去重扫描完成: 合并 {merged} 个重复成员")
            return {"merged": merged}

    # ---- 部门管理 ----

    async def list_departments(self, platform: str = "") -> list[Department]:
        """列出所有部门（可按平台过滤）"""
        async with self._session_factory() as session:
            stmt = select(Department).order_by(Department.order, Department.id)
            if platform:
                stmt = stmt.where(Department.platform == platform)
            result = await session.execute(stmt)
            return list(result.scalars().all())

    async def get_department_tree(self, platform: str = "") -> list[dict]:
        """获取部门树形结构（含成员数）"""
        async with self._session_factory() as session:
            stmt = select(Department).order_by(Department.order, Department.id)
            if platform:
                stmt = stmt.where(Department.platform == platform)
            result = await session.execute(stmt)
            departments = list(result.scalars().all())

            # 查每个部门的成员数
            dept_member_counts = {}
            for dept in departments:
                count_stmt = select(sa_func.count()).select_from(MemberDepartment).where(
                    MemberDepartment.department_id == dept.id
                )
                count_result = await session.execute(count_stmt)
                dept_member_counts[dept.id] = count_result.scalar() or 0

        # 构建树
        dept_map = {}
        for dept in departments:
            dept_map[dept.id] = {
                "id": dept.id,
                "name": dept.name,
                "parent_id": dept.parent_id,
                "platform": dept.platform,
                "platform_dept_id": dept.platform_dept_id,
                "order": dept.order,
                "member_count": dept_member_counts.get(dept.id, 0),
                "children": [],
            }

        roots = []
        for dept_id, node in dept_map.items():
            parent_id = node["parent_id"]
            if parent_id and parent_id in dept_map:
                dept_map[parent_id]["children"].append(node)
            else:
                roots.append(node)

        return roots

    async def get_department(self, dept_id: int) -> Department | None:
        async with self._session_factory() as session:
            return await session.get(Department, dept_id)

    async def create_department(self, name: str, parent_id: int | None = None, platform: str = "manual") -> Department:
        async with self._session_factory() as session:
            dept = Department(name=name, parent_id=parent_id, platform=platform)
            session.add(dept)
            await session.commit()
            await session.refresh(dept)
            return dept

    async def update_department(self, dept_id: int, name: str | None = None, parent_id: int | None = ..., order: int | None = None) -> bool:
        async with self._session_factory() as session:
            dept = await session.get(Department, dept_id)
            if not dept:
                return False
            if name is not None:
                dept.name = name
            if parent_id is not ...:
                dept.parent_id = parent_id
            if order is not None:
                dept.order = order
            await session.commit()
            return True

    async def delete_department(self, dept_id: int) -> bool:
        """删除部门（同时删除成员关联，子部门上移到父级）"""
        async with self._session_factory() as session:
            dept = await session.get(Department, dept_id)
            if not dept:
                return False

            # 子部门上移到父级
            children_stmt = select(Department).where(Department.parent_id == dept_id)
            children_result = await session.execute(children_stmt)
            for child in children_result.scalars().all():
                child.parent_id = dept.parent_id

            # 删除成员-部门关联
            from sqlalchemy import delete
            await session.execute(
                delete(MemberDepartment).where(MemberDepartment.department_id == dept_id)
            )

            await session.delete(dept)
            await session.commit()
            return True

    async def get_department_members(self, dept_id: int) -> list[dict]:
        """获取部门下的成员列表"""
        async with self._session_factory() as session:
            stmt = (
                select(Member, MemberDepartment.is_primary)
                .join(MemberDepartment, MemberDepartment.member_id == Member.id)
                .where(MemberDepartment.department_id == dept_id)
                .order_by(Member.name)
            )
            result = await session.execute(stmt)
            items = []
            for member, is_primary in result.all():
                items.append({
                    "id": member.id,
                    "name": member.name,
                    "email": member.email or "",
                    "phone": member.phone or "",
                    "is_primary": is_primary,
                })
            return items

    async def add_member_to_department(self, dept_id: int, member_id: str, is_primary: bool = False) -> bool:
        async with self._session_factory() as session:
            # 检查是否已存在
            stmt = select(MemberDepartment).where(
                MemberDepartment.member_id == member_id,
                MemberDepartment.department_id == dept_id,
            )
            result = await session.execute(stmt)
            if result.scalar_one_or_none():
                return False  # 已存在
            session.add(MemberDepartment(member_id=member_id, department_id=dept_id, is_primary=is_primary))
            await session.commit()
            return True

    async def remove_member_from_department(self, dept_id: int, member_id: str) -> bool:
        async with self._session_factory() as session:
            stmt = select(MemberDepartment).where(
                MemberDepartment.member_id == member_id,
                MemberDepartment.department_id == dept_id,
            )
            result = await session.execute(stmt)
            link = result.scalar_one_or_none()
            if not link:
                return False
            await session.delete(link)
            await session.commit()
            return True

    # ---- 内部工具方法 ----

    @staticmethod
    def _create_member_from_contact(contact: PlatformContact) -> Member:
        return Member(
            name=contact.display_name or contact.username or contact.user_id,
            email=contact.email,
            phone=contact.phone,
            avatar_url=contact.avatar_url or "",
            avatar_source=contact.platform if contact.avatar_url else "",
            position=contact.position or "",
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
        """回填 Member 缺失的 email/phone/name/position/avatar（从同步的联系人信息补充）"""
        if not member.email and contact.email:
            member.email = contact.email
        if not member.phone and contact.phone:
            member.phone = contact.phone
        if not member.name and contact.display_name:
            member.name = contact.display_name
        if not member.position and contact.position:
            member.position = contact.position
        if contact.avatar_url and _avatar_priority(contact.platform) >= _avatar_priority(member.avatar_source):
            member.avatar_url = contact.avatar_url
            member.avatar_source = contact.platform

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
