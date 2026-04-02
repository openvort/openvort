"""Version CRUD, Version Stories."""

from datetime import datetime

from fastapi import APIRouter, Query
from sqlalchemy import func, select, delete as sa_delete

from openvort.db.engine import get_session_factory
from openvort.plugins.vortflow.models import (
    FlowVersion, FlowVersionStory, FlowVersionBug, FlowStory, FlowBug,
)
from .helpers import _log_event, _parse_dt, _story_dict, _bug_dict, _version_dict
from .schemas import VersionCreate, VersionUpdate, VersionStoryBody, VersionBugBody

sub_router = APIRouter()


# ============ Version CRUD ============

@sub_router.get("/versions")
async def list_versions(
    project_id: str = Query("", description="按项目过滤"),
    status: str = Query("", description="按状态过滤"),
    keyword: str = Query("", description="按版本号/名称搜索"),
    owner_id: str = Query("", description="按负责人过滤"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=200),
):
    sf = get_session_factory()
    async with sf() as session:
        stmt = select(FlowVersion).order_by(FlowVersion.created_at.desc(), FlowVersion.id.desc())
        count_stmt = select(func.count()).select_from(FlowVersion)
        if project_id:
            stmt = stmt.where(FlowVersion.project_id == project_id)
            count_stmt = count_stmt.where(FlowVersion.project_id == project_id)
        if status:
            stmt = stmt.where(FlowVersion.status == status)
            count_stmt = count_stmt.where(FlowVersion.status == status)
        if keyword:
            like = f"%{keyword}%"
            cond = FlowVersion.name.ilike(like) | FlowVersion.description.ilike(like)
            stmt = stmt.where(cond)
            count_stmt = count_stmt.where(cond)
        if owner_id:
            stmt = stmt.where(FlowVersion.owner_id == owner_id)
            count_stmt = count_stmt.where(FlowVersion.owner_id == owner_id)
        total = (await session.execute(count_stmt)).scalar_one()
        stmt = stmt.offset((page - 1) * page_size).limit(page_size)
        rows = (await session.execute(stmt)).scalars().all()
    return {"total": total, "items": [_version_dict(r) for r in rows]}


@sub_router.get("/versions/{version_id}")
async def get_version(version_id: str):
    sf = get_session_factory()
    async with sf() as session:
        r = await session.get(FlowVersion, version_id)
        if not r:
            return {"error": "版本不存在"}
    return _version_dict(r)


@sub_router.post("/versions")
async def create_version(body: VersionCreate):
    sf = get_session_factory()
    async with sf() as session:
        planned_release = _parse_dt(body.planned_release_at) or _parse_dt(body.release_date)
        actual_release = _parse_dt(body.actual_release_at)
        v = FlowVersion(
            project_id=body.project_id, name=body.name,
            description=body.description,
            owner_id=body.owner_id,
            planned_release_at=planned_release,
            actual_release_at=actual_release,
            progress=max(0, min(100, int(body.progress or 0))),
            release_date=planned_release,
            status=body.status,
        )
        session.add(v)
        await session.flush()
        await _log_event(session, "version", v.id, "created", {"name": body.name})
        await session.commit()
        await session.refresh(v)
    return _version_dict(v)


@sub_router.put("/versions/{version_id}")
async def update_version(version_id: str, body: VersionUpdate):
    sf = get_session_factory()
    async with sf() as session:
        v = await session.get(FlowVersion, version_id)
        if not v:
            return {"error": "版本不存在"}
        changes = {}
        for field in ["name", "description", "status", "owner_id", "progress"]:
            val = getattr(body, field)
            if val is not None:
                old_val = getattr(v, field)
                if field == "progress":
                    val = max(0, min(100, int(val)))
                changes[field] = {"from": old_val, "to": val}
                setattr(v, field, val)
        if body.planned_release_at is not None or body.release_date is not None:
            old_val = str(v.planned_release_at) if v.planned_release_at else None
            planned = _parse_dt(body.planned_release_at) if body.planned_release_at is not None else _parse_dt(body.release_date)
            v.planned_release_at = planned
            v.release_date = planned
            changes["planned_release_at"] = {"from": old_val, "to": body.planned_release_at or body.release_date}
        if body.actual_release_at is not None:
            old_val = str(v.actual_release_at) if v.actual_release_at else None
            v.actual_release_at = _parse_dt(body.actual_release_at)
            changes["actual_release_at"] = {"from": old_val, "to": body.actual_release_at}
        if changes:
            await _log_event(session, "version", version_id, "updated", changes)
        await session.commit()
        await session.refresh(v)
    return _version_dict(v)


