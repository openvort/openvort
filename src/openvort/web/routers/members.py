"""成员管理路由"""

import json
from fastapi import APIRouter
from pydantic import BaseModel
from sqlalchemy import select, func as sa_func

from openvort.web.deps import get_db_session_factory, get_auth_service

router = APIRouter()


# ---- 请求模型 ----

class CreateMemberRequest(BaseModel):
    name: str
    email: str = ""
    phone: str = ""
    position: str = ""
    is_account: bool = False
    is_virtual: bool = False
    virtual_role: str = ""
    skills: list[str] = []
    auto_report: bool = False
    report_frequency: str = "daily"


class UpdateMemberRequest(BaseModel):
    name: str | None = None
    email: str | None = None
    phone: str | None = None
    position: str | None = None
    status: str | None = None
    is_account: bool | None = None
    is_virtual: bool | None = None
    virtual_role: str | None = None
    skills: list[str] | None = None
    auto_report: bool | None = None
    report_frequency: str | None = None


class ResetPasswordRequest(BaseModel):
    password: str | None = None  # 为空则重置为 default_password


class AssignRoleRequest(BaseModel):
    role: str


class BatchIdsRequest(BaseModel):
    ids: list[str]


class BatchRoleRequest(BaseModel):
    ids: list[str]
    role: str


class BatchDeptRequest(BaseModel):
    ids: list[str]
    dept_id: int


class CreateRoleRequest(BaseModel):
    name: str
    display_name: str
    permissions: list[str] = []  # permission codes


class UpdateRoleRequest(BaseModel):
    display_name: str | None = None
    permissions: list[str] | None = None  # permission codes


# ---- 角色/权限列表（静态路由，必须在 /{member_id} 之前） ----

@router.get("/roles/list")
async def list_roles():
    """角色列表（含权限和成员数）"""
    auth_service = get_auth_service()
    items = await auth_service.list_all_roles()
    return {"roles": items}


@router.get("/permissions/list")
async def list_permissions():
    """所有已注册权限列表"""
    auth_service = get_auth_service()
    perms = await auth_service.list_all_permissions()
    return {"permissions": perms}


@router.post("/roles")
async def create_role(req: CreateRoleRequest):
    """创建自定义角色"""
    auth_service = get_auth_service()
    result = await auth_service.create_role(req.name, req.display_name, req.permissions)
    if result is None:
        return {"success": False, "error": "角色名已存在"}
    return {"success": True, "role": result}


@router.put("/roles/{role_id}")
async def update_role(role_id: int, req: UpdateRoleRequest):
    """更新角色（内置角色仅可改显示名，不可改权限）"""
    auth_service = get_auth_service()
    ok = await auth_service.update_role(role_id, req.display_name, req.permissions)
    if not ok:
        return {"success": False, "error": "角色不存在"}
    return {"success": True}


@router.delete("/roles/{role_id}")
async def delete_role(role_id: int):
    """删除自定义角色（内置角色不可删除）"""
    auth_service = get_auth_service()
    ok = await auth_service.delete_role(role_id)
    if not ok:
        return {"success": False, "error": "角色不存在或为内置角色，无法删除"}
    return {"success": True}


# ---- 成员管理 ----

