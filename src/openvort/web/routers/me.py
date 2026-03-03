"""个人信息路由 — 所有登录用户可访问"""

import json
import uuid
from pathlib import Path

from fastapi import APIRouter, HTTPException, Request, UploadFile, File
from pydantic import BaseModel

from openvort.web.app import require_auth
from openvort.web.deps import get_db_session_factory, get_auth_service

router = APIRouter()

UPLOAD_DIR = Path(__file__).parent.parent.parent.parent / "web" / "dist" / "uploads" / "avatars"


# ---- 辅助 ----

def _get_member_id(request: Request) -> str:
    payload = require_auth(request)
    return payload.get("sub", "")


async def _load_member_full(member_id: str) -> dict | None:
    """加载成员完整信息（含平台账号、角色、部门名称）"""
    from sqlalchemy import select
    from openvort.contacts.models import Member, PlatformIdentity, MemberDepartment, Department

    session_factory = get_db_session_factory()
    auth_service = get_auth_service()

    async with session_factory() as session:
        stmt = select(Member).where(Member.id == member_id)
        result = await session.execute(stmt)
        member = result.scalar_one_or_none()
        if not member:
            return None

        roles = await auth_service.get_member_roles(member.id)
        if not roles:
            roles = ["member"]

        stmt = select(PlatformIdentity).where(PlatformIdentity.member_id == member.id)
        result = await session.execute(stmt)
        identities = result.scalars().all()

        platform_accounts = {}
        platform_position = ""
        for ident in identities:
            platform_accounts[ident.platform] = ident.platform_user_id
            if ident.platform_position and not platform_position:
                platform_position = ident.platform_position
        position = member.position or platform_position

        # 从 MemberDepartment 关联查真实部门名称
        dept_stmt = (
            select(Department.name)
            .join(MemberDepartment, MemberDepartment.department_id == Department.id)
            .where(MemberDepartment.member_id == member.id)
            .order_by(MemberDepartment.is_primary.desc())
        )
        dept_result = await session.execute(dept_stmt)
        dept_names = [row[0] for row in dept_result.all()]
        department = " / ".join(dept_names) if dept_names else ""

    return {
        "member_id": member.id,
        "name": member.name,
        "email": member.email or "",
        "phone": member.phone or "",
        "avatar_url": member.avatar_url or "",
        "bio": member.bio if hasattr(member, "bio") else "",
        "roles": roles,
        "position": position,
        "department": department,
        "platform_accounts": platform_accounts,
    }


# ---- 个人资料 ----

@router.get("/profile")
async def get_profile(request: Request):
    """获取当前用户完整信息"""
    member_id = _get_member_id(request)
    data = await _load_member_full(member_id)
    if not data:
        raise HTTPException(status_code=404, detail="用户不存在")
    return data


class UpdateProfileRequest(BaseModel):
    name: str | None = None
    email: str | None = None
    phone: str | None = None
    position: str | None = None
    department: str | None = None
    bio: str | None = None


@router.put("/profile")
async def update_profile(request: Request, req: UpdateProfileRequest):
    """更新个人基本信息"""
    member_id = _get_member_id(request)

    from sqlalchemy import select
    from openvort.contacts.models import Member

    session_factory = get_db_session_factory()
    async with session_factory() as session:
        stmt = select(Member).where(Member.id == member_id)
        result = await session.execute(stmt)
        member = result.scalar_one_or_none()
        if not member:
            raise HTTPException(status_code=404, detail="用户不存在")

        if req.name is not None:
            member.name = req.name.strip()
        if req.email is not None:
            member.email = req.email.strip()
        if req.phone is not None:
            member.phone = req.phone.strip()
        if req.position is not None:
            member.position = req.position.strip()
        if req.bio is not None and hasattr(member, "bio"):
            member.bio = req.bio.strip()
        await session.commit()

    return {"success": True}


class ChangePasswordRequest(BaseModel):
    old_password: str
    new_password: str


