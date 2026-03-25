"""
MCP 认证

通过 Personal Access Token (PAT) 验证 MCP 请求的调用者身份，
将 token 映射到成员，构建 RequestContext。
"""

from datetime import datetime, timezone

from sqlalchemy import select, text

from openvort.config.settings import get_settings
from openvort.contacts.models import Member, PlatformIdentity, MemberDepartment, Department
from openvort.utils.logging import get_logger
from openvort.web.auth import verify_password

log = get_logger("mcp.auth")


async def authenticate_pat(token: str) -> dict | None:
    """Validate a PAT and return member info, or None if invalid.

    Returns: { member_id, name, roles, position, department, ... } or None.
    """
    if not token or not token.startswith("ovt_"):
        return None

    token_prefix = token[:8]

    from openvort.web.deps import get_db_session_factory, get_auth_service

    session_factory = get_db_session_factory()
    auth_service = get_auth_service()

    async with session_factory() as session:
        result = await session.execute(
            text("""
                SELECT id, member_id, token_hash, expires_at
                FROM personal_access_tokens
                WHERE token_prefix = :prefix
            """),
            {"prefix": token_prefix},
        )
        candidates = result.mappings().all()

        matched_row = None
        for row in candidates:
            if verify_password(token, row["token_hash"]):
                matched_row = row
                break

        if not matched_row:
            return None

        if matched_row["expires_at"]:
            expires = matched_row["expires_at"]
            if hasattr(expires, "tzinfo") and expires.tzinfo is None:
                expires = expires.replace(tzinfo=timezone.utc)
            if expires < datetime.now(timezone.utc):
                log.warning(f"PAT {matched_row['id'][:8]}... expired")
                return None

        # Update last_used_at (fire-and-forget, no need to block)
        await session.execute(
            text("UPDATE personal_access_tokens SET last_used_at = NOW() WHERE id = :id"),
            {"id": matched_row["id"]},
        )
        await session.commit()

        member_id = matched_row["member_id"]

        stmt = select(Member).where(Member.id == member_id, Member.status == "active")
        result = await session.execute(stmt)
        member = result.scalar_one_or_none()
        if not member:
            log.warning(f"PAT member {member_id} not found or inactive")
            return None

        roles = await auth_service.get_member_roles(member.id)
        if not roles:
            roles = ["member"]

        stmt = select(PlatformIdentity).where(PlatformIdentity.member_id == member.id)
        result = await session.execute(stmt)
        identities = result.scalars().all()

        platform_accounts = {}
        position = member.position or ""
        for ident in identities:
            platform_accounts[ident.platform] = ident.platform_user_id
            if not position and ident.platform_position:
                position = ident.platform_position

        dept_stmt = (
            select(Department.name)
            .join(MemberDepartment, MemberDepartment.department_id == Department.id)
            .where(MemberDepartment.member_id == member.id)
            .order_by(MemberDepartment.is_primary.desc())
        )
        dept_result = await session.execute(dept_stmt)
        dept_names = [row[0] for row in dept_result.all()]

    return {
        "member_id": member.id,
        "member": member,
        "name": member.name,
        "roles": roles,
        "position": position,
        "department": " / ".join(dept_names) if dept_names else "",
        "platform_accounts": platform_accounts,
    }


async def authenticate_anonymous_localhost() -> dict | None:
    """When allow_anonymous_localhost is enabled, resolve the configured member."""
    settings = get_settings()
    member_name = settings.mcp.anonymous_member_name
    if not member_name:
        return None

    from openvort.web.deps import get_db_session_factory, get_auth_service

    session_factory = get_db_session_factory()
    auth_service = get_auth_service()

    async with session_factory() as session:
        stmt = select(Member).where(Member.name == member_name, Member.status == "active")
        result = await session.execute(stmt)
        member = result.scalar_one_or_none()
        if not member:
            log.warning(f"MCP anonymous member '{member_name}' not found")
            return None

        roles = await auth_service.get_member_roles(member.id)
        if not roles:
            roles = ["member"]

    return {
        "member_id": member.id,
        "member": member,
        "name": member.name,
        "roles": roles,
        "position": member.position or "",
        "department": "",
        "platform_accounts": {},
    }


async def resolve_mcp_identity(authorization: str | None, client_host: str | None = None) -> dict | None:
    """Resolve MCP caller identity from the request.

    Priority:
    1. Bearer PAT token (ovt_xxx)
    2. Anonymous localhost (if configured)

    Returns member info dict or None.
    """
    # 1. Try PAT
    if authorization and authorization.startswith("Bearer "):
        token = authorization[7:].strip()
        if token.startswith("ovt_"):
            result = await authenticate_pat(token)
            if result:
                log.info(f"MCP authenticated via PAT: {result['name']}")
                return result
            log.warning("MCP PAT authentication failed")
            return None

    # 2. Anonymous localhost fallback
    settings = get_settings()
    if settings.mcp.allow_anonymous_localhost:
        is_localhost = client_host in ("127.0.0.1", "::1", "localhost", None)
        if is_localhost:
            result = await authenticate_anonymous_localhost()
            if result:
                log.info(f"MCP anonymous localhost -> {result['name']}")
                return result

    return None