@router.post("")
async def create_member(req: CreateMemberRequest):
    """手动新增成员"""
    import json as _json
    from pathlib import Path
    from openvort.contacts.models import Member
    from openvort.skill.loader import _parse_skill_file, DEFAULT_ROLE_SKILLS
    from openvort.db.models import MemberSkill, Skill
    from openvort.web.deps import get_skill_loader

    session_factory = get_db_session_factory()

    # 获取虚拟员工的 persona
    virtual_system_prompt = ""
    if req.is_virtual and req.virtual_role:
        builtin_dir = Path(__file__).parent.parent.parent / "skills"
        skill_file = builtin_dir / req.virtual_role / "SKILL.md"
        if skill_file.exists():
            parsed = _parse_skill_file(skill_file)
            if parsed:
                virtual_system_prompt = parsed.get("content", "")

    async with session_factory() as session:
        member = Member(
            name=req.name,
            email=req.email,
            phone=req.phone,
            position=req.position,
            is_account=req.is_account,
            is_virtual=req.is_virtual,
            virtual_role=req.virtual_role,
            virtual_system_prompt=virtual_system_prompt,
            skills=_json.dumps(req.skills) if req.skills else "[]",
            auto_report=req.auto_report,
            report_frequency=req.report_frequency,
        )
        session.add(member)
        await session.commit()
        await session.refresh(member)

        # 如果是虚拟员工且有角色，添加角色推荐的技能
        if req.is_virtual and req.virtual_role:
            loader = get_skill_loader()
            if loader:
                role_skills = await loader.get_role_skills(req.virtual_role)
                for skill in role_skills:
                    # 检查是否已存在
                    result = await session.execute(
                        select(MemberSkill).where(
                            MemberSkill.member_id == member.id,
                            MemberSkill.skill_id == skill["id"],
                        )
                    )
                    if not result.scalar_one_or_none():
                        member_skill = MemberSkill(
                            member_id=member.id,
                            skill_id=skill["id"],
                            source=f"role:{req.virtual_role}",
                            enabled=True,
                        )
                        session.add(member_skill)
                await session.commit()

        return {"success": True, "id": member.id}


@router.get("")
async def list_members(search: str = "", role: str = "", department_id: int | None = None, page: int = 1, size: int = 50):
    """成员列表（支持搜索、角色筛选、部门筛选、分页）"""
    from openvort.contacts.models import Member, PlatformIdentity, MemberDepartment
    from openvort.auth.models import MemberRole, Role

    session_factory = get_db_session_factory()
    auth_service = get_auth_service()

    async with session_factory() as session:
        # 基础查询
        stmt = select(Member).order_by(Member.name)

        # 搜索过滤
        if search:
            pattern = f"%{search}%"
            stmt = stmt.where(
                (Member.name.ilike(pattern)) |
                (Member.email.ilike(pattern)) |
                (Member.phone.ilike(pattern))
            )

        # 角色筛选
        if role:
            stmt = stmt.join(MemberRole, MemberRole.member_id == Member.id)
            stmt = stmt.join(Role, Role.id == MemberRole.role_id)
            stmt = stmt.where(Role.name == role)

        # 部门筛选
        if department_id is not None:
            stmt = stmt.join(MemberDepartment, MemberDepartment.member_id == Member.id)
            stmt = stmt.where(MemberDepartment.department_id == department_id)

        # 总数
        count_stmt = select(sa_func.count()).select_from(stmt.subquery())
        total = (await session.execute(count_stmt)).scalar() or 0

        # 分页
        offset = (page - 1) * size
        stmt = stmt.offset(offset).limit(size)
        result = await session.execute(stmt)
        members = result.scalars().all()

        # 组装返回数据
        items = []
        for m in members:
            # 查角色
            roles = await auth_service.get_member_roles(m.id)
            # 查平台身份
            id_stmt = select(PlatformIdentity).where(PlatformIdentity.member_id == m.id)
            id_result = await session.execute(id_stmt)
            identities = id_result.scalars().all()
            platform_accounts = {i.platform: i.platform_user_id for i in identities}

            # 查部门
            from openvort.contacts.models import MemberDepartment, Department
            dept_stmt = (
                select(Department.name)
                .join(MemberDepartment, MemberDepartment.department_id == Department.id)
                .where(MemberDepartment.member_id == m.id)
                .order_by(MemberDepartment.is_primary.desc())
            )
            dept_result = await session.execute(dept_stmt)
            departments = [row[0] for row in dept_result.all()]

            items.append({
                "id": m.id,
                "name": m.name,
                "email": m.email or "",
                "phone": m.phone or "",
                "position": m.position or "",
                "avatar_url": m.avatar_url or "",
                "status": m.status,
                "is_account": m.is_account,
                "has_password": bool(m.password_hash),
                "roles": roles or [],
                "platform_accounts": platform_accounts,
                "departments": departments,
                "created_at": m.created_at.isoformat() if m.created_at else "",
            })

        return {"members": items, "total": total, "page": page, "size": size}


