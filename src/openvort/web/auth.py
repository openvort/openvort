"""
Web 面板认证

成员登录 + JWT（含角色权限）方案。
"""

import time
import hashlib
import hmac
import json
import base64

from openvort.config.settings import get_settings

TOKEN_EXPIRE_HOURS = 24


def _get_secret_key() -> str:
    """用 default_password 派生签名密钥"""
    settings = get_settings()
    pwd = settings.web.default_password
    return hashlib.sha256(pwd.encode()).hexdigest()


def _b64url_encode(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode()


def _b64url_decode(s: str) -> bytes:
    padding = 4 - len(s) % 4
    if padding != 4:
        s += "=" * padding
    return base64.urlsafe_b64decode(s)


def create_token(
    member_id: str,
    name: str,
    roles: list[str],
    expire_hours: int = TOKEN_EXPIRE_HOURS,
) -> str:
    """创建 JWT token，payload 含成员身份和角色"""
    header = _b64url_encode(json.dumps({"alg": "HS256", "typ": "JWT"}).encode())
    payload_data = {
        "sub": member_id,
        "name": name,
        "roles": roles,
        "exp": int(time.time()) + expire_hours * 3600,
        "iat": int(time.time()),
    }
    payload = _b64url_encode(json.dumps(payload_data).encode())
    signing_input = f"{header}.{payload}"
    signature = hmac.new(
        _get_secret_key().encode(), signing_input.encode(), hashlib.sha256
    ).digest()
    sig = _b64url_encode(signature)
    return f"{header}.{payload}.{sig}"


def verify_token(token: str) -> dict | None:
    """验证 JWT token，返回 payload 或 None

    返回: { sub: member_id, name, roles: [...], exp, iat }
    """
    try:
        parts = token.split(".")
        if len(parts) != 3:
            return None
        header, payload, sig = parts
        signing_input = f"{header}.{payload}"
        expected_sig = hmac.new(
            _get_secret_key().encode(), signing_input.encode(), hashlib.sha256
        ).digest()
        if not hmac.compare_digest(_b64url_decode(sig), expected_sig):
            return None
        payload_data = json.loads(_b64url_decode(payload))
        if payload_data.get("exp", 0) < time.time():
            return None
        return payload_data
    except Exception:
        return None


def hash_password(password: str) -> str:
    """对密码做 SHA-256 哈希（简单方案，与 JWT 签名复用 hashlib）"""
    return hashlib.sha256(password.encode()).hexdigest()


def verify_password(password: str, password_hash: str) -> bool:
    """验证密码是否匹配哈希"""
    return hmac.compare_digest(hash_password(password), password_hash)


async def authenticate_member(user_id: str, password: str) -> dict | None:
    """验证成员登录

    通过 user_id 查 platform_identities 或 members 表找到成员，
    验证密码：优先校验独立密码，为空时 fallback 到 default_password。
    仅 is_account=True 且 status=active 的成员可登录。

    Returns:
        { member_id, name, roles, position, department, platform_accounts } 或 None
    """
    from sqlalchemy import select
    from openvort.contacts.models import Member, PlatformIdentity
    from openvort.web.deps import get_db_session_factory, get_auth_service
    from openvort.utils.logging import get_logger

    log = get_logger("web.auth")

    settings = get_settings()
    session_factory = get_db_session_factory()
    auth_service = get_auth_service()

    async with session_factory() as session:
        member = None
        # 先按 platform_user_id 查（可能跨平台出现多条，不能用 scalar_one_or_none）
        stmt = select(PlatformIdentity).where(PlatformIdentity.platform_user_id == user_id)
        result = await session.execute(stmt)
        identities = result.scalars().all()
        if identities:
            if len(identities) > 1:
                log.warning(f"登录 user_id={user_id} 命中 {len(identities)} 条平台身份，按可登录账号优先匹配")
            member_ids = [i.member_id for i in identities]
            stmt = select(Member).where(Member.id.in_(member_ids), Member.status == "active", Member.is_account)
            result = await session.execute(stmt)
            candidates = result.scalars().all()
            member_by_id = {m.id: m for m in candidates}
            for ident in identities:
                if ident.member_id in member_by_id:
                    member = member_by_id[ident.member_id]
                    break
        else:
            # 按姓名查
            stmt = select(Member).where(Member.name == user_id, Member.status == "active")
            result = await session.execute(stmt)
            member = result.scalars().first()

        if not member:
            return None

        # 检查是否为可登录账号且状态正常
        if not member.is_account or member.status != "active":
            return None

        # 密码验证：优先独立密码，为空时 fallback 到 default_password
        if member.password_hash:
            if not verify_password(password, member.password_hash):
                return None
        else:
            if password != settings.web.default_password:
                return None

        # 查角色
        roles = await auth_service.get_member_roles(member.id)
        if not roles:
            roles = ["member"]  # 默认角色

        # 查平台账号和职位
        stmt = select(PlatformIdentity).where(PlatformIdentity.member_id == member.id)
        result = await session.execute(stmt)
        identities = result.scalars().all()

        platform_accounts = {}
        position = ""
        for ident in identities:
            platform_accounts[ident.platform] = ident.platform_user_id
            if ident.platform_position and not position:
                position = ident.platform_position

        # 从 MemberDepartment 关联查真实部门名称
        from openvort.contacts.models import MemberDepartment, Department
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
            "roles": roles,
            "position": position,
            "department": department,
            "platform_accounts": platform_accounts,
        }
