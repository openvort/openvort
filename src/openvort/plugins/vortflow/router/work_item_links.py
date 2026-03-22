from fastapi import APIRouter, Query, Request
from pydantic import BaseModel
from sqlalchemy import or_, select

from openvort.db.engine import get_session_factory
from openvort.plugins.vortflow.models import FlowWorkItemLink
from openvort.web.app import require_auth

from .helpers import _LINK_TYPE_DICT, _LINK_TYPE_MODEL, _log_event

sub_router = APIRouter()


class WorkItemLinkCreate(BaseModel):
    source_type: str  # story/task/bug
    source_id: str
    target_type: str  # story/task/bug
    target_id: str


@sub_router.get("/work-item-links")
async def list_work_item_links(
    entity_type: str = Query(..., description="story/task/bug"),
    entity_id: str = Query(..., description="Work item ID"),
):
    sf = get_session_factory()
    async with sf() as session:
        stmt = select(FlowWorkItemLink).where(
            or_(
                (FlowWorkItemLink.source_type == entity_type) & (FlowWorkItemLink.source_id == entity_id),
                (FlowWorkItemLink.target_type == entity_type) & (FlowWorkItemLink.target_id == entity_id),
            )
        ).order_by(FlowWorkItemLink.created_at.desc())
        links = (await session.execute(stmt)).scalars().all()

        items = []
        for link in links:
            is_source = link.source_type == entity_type and link.source_id == entity_id
            peer_type = link.target_type if is_source else link.source_type
            peer_id = link.target_id if is_source else link.source_id
            model = _LINK_TYPE_MODEL.get(peer_type)
            to_dict = _LINK_TYPE_DICT.get(peer_type)
            if not model or not to_dict:
                continue
            peer = await session.get(model, peer_id)
            if not peer:
                continue
            d = to_dict(peer)
            d["link_id"] = link.id
            d["link_type"] = peer_type
            items.append(d)

    return {"items": items}


@sub_router.post("/work-item-links")
async def create_work_item_link(body: WorkItemLinkCreate, request: Request):
    payload = require_auth(request)
    member_id = payload.get("sub", "")

    src_model = _LINK_TYPE_MODEL.get(body.source_type)
    tgt_model = _LINK_TYPE_MODEL.get(body.target_type)
    if not src_model or not tgt_model:
        return {"error": "无效的工作项类型"}
    if body.source_type == body.target_type and body.source_id == body.target_id:
        return {"error": "不能关联自身"}

    sf = get_session_factory()
    async with sf() as session:
        src = await session.get(src_model, body.source_id)
        if not src:
            return {"error": "源工作项不存在"}
        tgt = await session.get(tgt_model, body.target_id)
        if not tgt:
            return {"error": "目标工作项不存在"}

        existing = await session.execute(
            select(FlowWorkItemLink).where(
                or_(
                    (FlowWorkItemLink.source_type == body.source_type)
                    & (FlowWorkItemLink.source_id == body.source_id)
                    & (FlowWorkItemLink.target_type == body.target_type)
                    & (FlowWorkItemLink.target_id == body.target_id),
                    (FlowWorkItemLink.source_type == body.target_type)
                    & (FlowWorkItemLink.source_id == body.target_id)
                    & (FlowWorkItemLink.target_type == body.source_type)
                    & (FlowWorkItemLink.target_id == body.source_id),
                )
            )
        )
        if existing.scalar_one_or_none():
            return {"error": "关联已存在"}

        link = FlowWorkItemLink(
            source_type=body.source_type,
            source_id=body.source_id,
            target_type=body.target_type,
            target_id=body.target_id,
            created_by=member_id,
        )
        session.add(link)
        await _log_event(session, body.source_type, body.source_id, "link_added",
                         {"target_type": body.target_type, "target_id": body.target_id})
        await session.commit()
        await session.refresh(link)
    return {"ok": True, "id": link.id}


@sub_router.delete("/work-item-links/{link_id}")
async def delete_work_item_link(link_id: str):
    sf = get_session_factory()
    async with sf() as session:
        link = await session.get(FlowWorkItemLink, link_id)
        if not link:
            return {"error": "关联不存在"}
        await _log_event(session, link.source_type, link.source_id, "link_removed",
                         {"target_type": link.target_type, "target_id": link.target_id})
        await session.delete(link)
        await session.commit()
    return {"ok": True}