@router.get("/{member_id}")
async def get_member(member_id: str):
    """成员详情（含角色、权限、平台身份）"""
    from openvort.contacts.models import Member, PlatformIdentity

    session_factory = get_db_session_factory()
    auth_service = get_auth_service()

    async with session_factory() as session:
        stmt = select(Member).where(Member.id == member_id)
        result = await session.execute(stmt)
        member = result.scalar_one_or_none()
        if not member:
            return {"error": "成员不存在"}, 404

        roles = await auth_service.get_member_roles(member.id)
        permissions = list(await auth_service.get_member_permissions(member.id))

        id_stmt = select(PlatformIdentity).where(PlatformIdentity.member_id == member.id)
        id_result = await session.execute(id_stmt)
        identities = id_result.scalars().all()

        # 查部门
        from openvort.contacts.models import MemberDepartment, Department
        dept_stmt = (
            select(Department.id, Department.name)
            .join(MemberDepartment, MemberDepartment.department_id == Department.id)
            .where(MemberDepartment.member_id == member.id)
            .order_by(MemberDepartment.is_primary.desc())
        )
        dept_result = await session.execute(dept_stmt)
        departments = [{"id": row[0], "name": row[1]} for row in dept_result.all()]

        return {
            "id": member.id,
            "name": member.name,
            "email": member.email or "",
            "phone": member.phone or "",
            "position": member.position or "",
            "avatar_url": member.avatar_url or "",
            "status": member.status,
            "is_account": member.is_account,
            "has_password": bool(member.password_hash),
            "roles": roles or [],
            "permissions": permissions,
            "departments": departments,
            "identities": [
                {
                    "id": i.id,
                    "platform": i.platform,
                    "platform_user_id": i.platform_user_id,
                    "platform_username": i.platform_username,
                    "platform_display_name": i.platform_display_name,
                    "platform_email": i.platform_email,
                    "platform_position": i.platform_position,
                    "platform_department": i.platform_department,
                }
                for i in identities
            ],
            "created_at": member.created_at.isoformat() if member.created_at else "",
        }


@router.put("/{member_id}")
async def update_member(member_id: str, req: UpdateMemberRequest):
    """编辑成员基本信息"""
    import json as _json
    from pathlib import Path
    from openvort.contacts.models import Member
    from openvort.skill.loader import _parse_skill_file

    session_factory = get_db_session_factory()

    async with session_factory() as session:
        stmt = select(Member).where(Member.id == member_id)
        result = await session.execute(stmt)
        member = result.scalar_one_or_none()
        if not member:
            return {"success": False, "error": "成员不存在"}

        if req.name is not None:
            member.name = req.name
        if req.email is not None:
            member.email = req.email
        if req.phone is not None:
            member.phone = req.phone
        if req.position is not None:
            member.position = req.position
        if req.status is not None:
            member.status = req.status
        if req.is_account is not None:
            member.is_account = req.is_account
        if req.is_virtual is not None:
            member.is_virtual = req.is_virtual
        if req.virtual_role is not None:
            member.virtual_role = req.virtual_role
            # 重新加载角色模板
            if req.virtual_role:
                builtin_dir = Path(__file__).parent.parent.parent / "skills"
                skill_file = builtin_dir / req.virtual_role / "SKILL.md"
                if skill_file.exists():
                    parsed = _parse_skill_file(skill_file)
                    if parsed:
                        member.virtual_system_prompt = parsed.get("content", "")
        if req.skills is not None:
            member.skills = _json.dumps(req.skills)
        if req.auto_report is not None:
            member.auto_report = req.auto_report
        if req.report_frequency is not None:
            member.report_frequency = req.report_frequency

        await session.commit()
        return {"success": True}


