"""个人信息路由 — 所有登录用户可访问"""

import uuid
from pathlib import Path

from fastapi import APIRouter, Request, UploadFile, File

from openvort.web.app import require_auth
from openvort.web.deps import get_db_session_factory, get_auth_service

router = APIRouter()

UPLOAD_DIR = Path(__file__).parent.parent.parent.parent / "web" / "dist" / "uploads" / "avatars"


@router.get("/profile")
async def get_profile(request: Request):
    """获取当前用户完整信息"""
    payload = require_auth(request)
    member_id = payload.get("sub", "")

    from sqlalchemy import select
    from openvort.contacts.models import Member, PlatformIdentity

    session_factory = get_db_session_factory()
    auth_service = get_auth_service()

    async with session_factory() as session:
        stmt = select(Member).where(Member.id == member_id)
        result = await session.execute(stmt)
        member = result.scalar_one_or_none()

        if not member:
            return {"error": "用户不存在"}

        roles = await auth_service.get_member_roles(member.id)
        if not roles:
            roles = ["member"]

        stmt = select(PlatformIdentity).where(PlatformIdentity.member_id == member.id)
        result = await session.execute(stmt)
        identities = result.scalars().all()

        platform_accounts = {}
        position = ""
        department = ""
        for ident in identities:
            platform_accounts[ident.platform] = ident.platform_user_id
            if ident.platform_position and not position:
                position = ident.platform_position
            if ident.platform_department and not department:
                department = ident.platform_department

    return {
        "member_id": member.id,
        "name": member.name,
        "email": member.email or "",
        "phone": member.phone or "",
        "avatar_url": member.avatar_url or "",
        "roles": roles,
        "position": position,
        "department": department,
        "platform_accounts": platform_accounts,
    }


@router.post("/profile/avatar")
async def upload_avatar(request: Request, file: UploadFile = File(...)):
    """上传头像"""
    payload = require_auth(request)
    member_id = payload.get("sub", "")

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
