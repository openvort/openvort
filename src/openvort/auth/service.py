"""
权限服务

鉴权、角色管理、权限注册、内置种子数据初始化。
"""

from sqlalchemy import select

from openvort.auth.models import MemberRole, Permission, Role, RolePermission
from openvort.utils.logging import get_logger

log = get_logger("auth.service")

# 内置角色定义
BUILTIN_ROLES = [
    {"name": "admin", "display_name": "管理员", "permissions": ["*"]},
    {"name": "manager", "display_name": "部门管理者", "permissions": [
        "contacts.sync", "contacts.search", "contacts.match",
    ]},
    {"name": "member", "display_name": "普通成员", "permissions": [
        "contacts.search",
    ]},
    {"name": "guest", "display_name": "访客", "permissions": []},
]

# 内置权限定义
BUILTIN_PERMISSIONS = [
    {"code": "contacts.sync", "display_name": "同步通讯录"},
    {"code": "contacts.search", "display_name": "搜索成员"},
    {"code": "contacts.match", "display_name": "管理匹配建议"},
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

    async def assign_role(self, member_id: str, role_name: str) -> bool:
        """给成员分配角色（幂等）"""
        async with self._session_factory() as session:
            role = await self._get_role_by_name(session, role_name)
            if not role:
                log.warning(f"角色 '{role_name}' 不存在")
                return False

            # 检查是否已绑定
            stmt = select(MemberRole).where(
                MemberRole.member_id == member_id,
                MemberRole.role_id == role.id,
            )
            result = await session.execute(stmt)
            if result.scalar_one_or_none():
                return True  # 已有

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

    # ---- 缓存 ----

    def _put_cache(self, member_id: str, perms: set[str]) -> None:
        if len(self._cache) >= self._max_cache:
            self._cache.clear()
        self._cache[member_id] = perms

    def _invalidate(self, member_id: str) -> None:
        self._cache.pop(member_id, None)

    def clear_cache(self) -> None:
        self._cache.clear()