@router.put("/password")
async def change_password(request: Request, req: ChangePasswordRequest):
    """修改密码"""
    member_id = _get_member_id(request)

    if len(req.new_password) < 6:
        raise HTTPException(status_code=400, detail="新密码长度不能少于 6 位")

    from sqlalchemy import select
    from openvort.contacts.models import Member
    from openvort.web.auth import hash_password, verify_password
    from openvort.config.settings import get_settings

    settings = get_settings()
    session_factory = get_db_session_factory()

    async with session_factory() as session:
        stmt = select(Member).where(Member.id == member_id)
        result = await session.execute(stmt)
        member = result.scalar_one_or_none()
        if not member:
            raise HTTPException(status_code=404, detail="用户不存在")

        # 验证旧密码
        if member.password_hash:
            if not verify_password(req.old_password, member.password_hash):
                raise HTTPException(status_code=400, detail="原密码错误")
        else:
            # 没有独立密码时，用 default_password 验证
            if req.old_password != settings.web.default_password:
                raise HTTPException(status_code=400, detail="原密码错误")

        member.password_hash = hash_password(req.new_password)
        await session.commit()

    return {"success": True}


# ---- 通知偏好 ----

class NotificationPreferences(BaseModel):
    preferences: dict  # { "system": {"web": true, "wecom": false}, ... }


@router.get("/notifications")
async def get_notification_prefs(request: Request):
    """获取通知偏好设置"""
    member_id = _get_member_id(request)

    from sqlalchemy import select
    from openvort.contacts.models import Member

    session_factory = get_db_session_factory()
    async with session_factory() as session:
        stmt = select(Member).where(Member.id == member_id)
        result = await session.execute(stmt)
        member = result.scalar_one_or_none()
        if not member:
            raise HTTPException(status_code=404, detail="用户不存在")

        # 从 notification_prefs 字段读取，字段可能尚未添加
        raw = getattr(member, "notification_prefs", None) or "{}"
        try:
            prefs = json.loads(raw)
        except (json.JSONDecodeError, TypeError):
            prefs = {}

    # 返回默认结构（前端可合并）
    defaults = {
        "system": {"web": True},
        "task": {"web": True},
        "team": {"web": False},
    }
    # 合并已保存的偏好
    for key in defaults:
        if key in prefs:
            defaults[key] = prefs[key]

    return {"preferences": defaults}


@router.put("/notifications")
async def update_notification_prefs(request: Request, req: NotificationPreferences):
    """更新通知偏好设置"""
    member_id = _get_member_id(request)

    from sqlalchemy import select
    from openvort.contacts.models import Member

    session_factory = get_db_session_factory()
    async with session_factory() as session:
        stmt = select(Member).where(Member.id == member_id)
        result = await session.execute(stmt)
        member = result.scalar_one_or_none()
        if not member:
            raise HTTPException(status_code=404, detail="用户不存在")

        if hasattr(member, "notification_prefs"):
            member.notification_prefs = json.dumps(req.preferences, ensure_ascii=False)
        await session.commit()

    return {"success": True}


# ---- 头像上传 ----

@router.post("/profile/avatar")
async def upload_avatar(request: Request, file: UploadFile = File(...)):
    """上传头像"""
    member_id = _get_member_id(request)

    # 校验文件类型
    allowed = {"image/jpeg", "image/png", "image/gif", "image/webp"}
    if file.content_type not in allowed:
        return {"error": "仅支持 jpg/png/gif/webp 格式"}

    # 读取并保存
    content = await file.read()
    if len(content) > 5 * 1024 * 1024:
        return {"error": "文件大小不能超过 5MB"}

    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    ext = file.filename.rsplit(".", 1)[-1] if file.filename and "." in file.filename else "png"
    filename = f"{uuid.uuid4().hex}.{ext}"
    filepath = UPLOAD_DIR / filename
    filepath.write_bytes(content)

    avatar_url = f"/uploads/avatars/{filename}"

    # 更新数据库
    from sqlalchemy import select
    from openvort.contacts.models import Member

    session_factory = get_db_session_factory()
    async with session_factory() as session:
        stmt = select(Member).where(Member.id == member_id)
        result = await session.execute(stmt)
        member = result.scalar_one_or_none()
        if not member:
            return {"error": "用户不存在"}
        member.avatar_url = avatar_url
        await session.commit()

    return {"success": True, "avatar_url": avatar_url}


