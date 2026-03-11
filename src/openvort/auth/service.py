"""
权限服务

鉴权、角色管理、权限注册、内置种子数据初始化。
"""

from sqlalchemy import select, delete, text

from openvort.auth.models import MemberRole, Permission, Role, RolePermission
from openvort.utils.logging import get_logger

log = get_logger("auth.service")

# 内置角色定义
BUILTIN_ROLES = [
    {"name": "admin", "display_name": "管理员", "permissions": ["*"]},
    {"name": "manager", "display_name": "部门管理者", "permissions": [
        "contacts.sync", "contacts.search", "contacts.match",
        "wecom.send", "feishu.send", "dingtalk.send",
        "members.view", "departments.view",
        "plugins.view", "skills.view", "channels.view",
        "logs.view", "dashboard.view",
        "schedules.manage", "webhooks.view", "agents.view",
    ]},
    {"name": "member", "display_name": "普通成员", "permissions": [
        "contacts.search",
        "wecom.send", "feishu.send", "dingtalk.send",
        "dashboard.view", "schedules.use",
    ]},
    {"name": "guest", "display_name": "访客", "permissions": []},
]

# 内置权限定义
BUILTIN_PERMISSIONS = [
    # 通讯录
    {"code": "contacts.sync", "display_name": "同步通讯录"},
    {"code": "contacts.search", "display_name": "搜索成员"},
    {"code": "contacts.match", "display_name": "管理匹配建议"},
    # 渠道主动消息
    {"code": "wecom.send", "display_name": "发送企业微信消息"},
    {"code": "feishu.send", "display_name": "发送飞书消息"},
    {"code": "dingtalk.send", "display_name": "发送钉钉消息"},
    # 成员管理
    {"code": "members.view", "display_name": "查看成员"},
    {"code": "members.manage", "display_name": "管理成员"},
    # 部门管理
    {"code": "departments.view", "display_name": "查看部门"},
    {"code": "departments.manage", "display_name": "管理部门"},
    # 插件
    {"code": "plugins.view", "display_name": "查看插件"},
    {"code": "plugins.manage", "display_name": "管理插件"},
    # Skill
    {"code": "skills.view", "display_name": "查看 Skill"},
    {"code": "skills.manage", "display_name": "管理 Skill"},
    # 通道
    {"code": "channels.view", "display_name": "查看通道"},
    {"code": "channels.manage", "display_name": "管理通道"},
    # 系统设置
    {"code": "settings.view", "display_name": "查看设置"},
    {"code": "settings.manage", "display_name": "管理设置"},
    # 日志
    {"code": "logs.view", "display_name": "查看日志"},
    # 仪表盘
    {"code": "dashboard.view", "display_name": "查看仪表盘"},
    # 定时任务
    {"code": "schedules.use", "display_name": "使用定时任务"},
    {"code": "schedules.manage", "display_name": "管理定时任务"},
    # Webhook
    {"code": "webhooks.view", "display_name": "查看 Webhook"},
    {"code": "webhooks.manage", "display_name": "管理 Webhook"},
    # Agent
    {"code": "agents.view", "display_name": "查看 Agent"},
    {"code": "agents.manage", "display_name": "管理 Agent"},
]