@router.post("/{member_id}/reset-password")
async def reset_password(member_id: str, req: ResetPasswordRequest):
    """重置密码（传 password 则设为新密码，不传则清空回退到 default_password）"""
    from openvort.contacts.models import Member
    from openvort.web.auth import hash_password

    session_factory = get_db_session_factory()

    async with session_factory() as session:
        stmt = select(Member).where(Member.id == member_id)
        result = await session.execute(stmt)
        member = result.scalar_one_or_none()
        if not member:
            return {"success": False, "error": "成员不存在"}

        if req.password:
            member.password_hash = hash_password(req.password)
        else:
            member.password_hash = ""

        await session.commit()
        return {"success": True}


@router.post("/{member_id}/toggle-account")
async def toggle_account(member_id: str):
    """启用/禁用登录"""
    from openvort.contacts.models import Member

    session_factory = get_db_session_factory()

    async with session_factory() as session:
        stmt = select(Member).where(Member.id == member_id)
        result = await session.execute(stmt)
        member = result.scalar_one_or_none()
        if not member:
            return {"success": False, "error": "成员不存在"}

        member.is_account = not member.is_account
        await session.commit()
        return {"success": True, "is_account": member.is_account}


@router.delete("/{member_id}")
async def delete_member(member_id: str):
    """删除成员（同时删除关联的平台身份、角色绑定、匹配建议）"""
    from openvort.contacts.models import Member, PlatformIdentity, MatchSuggestion
    from openvort.auth.models import MemberRole

    session_factory = get_db_session_factory()
    auth_service = get_auth_service()

    async with session_factory() as session:
        stmt = select(Member).where(Member.id == member_id)
        result = await session.execute(stmt)
        member = result.scalar_one_or_none()
        if not member:
            return {"success": False, "error": "成员不存在"}

        # 删除角色绑定
        role_stmt = select(MemberRole).where(MemberRole.member_id == member_id)
        role_result = await session.execute(role_stmt)
        for mr in role_result.scalars().all():
            await session.delete(mr)

        # 删除匹配建议
        match_stmt = select(MatchSuggestion).where(MatchSuggestion.target_member_id == member_id)
        match_result = await session.execute(match_stmt)
        for ms in match_result.scalars().all():
            await session.delete(ms)

        # 删除成员（cascade 会删除 platform_identities）
        await session.delete(member)
        await session.commit()

    auth_service.clear_cache()
    return {"success": True}


# ---- 批量操作 ----

@router.post("/batch/delete")
async def batch_delete(req: BatchIdsRequest):
    """批量删除成员"""
    from openvort.contacts.models import Member, MatchSuggestion
    from openvort.auth.models import MemberRole

    session_factory = get_db_session_factory()
    auth_service = get_auth_service()
    deleted = 0

    async with session_factory() as session:
        for mid in req.ids:
            stmt = select(Member).where(Member.id == mid)
            result = await session.execute(stmt)
            member = result.scalar_one_or_none()
            if not member:
                continue

            # 删除角色绑定
            role_stmt = select(MemberRole).where(MemberRole.member_id == mid)
            for mr in (await session.execute(role_stmt)).scalars().all():
                await session.delete(mr)

            # 删除匹配建议
            match_stmt = select(MatchSuggestion).where(MatchSuggestion.target_member_id == mid)
            for ms in (await session.execute(match_stmt)).scalars().all():
                await session.delete(ms)

            await session.delete(member)
            deleted += 1

        await session.commit()

    auth_service.clear_cache()
    return {"success": True, "deleted": deleted}


@router.post("/batch/enable-account")
async def batch_enable_account(req: BatchIdsRequest):
    """批量启用登录"""
    from openvort.contacts.models import Member

    session_factory = get_db_session_factory()
    count = 0

    async with session_factory() as session:
        for mid in req.ids:
            stmt = select(Member).where(Member.id == mid)
            member = (await session.execute(stmt)).scalar_one_or_none()
            if member and not member.is_account:
                member.is_account = True
                count += 1
        await session.commit()

    return {"success": True, "count": count}