@sub_router.delete("/versions/{version_id}")
async def delete_version(version_id: str):
    sf = get_session_factory()
    async with sf() as session:
        v = await session.get(FlowVersion, version_id)
        if not v:
            return {"error": "版本不存在"}
        await session.execute(sa_delete(FlowVersionStory).where(FlowVersionStory.version_id == version_id))
        await session.delete(v)
        await _log_event(session, "version", version_id, "deleted", {"name": v.name})
        await session.commit()
    return {"ok": True}


@sub_router.post("/versions/{version_id}/release")
async def release_version(version_id: str):
    """发布版本"""
    sf = get_session_factory()
    async with sf() as session:
        v = await session.get(FlowVersion, version_id)
        if not v:
            return {"error": "版本不存在"}
        if v.status == "released":
            return {"error": "版本已发布"}
        v.status = "released"
        v.actual_release_at = datetime.utcnow()
        v.release_date = v.actual_release_at
        v.progress = 100
        await _log_event(session, "version", version_id, "released", {"name": v.name})
        await session.commit()
        await session.refresh(v)
    return _version_dict(v)


# ---- Version Stories ----

@sub_router.get("/versions/{version_id}/stories")
async def list_version_stories(version_id: str):
    sf = get_session_factory()
    async with sf() as session:
        stmt = (
            select(FlowVersionStory, FlowStory)
            .join(FlowStory, FlowVersionStory.story_id == FlowStory.id)
            .where(FlowVersionStory.version_id == version_id)
            .order_by(FlowVersionStory.story_order.asc())
        )
        rows = await session.execute(stmt)
        items = []
        for link, story in rows:
            items.append({
                "link_id": link.id,
                "added_reason": link.added_reason,
                "story_order": link.story_order,
                **_story_dict(story),
            })
    return {"items": items}


@sub_router.post("/versions/{version_id}/stories")
async def add_version_story(version_id: str, body: VersionStoryBody):
    sf = get_session_factory()
    async with sf() as session:
        version = await session.get(FlowVersion, version_id)
        if not version:
            return {"error": "版本不存在"}
        story = await session.get(FlowStory, body.story_id)
        if not story:
            return {"error": "需求不存在"}
        existing = await session.execute(
            select(FlowVersionStory).where(
                FlowVersionStory.version_id == version_id,
                FlowVersionStory.story_id == body.story_id,
            )
        )
        if existing.scalar_one_or_none():
            return {"error": "需求已在版本中"}
        link = FlowVersionStory(
            version_id=version_id, story_id=body.story_id,
            added_reason=body.added_reason, story_order=body.story_order,
        )
        session.add(link)
        await _log_event(session, "version", version_id, "story_added",
                         {"story_id": body.story_id})
        await session.commit()
    return {"ok": True}


@sub_router.delete("/versions/{version_id}/stories/{story_id}")
async def remove_version_story(version_id: str, story_id: str):
    sf = get_session_factory()
    async with sf() as session:
        await session.execute(
            sa_delete(FlowVersionStory).where(
                FlowVersionStory.version_id == version_id,
                FlowVersionStory.story_id == story_id,
            )
        )
        await _log_event(session, "version", version_id, "story_removed",
                         {"story_id": story_id})
        await session.commit()
    return {"ok": True}


# ---- Version Bugs ----

@sub_router.post("/versions/{version_id}/bugs")
async def add_version_bug(version_id: str, body: VersionBugBody):
    sf = get_session_factory()
    async with sf() as session:
        version = await session.get(FlowVersion, version_id)
        if not version:
            return {"error": "版本不存在"}
        bug = await session.get(FlowBug, body.bug_id)
        if not bug:
            return {"error": "缺陷不存在"}
        existing = await session.execute(
            select(FlowVersionBug).where(
                FlowVersionBug.version_id == version_id,
                FlowVersionBug.bug_id == body.bug_id,
            )
        )
        if existing.scalar_one_or_none():
            return {"error": "缺陷已在版本中"}
        link = FlowVersionBug(
            version_id=version_id, bug_id=body.bug_id,
            bug_order=body.bug_order,
        )
        session.add(link)
        await _log_event(session, "version", version_id, "bug_added",
                         {"bug_id": body.bug_id})
        await session.commit()
    return {"ok": True}


@sub_router.delete("/versions/{version_id}/bugs/{bug_id}")
async def remove_version_bug(version_id: str, bug_id: str):
    sf = get_session_factory()
    async with sf() as session:
        await session.execute(
            sa_delete(FlowVersionBug).where(
                FlowVersionBug.version_id == version_id,
                FlowVersionBug.bug_id == bug_id,
            )
        )
        await _log_event(session, "version", version_id, "bug_removed",
                         {"bug_id": bug_id})
        await session.commit()
    return {"ok": True}
