from fastapi import APIRouter
from sqlalchemy import func, select

from openvort.db.engine import get_session_factory
from openvort.plugins.vortflow.models import FlowTag

from .helpers import _count_tag_usage, _replace_tag_in_items, _sync_missing_tags, _tag_dict
from .schemas import TagCreate, TagMigrate, TagReorder, TagUpdate

sub_router = APIRouter()


@sub_router.get("/tags")
async def list_tags():
    sf = get_session_factory()
    async with sf() as session:
        await _sync_missing_tags(session)
        await session.commit()

        result = await session.execute(
            select(FlowTag).order_by(FlowTag.sort_order, FlowTag.created_at)
        )
        tags = result.scalars().all()
        items = []
        for t in tags:
            d = _tag_dict(t)
            d["usage_count"] = await _count_tag_usage(session, t.name)
            items.append(d)
    return {"items": items}


@sub_router.post("/tags")
async def create_tag(body: TagCreate):
    sf = get_session_factory()
    async with sf() as session:
        existing = await session.execute(
            select(FlowTag).where(FlowTag.name == body.name)
        )
        if existing.scalar_one_or_none():
            return {"error": "标签名称已存在"}
        max_order = await session.execute(
            select(func.coalesce(func.max(FlowTag.sort_order), 0))
        )
        next_order = (max_order.scalar() or 0) + 1
        tag = FlowTag(name=body.name, color=body.color, sort_order=next_order)
        session.add(tag)
        await session.commit()
        await session.refresh(tag)
    return _tag_dict(tag)


@sub_router.post("/tags/reorder")
async def reorder_tags(body: TagReorder):
    sf = get_session_factory()
    async with sf() as session:
        for idx, tag_id in enumerate(body.ids):
            tag = await session.get(FlowTag, tag_id)
            if tag:
                tag.sort_order = idx
        await session.commit()
    return {"ok": True}


@sub_router.put("/tags/{tag_id}")
async def update_tag(tag_id: str, body: TagUpdate):
    sf = get_session_factory()
    async with sf() as session:
        tag = await session.get(FlowTag, tag_id)
        if not tag:
            return {"error": "标签不存在"}
        old_name = tag.name
        if body.name is not None and body.name != old_name:
            dup = await session.execute(
                select(FlowTag).where(FlowTag.name == body.name, FlowTag.id != tag_id)
            )
            if dup.scalar_one_or_none():
                return {"error": "标签名称已存在"}
            await _replace_tag_in_items(session, old_name, body.name)
            tag.name = body.name
        if body.color is not None:
            tag.color = body.color
        await session.commit()
        await session.refresh(tag)
    return _tag_dict(tag)


@sub_router.delete("/tags/{tag_id}")
async def delete_tag(tag_id: str):
    sf = get_session_factory()
    async with sf() as session:
        tag = await session.get(FlowTag, tag_id)
        if not tag:
            return {"error": "标签不存在"}
        await _replace_tag_in_items(session, tag.name, None)
        await session.delete(tag)
        await session.commit()
    return {"ok": True}


@sub_router.post("/tags/{tag_id}/migrate")
async def migrate_tag(tag_id: str, body: TagMigrate):
    sf = get_session_factory()
    async with sf() as session:
        source_tag = await session.get(FlowTag, tag_id)
        if not source_tag:
            return {"error": "原标签不存在"}
        target_name: str | None = None
        if body.target_tag_id:
            target_tag = await session.get(FlowTag, body.target_tag_id)
            if not target_tag:
                return {"error": "目标标签不存在"}
            target_name = target_tag.name
        affected = await _count_tag_usage(session, source_tag.name)
        await _replace_tag_in_items(session, source_tag.name, target_name)
        await session.delete(source_tag)
        await session.commit()
    return {"ok": True, "affected": affected}