# ---- Git Token 管理 ----

class GitTokenRequest(BaseModel):
    platform: str  # gitee / github / gitlab
    token: str
    username: str = ""


@router.get("/git-tokens")
async def list_git_tokens(request: Request):
    """列出当前用户已配置的 Git Token（仅返回平台和用户名，不返回明文 token）"""
    member_id = _get_member_id(request)

    from sqlalchemy import select
    from openvort.contacts.models import PlatformIdentity

    session_factory = get_db_session_factory()
    async with session_factory() as session:
        stmt = select(PlatformIdentity).where(
            PlatformIdentity.member_id == member_id,
            PlatformIdentity.platform.in_(["gitee", "github", "gitlab"]),
        )
        result = await session.execute(stmt)
        identities = result.scalars().all()

    tokens = []
    for ident in identities:
        tokens.append({
            "platform": ident.platform,
            "username": ident.platform_username or ident.platform_user_id,
            "email": ident.platform_email,
            "has_token": bool(ident.access_token),
        })
    return {"tokens": tokens}


@router.put("/git-tokens")
async def save_git_token(request: Request, req: GitTokenRequest):
    """保存或更新个人 Git Token（加密存储）"""
    member_id = _get_member_id(request)

    if req.platform not in ("gitee", "github", "gitlab"):
        raise HTTPException(status_code=400, detail="平台仅支持 gitee / github / gitlab")
    if not req.token.strip():
        raise HTTPException(status_code=400, detail="Token 不能为空")

    from sqlalchemy import select
    from openvort.contacts.models import PlatformIdentity
    from openvort.plugins.vortgit.crypto import encrypt_token

    encrypted = encrypt_token(req.token.strip())

    session_factory = get_db_session_factory()
    async with session_factory() as session:
        stmt = select(PlatformIdentity).where(
            PlatformIdentity.member_id == member_id,
            PlatformIdentity.platform == req.platform,
        )
        result = await session.execute(stmt)
        ident = result.scalar_one_or_none()

        if ident:
            ident.access_token = encrypted
            if req.username.strip():
                ident.platform_username = req.username.strip()
        else:
            username = req.username.strip() or member_id[:8]
            ident = PlatformIdentity(
                member_id=member_id,
                platform=req.platform,
                platform_user_id=username,
                platform_username=username,
                access_token=encrypted,
            )
            session.add(ident)

        await session.commit()

    return {"success": True}


@router.delete("/git-tokens/{platform}")
async def delete_git_token(request: Request, platform: str):
    """删除个人 Git Token（仅清空 token，保留平台身份）"""
    member_id = _get_member_id(request)

    from sqlalchemy import select
    from openvort.contacts.models import PlatformIdentity

    session_factory = get_db_session_factory()
    async with session_factory() as session:
        stmt = select(PlatformIdentity).where(
            PlatformIdentity.member_id == member_id,
            PlatformIdentity.platform == platform,
        )
        result = await session.execute(stmt)
        ident = result.scalar_one_or_none()

        if ident:
            ident.access_token = ""
            await session.commit()

    return {"success": True}


@router.get("/workspace")
async def get_workspace(request: Request):
    """个人工作台数据"""
    payload = require_auth(request)
    member_id = payload.get("sub", "")
    name = payload.get("name", "")

    from openvort.web.deps import get_session_store
    session_store = get_session_store()

    # 获取该用户的最近对话数
    messages = session_store.get_messages("web", member_id)
    chat_count = len([m for m in messages if m.get("role") == "user"])

    return {
        "name": name,
        "chat_count": chat_count,
        "recent_chats": [],  # 后续可扩展
    }
