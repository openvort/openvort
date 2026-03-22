"""个人信息路由 — 所有登录用户可访问"""

import json
import uuid

from fastapi import APIRouter, HTTPException, Request, UploadFile, File
from pydantic import BaseModel

from openvort.config.settings import get_settings
from openvort.web.app import require_auth
from openvort.web.deps import get_db_session_factory, get_auth_service, get_registry
from openvort.web.upload_utils import get_upload_dir, get_upload_url

router = APIRouter()

UPLOAD_DIR = get_upload_dir("avatars")


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
        "vortflow": {"web": True, "im": True},
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

    avatar_url = get_upload_url(f"/uploads/avatars/{filename}")

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
        member.avatar_source = "manual"
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


# ---- 个人插件配置 ----


@router.get("/plugin-settings")
async def list_plugin_personal_settings(request: Request):
    """列出所有声明了 personal_config_schema 的插件及当前用户配置状态"""
    member_id = _get_member_id(request)

    registry = get_registry()

    from sqlalchemy import select
    from openvort.db.models import MemberPluginSetting

    session_factory = get_db_session_factory()
    async with session_factory() as session:
        stmt = select(MemberPluginSetting).where(MemberPluginSetting.member_id == member_id)
        result = await session.execute(stmt)
        saved = {row.plugin_name: row for row in result.scalars().all()}

    plugins = []
    for plugin in registry.list_plugins():
        schema = plugin.get_personal_config_schema()
        if not schema:
            continue
        has_config = plugin.name in saved and saved[plugin.name].settings_data != "{}"
        plugins.append({
            "plugin_name": plugin.name,
            "display_name": plugin.display_name,
            "description": plugin.description,
            "schema": schema,
            "has_config": has_config,
        })
    return {"plugins": plugins}


@router.get("/plugin-settings/{plugin_name}")
async def get_plugin_personal_settings(request: Request, plugin_name: str):
    """获取某插件的个人配置（secret 字段脱敏）"""
    member_id = _get_member_id(request)

    registry = get_registry()
    plugin = registry.get_plugin(plugin_name)
    if not plugin:
        raise HTTPException(status_code=404, detail="插件不存在")

    schema = plugin.get_personal_config_schema()
    if not schema:
        raise HTTPException(status_code=400, detail="该插件不支持个人配置")

    secret_keys = {f["key"] for f in schema if f.get("secret")}

    from sqlalchemy import select
    from openvort.db.models import MemberPluginSetting

    session_factory = get_db_session_factory()
    async with session_factory() as session:
        stmt = select(MemberPluginSetting).where(
            MemberPluginSetting.member_id == member_id,
            MemberPluginSetting.plugin_name == plugin_name,
        )
        result = await session.execute(stmt)
        row = result.scalar_one_or_none()

    config = {}
    if row and row.settings_data:
        raw = json.loads(row.settings_data)
        for key, val in raw.items():
            if key in secret_keys and val:
                from openvort.plugins.vortgit.crypto import decrypt_token
                try:
                    decrypted = decrypt_token(val)
                    config[key] = "****" + decrypted[-4:] if len(decrypted) > 4 else "****"
                except Exception:
                    config[key] = "****"
            else:
                config[key] = val

    return {"plugin_name": plugin_name, "config": config, "schema": schema}


class PluginPersonalSettingsRequest(BaseModel):
    settings: dict


@router.put("/plugin-settings/{plugin_name}")
async def save_plugin_personal_settings(request: Request, plugin_name: str, req: PluginPersonalSettingsRequest):
    """保存个人插件配置（secret 字段加密存储）"""
    member_id = _get_member_id(request)

    registry = get_registry()
    plugin = registry.get_plugin(plugin_name)
    if not plugin:
        raise HTTPException(status_code=404, detail="插件不存在")

    schema = plugin.get_personal_config_schema()
    if not schema:
        raise HTTPException(status_code=400, detail="该插件不支持个人配置")

    secret_keys = {f["key"] for f in schema if f.get("secret")}

    from sqlalchemy import select
    from openvort.db.models import MemberPluginSetting
    from openvort.plugins.vortgit.crypto import encrypt_token

    session_factory = get_db_session_factory()
    async with session_factory() as session:
        stmt = select(MemberPluginSetting).where(
            MemberPluginSetting.member_id == member_id,
            MemberPluginSetting.plugin_name == plugin_name,
        )
        result = await session.execute(stmt)
        row = result.scalar_one_or_none()

        old_data = json.loads(row.settings_data) if row and row.settings_data else {}
        new_data = {}
        for key, val in req.settings.items():
            if key in secret_keys:
                if isinstance(val, str) and val.startswith("****"):
                    new_data[key] = old_data.get(key, "")
                elif val:
                    cleaned = str(val).encode("ascii", errors="ignore").decode("ascii").strip()
                    if not cleaned:
                        raise HTTPException(status_code=400, detail=f"字段 {key} 包含无效字符，请确保输入纯 ASCII 内容（如 API Token）")
                    new_data[key] = encrypt_token(cleaned)
                else:
                    new_data[key] = ""
            else:
                new_data[key] = val

        settings_json = json.dumps(new_data, ensure_ascii=False)

        if row:
            row.settings_data = settings_json
        else:
            row = MemberPluginSetting(
                member_id=member_id,
                plugin_name=plugin_name,
                settings_data=settings_json,
            )
            session.add(row)
        await session.commit()

    return {"success": True}


@router.delete("/plugin-settings/{plugin_name}")
async def delete_plugin_personal_settings(request: Request, plugin_name: str):
    """删除个人插件配置"""
    member_id = _get_member_id(request)

    from sqlalchemy import select
    from openvort.db.models import MemberPluginSetting

    session_factory = get_db_session_factory()
    async with session_factory() as session:
        stmt = select(MemberPluginSetting).where(
            MemberPluginSetting.member_id == member_id,
            MemberPluginSetting.plugin_name == plugin_name,
        )
        result = await session.execute(stmt)
        row = result.scalar_one_or_none()
        if row:
            await session.delete(row)
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