@router.post("/batch/disable-account")
async def batch_disable_account(req: BatchIdsRequest):
    """批量禁用登录"""
    from openvort.contacts.models import Member

    session_factory = get_db_session_factory()
    count = 0

    async with session_factory() as session:
        for mid in req.ids:
            stmt = select(Member).where(Member.id == mid)
            member = (await session.execute(stmt)).scalar_one_or_none()
            if member and member.is_account:
                member.is_account = False
                count += 1
        await session.commit()

    return {"success": True, "count": count}


@router.post("/batch/assign-role")
async def batch_assign_role(req: BatchRoleRequest):
    """批量分配角色"""
    auth_service = get_auth_service()
    count = 0
    for mid in req.ids:
        ok = await auth_service.assign_role(mid, req.role)
        if ok:
            count += 1
    auth_service.clear_cache()
    return {"success": True, "count": count}


@router.post("/batch/remove-role")
async def batch_remove_role(req: BatchRoleRequest):
    """批量移除角色"""
    auth_service = get_auth_service()
    count = 0
    for mid in req.ids:
        ok = await auth_service.remove_role(mid, req.role)
        if ok:
            count += 1
    auth_service.clear_cache()
    return {"success": True, "count": count}


@router.post("/batch/assign-dept")
async def batch_assign_dept(req: BatchDeptRequest):
    """批量分配部门"""
    from openvort.contacts.service import ContactService
    session_factory = get_db_session_factory()
    service = ContactService(session_factory)
    count = 0
    for mid in req.ids:
        ok = await service.add_member_to_department(req.dept_id, mid)
        if ok:
            count += 1
    return {"success": True, "count": count}


@router.post("/batch/remove-dept")
async def batch_remove_dept(req: BatchDeptRequest):
    """批量移除部门"""
    from openvort.contacts.service import ContactService
    session_factory = get_db_session_factory()
    service = ContactService(session_factory)
    count = 0
    for mid in req.ids:
        ok = await service.remove_member_from_department(req.dept_id, mid)
        if ok:
            count += 1
    return {"success": True, "count": count}


# ---- 角色管理 ----

@router.post("/{member_id}/roles")
async def assign_role(member_id: str, req: AssignRoleRequest):
    """给成员分配角色"""
    auth_service = get_auth_service()
    ok = await auth_service.assign_role(member_id, req.role)
    if ok:
        auth_service.clear_cache()
    return {"success": ok}


@router.delete("/{member_id}/roles/{role_name}")
async def remove_role(member_id: str, role_name: str):
    """移除成员角色"""
    auth_service = get_auth_service()
    ok = await auth_service.remove_role(member_id, role_name)
    if ok:
        auth_service.clear_cache()
    return {"success": ok}


# ---- 角色技能映射 API ----

@router.get("/roles/skills")
async def get_role_skills(role: str = ""):
    """获取角色对应的推荐技能（可选按角色筛选）"""
    from openvort.web.deps import get_skill_loader

    loader = get_skill_loader()
    if not loader:
        return {"skills": []}

    if role:
        skills = await loader.get_role_skills(role)
        return {"skills": skills}

    # 返回所有角色的推荐技能
    from openvort.skill.loader import DEFAULT_ROLE_SKILLS
    all_role_skills = {}
    for r in DEFAULT_ROLE_SKILLS.keys():
        all_role_skills[r] = await loader.get_role_skills(r)
    return {"roles": all_role_skills}


class AddRoleSkillRequest(BaseModel):
    role: str
    skill_id: str
    priority: int = 0


class RemoveRoleSkillRequest(BaseModel):
    role: str
    skill_id: str


@router.post("/roles/skills")
async def add_role_skill(req: AddRoleSkillRequest):
    """为角色添加推荐技能"""
    from openvort.db.models import RoleSkill, Skill

    session_factory = get_db_session_factory()
    async with session_factory() as db:
        skill = await db.get(Skill, req.skill_id)
        if not skill:
            return {"success": False, "error": "技能不存在"}

        existing = await db.execute(
            select(RoleSkill).where(RoleSkill.role == req.role, RoleSkill.skill_id == req.skill_id)
        )
        if existing.scalar_one_or_none():
            return {"success": False, "error": "该映射已存在"}

        db.add(RoleSkill(role=req.role, skill_id=req.skill_id, priority=req.priority))
        await db.commit()

    return {"success": True}


