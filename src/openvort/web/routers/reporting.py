"""汇报关系路由"""

from fastapi import APIRouter
from pydantic import BaseModel

from openvort.web.deps import get_db_session_factory

router = APIRouter()


class CreateRelationRequest(BaseModel):
    reporter_id: str
    supervisor_id: str
    relation_type: str = "direct"
    is_primary: bool = True


class UpdateRelationRequest(BaseModel):
    relation_type: str | None = None
    is_primary: bool | None = None


@router.get("")
async def list_relations(member_id: str | None = None):
    """列出汇报关系，可按成员筛选"""
    from sqlalchemy import select
    from sqlalchemy.orm import selectinload

    from openvort.contacts.models import ReportingRelation

    session_factory = get_db_session_factory()
    async with session_factory() as session:
        stmt = select(ReportingRelation).options(
            selectinload(ReportingRelation.reporter),
            selectinload(ReportingRelation.supervisor),
        )
        if member_id:
            stmt = stmt.where(
                (ReportingRelation.reporter_id == member_id)
                | (ReportingRelation.supervisor_id == member_id)
            )
        stmt = stmt.order_by(ReportingRelation.created_at.desc())
        result = await session.execute(stmt)
        relations = result.scalars().all()

        items = []
        for r in relations:
            items.append({
                "id": r.id,
                "reporter_id": r.reporter_id,
                "reporter_name": r.reporter.name if r.reporter else "",
                "supervisor_id": r.supervisor_id,
                "supervisor_name": r.supervisor.name if r.supervisor else "",
                "relation_type": r.relation_type,
                "is_primary": r.is_primary,
                "created_at": r.created_at.isoformat() if r.created_at else None,
            })
        return {"relations": items}


@router.post("")
async def create_relation(req: CreateRelationRequest):
    """创建汇报关系"""
    from openvort.contacts.models import ReportingRelation

    if req.reporter_id == req.supervisor_id:
        return {"success": False, "error": "不能向自己汇报"}

    session_factory = get_db_session_factory()
    async with session_factory() as session:
        rel = ReportingRelation(
            reporter_id=req.reporter_id,
            supervisor_id=req.supervisor_id,
            relation_type=req.relation_type,
            is_primary=req.is_primary,
        )
        session.add(rel)
        try:
            await session.commit()
            await session.refresh(rel)
            return {"success": True, "id": rel.id}
        except Exception:
            await session.rollback()
            return {"success": False, "error": "汇报关系已存在或数据无效"}


@router.put("/{relation_id}")
async def update_relation(relation_id: int, req: UpdateRelationRequest):
    """更新汇报关系"""
    from sqlalchemy import select

    from openvort.contacts.models import ReportingRelation

    session_factory = get_db_session_factory()
    async with session_factory() as session:
        stmt = select(ReportingRelation).where(ReportingRelation.id == relation_id)
        result = await session.execute(stmt)
        rel = result.scalar_one_or_none()
        if not rel:
            return {"success": False, "error": "汇报关系不存在"}

        if req.relation_type is not None:
            rel.relation_type = req.relation_type
        if req.is_primary is not None:
            rel.is_primary = req.is_primary

        await session.commit()
        return {"success": True}


@router.delete("/{relation_id}")
async def delete_relation(relation_id: int):
    """删除汇报关系"""
    from sqlalchemy import delete

    from openvort.contacts.models import ReportingRelation

    session_factory = get_db_session_factory()
    async with session_factory() as session:
        stmt = delete(ReportingRelation).where(ReportingRelation.id == relation_id)
        result = await session.execute(stmt)
        await session.commit()
        return {"success": result.rowcount > 0}


@router.get("/subordinates/{member_id}")
async def get_subordinates(member_id: str):
    """获取某成员的所有下属"""
    from sqlalchemy import select
    from sqlalchemy.orm import selectinload

    from openvort.contacts.models import ReportingRelation

    session_factory = get_db_session_factory()
    async with session_factory() as session:
        stmt = (
            select(ReportingRelation)
            .options(selectinload(ReportingRelation.reporter))
            .where(ReportingRelation.supervisor_id == member_id)
        )
        result = await session.execute(stmt)
        relations = result.scalars().all()

        subordinates = []
        for r in relations:
            subordinates.append({
                "member_id": r.reporter_id,
                "name": r.reporter.name if r.reporter else "",
                "relation_type": r.relation_type,
                "is_primary": r.is_primary,
            })
        return {"subordinates": subordinates}


@router.get("/supervisors/{member_id}")
async def get_supervisors(member_id: str):
    """获取某成员的所有上级"""
    from sqlalchemy import select
    from sqlalchemy.orm import selectinload

    from openvort.contacts.models import ReportingRelation

    session_factory = get_db_session_factory()
    async with session_factory() as session:
        stmt = (
            select(ReportingRelation)
            .options(selectinload(ReportingRelation.supervisor))
            .where(ReportingRelation.reporter_id == member_id)
        )
        result = await session.execute(stmt)
        relations = result.scalars().all()

        supervisors = []
        for r in relations:
            supervisors.append({
                "member_id": r.supervisor_id,
                "name": r.supervisor.name if r.supervisor else "",
                "relation_type": r.relation_type,
                "is_primary": r.is_primary,
            })
        return {"supervisors": supervisors}
