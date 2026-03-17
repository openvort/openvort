import json

from fastapi import APIRouter, Query
from sqlalchemy import func, select

from openvort.db.engine import get_session_factory
from openvort.plugins.vortflow.models import FlowStatus

from .helpers import _ensure_default_statuses, _parse_json_list, _status_dict
from .schemas import StatusCreate, StatusUpdate

sub_router = APIRouter()


@sub_router.get("/statuses")
async def list_statuses(keyword: str = Query("", alias="keyword")):
    sf = get_session_factory()
    async with sf() as session:
        await _ensure_default_statuses(session)
        await session.commit()

        query = select(FlowStatus).order_by(FlowStatus.sort_order, FlowStatus.created_at)
        if keyword.strip():
            query = query.where(FlowStatus.name.contains(keyword.strip()))
        result = await session.execute(query)
        statuses = result.scalars().all()
    return {"items": [_status_dict(s) for s in statuses]}


@sub_router.post("/statuses")
async def create_status(body: StatusCreate):
    sf = get_session_factory()
    async with sf() as session:
        existing = await session.execute(
            select(FlowStatus).where(FlowStatus.name == body.name)
        )
        if existing.scalar_one_or_none():
            return {"error": "状态名称已存在"}
        max_order = await session.execute(
            select(func.coalesce(func.max(FlowStatus.sort_order), 0))
        )
        next_order = (max_order.scalar() or 0) + 1
        status = FlowStatus(
            name=body.name,
            icon=body.icon,
            icon_color=body.icon_color,
            command=body.command,
            work_item_types_json=json.dumps(body.work_item_types, ensure_ascii=False),
            sort_order=next_order,
        )
        session.add(status)
        await session.commit()
        await session.refresh(status)
    return _status_dict(status)


@sub_router.put("/statuses/{status_id}")
async def update_status(status_id: str, body: StatusUpdate):
    sf = get_session_factory()
    async with sf() as session:
        status = await session.get(FlowStatus, status_id)
        if not status:
            return {"error": "状态不存在"}
        if body.name is not None and body.name != status.name:
            dup = await session.execute(
                select(FlowStatus).where(FlowStatus.name == body.name, FlowStatus.id != status_id)
            )
            if dup.scalar_one_or_none():
                return {"error": "状态名称已存在"}
            status.name = body.name
        if body.icon is not None:
            status.icon = body.icon
        if body.icon_color is not None:
            status.icon_color = body.icon_color
        if body.command is not None:
            status.command = body.command
        if body.work_item_types is not None:
            status.work_item_types_json = json.dumps(body.work_item_types, ensure_ascii=False)
        await session.commit()
        await session.refresh(status)
    return _status_dict(status)


@sub_router.delete("/statuses/{status_id}")
async def delete_status(status_id: str):
    sf = get_session_factory()
    async with sf() as session:
        status = await session.get(FlowStatus, status_id)
        if not status:
            return {"error": "状态不存在"}
        await session.delete(status)
        await session.commit()
    return {"ok": True}
