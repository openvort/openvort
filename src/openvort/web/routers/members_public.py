"""Public member endpoints — all authenticated users."""

from fastapi import APIRouter
from sqlalchemy import select, func as sa_func

from openvort.web.deps import get_db_session_factory

router = APIRouter()


@router.get("/simple")
async def list_members_simple(search: str = "", page: int = 1, size: int = 100):
    """Return a lightweight member list for pickers / dropdowns.

    Only exposes id, name, avatar_url, is_virtual, and department — no
    sensitive fields like email / phone / password / platform_accounts.
    """
    from openvort.contacts.models import Member, MemberDepartment, Department

    session_factory = get_db_session_factory()

    async with session_factory() as session:
        stmt = select(Member).where(Member.status == "active").order_by(Member.name)

        if search:
            pattern = f"%{search}%"
            stmt = stmt.where(Member.name.ilike(pattern))

        count_stmt = select(sa_func.count()).select_from(stmt.subquery())
        total = (await session.execute(count_stmt)).scalar() or 0

        offset = (page - 1) * size
        stmt = stmt.offset(offset).limit(size)
        result = await session.execute(stmt)
        members = result.scalars().all()

        items = []
        for m in members:
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
                "avatar_url": m.avatar_url or "",
                "is_virtual": m.is_virtual,
                "dept": " / ".join(departments) if departments else "",
            })

        return {"members": items, "total": total, "page": page, "size": size}
