"""Custom Views CRUD, Column Settings."""

import json

from fastapi import APIRouter, Query, Request
from sqlalchemy import or_, select

from openvort.db.engine import get_session_factory
from openvort.web.app import require_auth
from openvort.plugins.vortflow.models import FlowView, FlowColumnSetting
from .schemas import ViewCreate, ViewUpdate, ColumnSettingBody

sub_router = APIRouter()


def _view_dict(r: FlowView) -> dict:
    return {
        "id": r.id, "name": r.name,
        "work_item_type": r.work_item_type,
        "scope": r.scope, "owner_id": r.owner_id,
        "filters": json.loads(r.filters_json) if r.filters_json else {},
        "columns": json.loads(r.columns_json) if r.columns_json else [],
        "order": r.view_order,
        "created_at": r.created_at.isoformat() if r.created_at else None,
        "updated_at": r.updated_at.isoformat() if r.updated_at else None,
    }


# ============ Custom Views CRUD ============

@sub_router.get("/views")
async def list_views(
    request: Request,
    work_item_type: str = Query("", description="按工作项类型过滤"),
):
    payload = require_auth(request)
    member_id = payload.get("sub", "")
    sf = get_session_factory()
    async with sf() as session:
        stmt = (
            select(FlowView)
            .where(or_(
                FlowView.scope == "shared",
                FlowView.owner_id == member_id,
            ))
            .order_by(FlowView.view_order.asc(), FlowView.created_at.asc())
        )
        if work_item_type:
            stmt = stmt.where(FlowView.work_item_type == work_item_type)
        rows = (await session.execute(stmt)).scalars().all()
    return {"items": [_view_dict(r) for r in rows]}

@sub_router.post("/views")
async def create_view(body: ViewCreate, request: Request):
    payload = require_auth(request)
    member_id = payload.get("sub", "")
    sf = get_session_factory()
    async with sf() as session:
        v = FlowView(
            name=body.name,
            work_item_type=body.work_item_type,
            scope=body.scope,
            owner_id=member_id,
            filters_json=json.dumps(body.filters, ensure_ascii=False),
            columns_json=json.dumps(body.columns, ensure_ascii=False),
        )
        session.add(v)
        await session.commit()
        await session.refresh(v)
    return _view_dict(v)

@sub_router.put("/views/{view_id}")
async def update_view(view_id: str, body: ViewUpdate, request: Request):
    payload = require_auth(request)
    member_id = payload.get("sub", "")
    sf = get_session_factory()
    async with sf() as session:
        v = await session.get(FlowView, view_id)
        if not v:
            return {"error": "视图不存在"}
        if v.scope == "personal" and v.owner_id != member_id:
            return {"error": "无权修改他人的个人视图"}
        if body.name is not None:
            v.name = body.name
        if body.filters is not None:
            v.filters_json = json.dumps(body.filters, ensure_ascii=False)
        if body.columns is not None:
            v.columns_json = json.dumps(body.columns, ensure_ascii=False)
        if body.view_order is not None:
            v.view_order = body.view_order
        await session.commit()
        await session.refresh(v)
    return _view_dict(v)

@sub_router.delete("/views/{view_id}")
async def delete_view(view_id: str, request: Request):
    payload = require_auth(request)
    member_id = payload.get("sub", "")
    sf = get_session_factory()
    async with sf() as session:
        v = await session.get(FlowView, view_id)
        if not v:
            return {"error": "视图不存在"}
        if v.scope == "personal" and v.owner_id != member_id:
            return {"error": "无权删除他人的个人视图"}
        await session.delete(v)
        await session.commit()
    return {"ok": True}


# ============ Column Settings (per user per type) ============

@sub_router.get("/column-settings")
async def get_column_settings(
    request: Request,
    work_item_type: str = Query("", description="工作项类型"),
):
    payload = require_auth(request)
    member_id = payload.get("sub", "")
    sf = get_session_factory()
    async with sf() as session:
        stmt = select(FlowColumnSetting).where(FlowColumnSetting.member_id == member_id)
        if work_item_type:
            stmt = stmt.where(FlowColumnSetting.work_item_type == work_item_type)
        rows = (await session.execute(stmt)).scalars().all()
    result = {}
    for r in rows:
        result[r.work_item_type] = json.loads(r.columns_json) if r.columns_json else []
    return result

@sub_router.put("/column-settings")
async def save_column_settings(body: ColumnSettingBody, request: Request):
    payload = require_auth(request)
    member_id = payload.get("sub", "")
    sf = get_session_factory()
    async with sf() as session:
        stmt = select(FlowColumnSetting).where(
            FlowColumnSetting.member_id == member_id,
            FlowColumnSetting.work_item_type == body.work_item_type,
        )
        existing = (await session.execute(stmt)).scalar_one_or_none()
        columns_str = json.dumps(body.columns, ensure_ascii=False)
        if existing:
            existing.columns_json = columns_str
        else:
            session.add(FlowColumnSetting(
                member_id=member_id,
                work_item_type=body.work_item_type,
                columns_json=columns_str,
            ))
        await session.commit()
    return {"ok": True}