@router.delete("/roles/skills")
async def remove_role_skill(req: RemoveRoleSkillRequest):
    """移除角色的推荐技能"""
    from openvort.db.models import RoleSkill

    session_factory = get_db_session_factory()
    async with session_factory() as db:
        result = await db.execute(
            select(RoleSkill).where(RoleSkill.role == req.role, RoleSkill.skill_id == req.skill_id)
        )
        row = result.scalar_one_or_none()
        if row:
            await db.delete(row)
            await db.commit()

    return {"success": True}


# ---- 成员技能 API ----

class AddMemberSkillRequest(BaseModel):
    skill_id: str
    source: str = "public"  # role:developer / personal / public


class UpdateMemberSkillRequest(BaseModel):
    enabled: bool | None = None
    custom_content: str | None = None


@router.get("/{member_id}/skills")
async def get_member_skills(member_id: str):
    """获取成员技能列表（含来源信息）"""
    from openvort.web.deps import get_skill_loader

    loader = get_skill_loader()
    if not loader:
        return {"skills": []}

    skills = await loader.get_member_skills_with_source(member_id)
    return {"skills": skills}


@router.post("/{member_id}/skills")
async def add_member_skill(member_id: str, req: AddMemberSkillRequest):
    """为成员添加技能订阅"""
    from openvort.db.models import MemberSkill, Skill
    from openvort.web.deps import get_db_session_factory

    session_factory = get_db_session_factory()
    async with session_factory() as db:
        # 检查技能是否存在
        result = await db.execute(select(Skill).where(Skill.id == req.skill_id))
        skill = result.scalar_one_or_none()
        if not skill:
            return {"success": False, "error": "技能不存在"}

        # 检查是否已存在
        result = await db.execute(
            select(MemberSkill).where(
                MemberSkill.member_id == member_id,
                MemberSkill.skill_id == req.skill_id,
            )
        )
        existing = result.scalar_one_or_none()
        if existing:
            return {"success": False, "error": "该技能已订阅"}

        # 创建订阅
        member_skill = MemberSkill(
            member_id=member_id,
            skill_id=req.skill_id,
            source=req.source,
            enabled=True,
        )
        db.add(member_skill)
        await db.commit()

    return {"success": True}


@router.put("/{member_id}/skills/{skill_id}")
async def update_member_skill(member_id: str, skill_id: str, req: UpdateMemberSkillRequest):
    """更新成员技能（启用/禁用/自定义内容）"""
    from openvort.db.models import MemberSkill
    from openvort.web.deps import get_db_session_factory

    session_factory = get_db_session_factory()
    async with session_factory() as db:
        result = await db.execute(
            select(MemberSkill).where(
                MemberSkill.member_id == member_id,
                MemberSkill.skill_id == skill_id,
            )
        )
        member_skill = result.scalar_one_or_none()
        if not member_skill:
            return {"success": False, "error": "订阅不存在"}

        if req.enabled is not None:
            member_skill.enabled = req.enabled
        if req.custom_content is not None:
            member_skill.custom_content = req.custom_content

        await db.commit()

    return {"success": True}


@router.delete("/{member_id}/skills/{skill_id}")
async def remove_member_skill(member_id: str, skill_id: str):
    """取消成员技能订阅"""
    from openvort.db.models import MemberSkill
    from openvort.web.deps import get_db_session_factory

    session_factory = get_db_session_factory()
    async with session_factory() as db:
        result = await db.execute(
            select(MemberSkill).where(
                MemberSkill.member_id == member_id,
                MemberSkill.skill_id == skill_id,
            )
        )
        member_skill = result.scalar_one_or_none()
        if member_skill:
            await db.delete(member_skill)
            await db.commit()

    return {"success": True}