class AuthService:
    """权限服务"""

    def __init__(self, session_factory):
        self._session_factory = session_factory
        # 权限缓存: member_id -> set[permission_code]
        self._cache: dict[str, set[str]] = {}
        self._max_cache = 512

    # ---- 初始化 ----

    async def init_builtin(self) -> None:
        """初始化内置角色和权限（幂等）"""
        async with self._session_factory() as session:
            # 注册内置权限
            for perm_def in BUILTIN_PERMISSIONS:
                await self._ensure_permission(session, perm_def["code"], perm_def["display_name"], "core")

            # 注册内置角色
            for role_def in BUILTIN_ROLES:
                role = await self._ensure_role(session, role_def["name"], role_def["display_name"], "core", True)
                # 绑定权限（* 表示全部权限，由 check_permission 特殊处理）
                if role_def["permissions"] != ["*"]:
                    for perm_code in role_def["permissions"]:
                        await self._ensure_role_permission(session, role.id, perm_code)

            await session.commit()
        log.info("内置角色和权限已初始化")

    # ---- 鉴权 ----

    async def check_permission(self, member_id: str, permission: str) -> bool:
        """检查成员是否有某权限"""
        perms = await self.get_member_permissions(member_id)
        # admin 角色有 * 通配权限
        return "*" in perms or permission in perms

    async def get_member_permissions(self, member_id: str) -> set[str]:
        """获取成员的所有权限码（含角色继承），带缓存"""
        if member_id in self._cache:
            return self._cache[member_id]

        async with self._session_factory() as session:
            # 查成员的所有角色
            stmt = (
                select(Role.name)
                .join(MemberRole, MemberRole.role_id == Role.id)
                .where(MemberRole.member_id == member_id)
            )
            result = await session.execute(stmt)
            role_names = set(result.scalars().all())

            # admin 角色直接返回通配
            if "admin" in role_names:
                perms = {"*"}
                self._put_cache(member_id, perms)
                return perms

            # 查所有角色关联的权限
            stmt = (
                select(Permission.code)
                .join(RolePermission, RolePermission.permission_id == Permission.id)
                .join(Role, Role.id == RolePermission.role_id)
                .join(MemberRole, MemberRole.role_id == Role.id)
                .where(MemberRole.member_id == member_id)
            )
            result = await session.execute(stmt)
            perms = set(result.scalars().all())

        self._put_cache(member_id, perms)
        return perms

    async def get_member_roles(self, member_id: str) -> list[str]:
        """获取成员的所有角色名"""
        async with self._session_factory() as session:
            stmt = (
                select(Role.name)
                .join(MemberRole, MemberRole.role_id == Role.id)
                .where(MemberRole.member_id == member_id)
            )
            result = await session.execute(stmt)
            return list(result.scalars().all())

    async def get_member_role_display(self, member_id: str) -> list[str]:
        """获取成员的所有角色显示名"""
        async with self._session_factory() as session:
            stmt = (
                select(Role.display_name)
                .join(MemberRole, MemberRole.role_id == Role.id)
                .where(MemberRole.member_id == member_id)
            )
            result = await session.execute(stmt)
            return list(result.scalars().all())

    # ---- 角色管理 ----

    async def assign_role(self, member_id: str, role_name: str, exclusive: bool = True) -> bool:
        """给成员分配角色（幂等）

        Args:
            member_id: 成员ID
            role_name: 角色名
            exclusive: 是否独占模式（默认True，表示分配新角色前先移除其他所有角色）
        """
        async with self._session_factory() as session:
            role = await self._get_role_by_name(session, role_name)
            if not role:
                log.warning(f"角色 '{role_name}' 不存在")
                return False

            if exclusive:
                existing_stmt = select(MemberRole).where(MemberRole.member_id == member_id)
                existing_result = await session.execute(existing_stmt)
                existing_roles = existing_result.scalars().all()

                has_target = any(mr.role_id == role.id for mr in existing_roles)
                if has_target and len(existing_roles) == 1:
                    return True

                for mr in existing_roles:
                    if mr.role_id != role.id:
                        await session.delete(mr)

                if has_target:
                    await session.commit()
                    self._invalidate(member_id)
                    return True

                await session.flush()
            else:
                stmt = select(MemberRole).where(
                    MemberRole.member_id == member_id,
                    MemberRole.role_id == role.id,
                )
                result = await session.execute(stmt)
                if result.scalar_one_or_none():
                    return True

            try:
                session.add(MemberRole(member_id=member_id, role_id=role.id))
                await session.commit()
            except Exception:
                await session.rollback()
                await self._fix_sequence(session, "member_roles")
                session.add(MemberRole(member_id=member_id, role_id=role.id))
                await session.commit()

        self._invalidate(member_id)
        log.info(f"已分配角色: member={member_id[:8]} role={role_name}")
        return True

    async def remove_role(self, member_id: str, role_name: str) -> bool:
        """移除成员角色"""
        async with self._session_factory() as session:
            role = await self._get_role_by_name(session, role_name)
            if not role:
                return False

            stmt = select(MemberRole).where(
                MemberRole.member_id == member_id,
                MemberRole.role_id == role.id,
            )
            result = await session.execute(stmt)
            mr = result.scalar_one_or_none()
            if mr:
                await session.delete(mr)
                await session.commit()

        self._invalidate(member_id)
        return True

    # ---- 角色 CRUD ----

    async def list_all_roles(self) -> list[dict]:
        """列出所有角色（含权限和成员数）"""
        from sqlalchemy import func as sa_func
        async with self._session_factory() as session:
            result = await session.execute(select(Role).order_by(Role.id))
            roles = result.scalars().all()

            items = []
            for r in roles:
                perm_stmt = (
                    select(Permission.code, Permission.display_name)
                    .join(RolePermission, RolePermission.permission_id == Permission.id)
                    .where(RolePermission.role_id == r.id)
                )
                perm_result = await session.execute(perm_stmt)
                perms = [{"code": row[0], "display_name": row[1]} for row in perm_result.all()]

                from sqlalchemy import func as sa_func
                count_stmt = select(sa_func.count()).where(MemberRole.role_id == r.id)
                member_count = (await session.execute(count_stmt)).scalar() or 0

                is_admin = r.name == "admin"
                items.append({
                    "id": r.id,
                    "name": r.name,
                    "display_name": r.display_name,
                    "source": r.source,
                    "is_builtin": r.is_builtin,
                    "is_admin": is_admin,
                    "permissions": [{"code": "*", "display_name": "全部权限"}] if is_admin else perms,
                    "member_count": member_count,
                })
            return items

    async def list_all_permissions(self) -> list[dict]:
        """列出所有已注册权限"""
        async with self._session_factory() as session:
            result = await session.execute(select(Permission).order_by(Permission.source, Permission.code))
            perms = result.scalars().all()
            return [
                {"id": p.id, "code": p.code, "display_name": p.display_name, "source": p.source}
                for p in perms
            ]

    async def create_role(self, name: str, display_name: str, permission_codes: list[str]) -> dict | None:
        """创建自定义角色并绑定权限，返回角色信息；name 重复返回 None"""
        async with self._session_factory() as session:
            existing = await session.execute(select(Role).where(Role.name == name))
            if existing.scalar_one_or_none():
                return None

            role = Role(name=name, display_name=display_name, source="custom", is_builtin=False)
            session.add(role)
            await session.flush()

            for code in permission_codes:
                await self._ensure_role_permission(session, role.id, code)

            await session.commit()
            log.info(f"已创建角色: {name}")
            return {"id": role.id, "name": role.name, "display_name": role.display_name}

    async def update_role(self, role_id: int, display_name: str | None, permission_codes: list[str] | None) -> bool:
        """更新自定义角色（内置角色不可修改权限）"""
        async with self._session_factory() as session:
            result = await session.execute(select(Role).where(Role.id == role_id))
            role = result.scalar_one_or_none()
            if not role:
                return False

            if display_name is not None:
                role.display_name = display_name

            # 内置角色只能改 display_name，不能改权限
            if permission_codes is not None and not role.is_builtin:
                # 删除旧权限绑定
                old_rps = await session.execute(
                    select(RolePermission).where(RolePermission.role_id == role.id)
                )
                for rp in old_rps.scalars().all():
                    await session.delete(rp)
                await session.flush()

                # 绑定新权限
                for code in permission_codes:
                    await self._ensure_role_permission(session, role.id, code)

            await session.commit()

        self._cache.clear()
        log.info(f"已更新角色: id={role_id}")
        return True

    async def delete_role(self, role_id: int) -> bool:
        """删除自定义角色（内置角色不可删除）"""
        async with self._session_factory() as session:
            result = await session.execute(select(Role).where(Role.id == role_id))
            role = result.scalar_one_or_none()
            if not role or role.is_builtin:
                return False

            # 删除角色-权限绑定
            rp_stmt = select(RolePermission).where(RolePermission.role_id == role.id)
            for rp in (await session.execute(rp_stmt)).scalars().all():
                await session.delete(rp)

            # 删除成员-角色绑定
            mr_stmt = select(MemberRole).where(MemberRole.role_id == role.id)
            for mr in (await session.execute(mr_stmt)).scalars().all():
                await session.delete(mr)

            await session.delete(role)
            await session.commit()

        self._cache.clear()
        log.info(f"已删除角色: id={role_id}")
        return True

    # ---- 插件权限/角色注册 ----

    async def register_permission(self, code: str, display_name: str, source: str = "core") -> None:
        """注册权限（幂等）"""
        async with self._session_factory() as session:
            await self._ensure_permission(session, code, display_name, source)
            await session.commit()

    async def register_role(
        self, name: str, display_name: str, permissions: list[str], source: str = "core",
    ) -> None:
        """注册角色并绑定权限（幂等）"""
        async with self._session_factory() as session:
            role = await self._ensure_role(session, name, display_name, source, False)
            for perm_code in permissions:
                await self._ensure_role_permission(session, role.id, perm_code)
            await session.commit()

    # ---- 内部方法 ----

    async def _ensure_permission(self, session, code: str, display_name: str, source: str) -> Permission:
        result = await session.execute(select(Permission).where(Permission.code == code))
        perm = result.scalar_one_or_none()
        if not perm:
            perm = Permission(code=code, display_name=display_name, source=source)
            session.add(perm)
            await session.flush()
        return perm

    async def _ensure_role(self, session, name: str, display_name: str, source: str, is_builtin: bool) -> Role:
        result = await session.execute(select(Role).where(Role.name == name))
        role = result.scalar_one_or_none()
        if not role:
            role = Role(name=name, display_name=display_name, source=source, is_builtin=is_builtin)
            session.add(role)
            await session.flush()
        return role

    async def _ensure_role_permission(self, session, role_id: int, perm_code: str) -> None:
        perm_result = await session.execute(select(Permission).where(Permission.code == perm_code))
        perm = perm_result.scalar_one_or_none()
        if not perm:
            return
        existing = await session.execute(
            select(RolePermission).where(
                RolePermission.role_id == role_id,
                RolePermission.permission_id == perm.id,
            )
        )
        if not existing.scalar_one_or_none():
            session.add(RolePermission(role_id=role_id, permission_id=perm.id))

    async def _get_role_by_name(self, session, name: str) -> Role | None:
        result = await session.execute(select(Role).where(Role.name == name))
        return result.scalar_one_or_none()

    async def _fix_sequence(self, session, table_name: str) -> None:
        """Reset PostgreSQL sequence to max(id)+1 to fix out-of-sync auto-increment."""
        seq_name = f"{table_name}_id_seq"
        try:
            await session.execute(text(
                f"SELECT setval('{seq_name}', COALESCE((SELECT MAX(id) FROM {table_name}), 0) + 1, false)"
            ))
            await session.commit()
            log.info(f"已修复序列 {seq_name}")
        except Exception as e:
            log.warning(f"修复序列 {seq_name} 失败: {e}")

    # ---- 缓存 ----

    def _put_cache(self, member_id: str, perms: set[str]) -> None:
        if len(self._cache) >= self._max_cache:
            self._cache.clear()
        self._cache[member_id] = perms

    def _invalidate(self, member_id: str) -> None:
        self._cache.pop(member_id, None)

    def clear_cache(self) -> None:
        self._cache.clear()
