from fastapi import APIRouter
from sqlalchemy import func, select, delete as sa_delete

from openvort.db.engine import get_session_factory
from openvort.plugins.vortflow.router.helpers import (
    _parse_dt,
    _project_dict,
    _log_event,
)
from openvort.plugins.vortflow.router.schemas import (
    ProjectCreate,
    ProjectUpdate,
    ProjectMemberBody,
)
from openvort.plugins.vortflow.models import (
    FlowProject,
    FlowProjectMember,
    FlowStory,
    FlowTask,
    FlowBug,
)

sub_router = APIRouter()


# ============ Project CRUD ============

@sub_router.get("/projects")
async def list_projects():
    sf = get_session_factory()
    async with sf() as session:
        result = await session.execute(select(FlowProject).order_by(FlowProject.created_at.desc()))
        rows = result.scalars().all()

        project_story_ids: dict[str, list[str]] = {}
        items = []
        for r in rows:
            story_count = (await session.execute(
                select(func.count()).select_from(FlowStory).where(FlowStory.project_id == r.id)
            )).scalar_one()

            story_ids_result = (await session.execute(
                select(FlowStory.id).where(FlowStory.project_id == r.id)
            )).scalars().all()
            project_story_ids[r.id] = list(story_ids_result)

            task_count = 0
            bug_count = 0
            if project_story_ids[r.id]:
                task_count = (await session.execute(
                    select(func.count()).select_from(FlowTask).where(
                        FlowTask.story_id.in_(project_story_ids[r.id])
                    )
                )).scalar_one()
                bug_count = (await session.execute(
                    select(func.count()).select_from(FlowBug).where(
                        FlowBug.story_id.in_(project_story_ids[r.id])
                    )
                )).scalar_one()

            items.append({
                **_project_dict(r),
                "story_count": story_count,
                "task_count": task_count,
                "bug_count": bug_count,
            })
    return {"items": items}

@sub_router.get("/projects/{project_id}")
async def get_project(project_id: str):
    sf = get_session_factory()
    async with sf() as session:
        r = await session.get(FlowProject, project_id)
        if not r:
            return {"error": "项目不存在"}, 404
        members_stmt = select(FlowProjectMember).where(FlowProjectMember.project_id == project_id)
        members = (await session.execute(members_stmt)).scalars().all()
    return {
        **_project_dict(r),
        "members": [{"id": m.id, "member_id": m.member_id, "role": m.role,
                      "joined_at": m.joined_at.isoformat() if m.joined_at else None} for m in members],
    }

@sub_router.post("/projects")
async def create_project(body: ProjectCreate):
    sf = get_session_factory()
    async with sf() as session:
        p = FlowProject(
            name=body.name, description=body.description,
            product=body.product, iteration=body.iteration, version=body.version,
            start_date=_parse_dt(body.start_date), end_date=_parse_dt(body.end_date),
        )
        session.add(p)
        await session.flush()
        await _log_event(session, "project", p.id, "created", {"name": body.name})
        await session.commit()
        await session.refresh(p)
    return _project_dict(p)

@sub_router.put("/projects/{project_id}")
async def update_project(project_id: str, body: ProjectUpdate):
    sf = get_session_factory()
    async with sf() as session:
        p = await session.get(FlowProject, project_id)
        if not p:
            return {"error": "项目不存在"}
        changes = {}
        for field in ["name", "description", "product", "iteration", "version"]:
            val = getattr(body, field)
            if val is not None:
                changes[field] = val
                setattr(p, field, val)
        if body.start_date is not None:
            p.start_date = _parse_dt(body.start_date)
            changes["start_date"] = body.start_date
        if body.end_date is not None:
            p.end_date = _parse_dt(body.end_date)
            changes["end_date"] = body.end_date
        if changes:
            await _log_event(session, "project", project_id, "updated", changes)
        await session.commit()
        await session.refresh(p)
    return _project_dict(p)

@sub_router.delete("/projects/{project_id}")
async def delete_project(project_id: str):
    sf = get_session_factory()
    async with sf() as session:
        p = await session.get(FlowProject, project_id)
        if not p:
            return {"error": "项目不存在"}
        await session.execute(sa_delete(FlowProjectMember).where(FlowProjectMember.project_id == project_id))
        await session.delete(p)
        await _log_event(session, "project", project_id, "deleted", {"name": p.name})
        await session.commit()
    return {"ok": True}

# ---- Project Members ----

@sub_router.get("/projects/{project_id}/members")
async def list_project_members(project_id: str):
    sf = get_session_factory()
    async with sf() as session:
        stmt = select(FlowProjectMember).where(FlowProjectMember.project_id == project_id)
        rows = (await session.execute(stmt)).scalars().all()
    return {"items": [{"id": m.id, "member_id": m.member_id, "role": m.role,
                        "joined_at": m.joined_at.isoformat() if m.joined_at else None} for m in rows]}

@sub_router.post("/projects/{project_id}/members")
async def add_project_member(project_id: str, body: ProjectMemberBody):
    sf = get_session_factory()
    async with sf() as session:
        existing = await session.execute(
            select(FlowProjectMember).where(
                FlowProjectMember.project_id == project_id,
                FlowProjectMember.member_id == body.member_id,
            )
        )
        if existing.scalar_one_or_none():
            return {"error": "成员已存在"}
        m = FlowProjectMember(project_id=project_id, member_id=body.member_id, role=body.role)
        session.add(m)
        await _log_event(session, "project", project_id, "member_added",
                         {"member_id": body.member_id, "role": body.role})
        await session.commit()
    return {"ok": True}

@sub_router.delete("/projects/{project_id}/members/{member_id}")
async def remove_project_member(project_id: str, member_id: str):
    sf = get_session_factory()
    async with sf() as session:
        await session.execute(
            sa_delete(FlowProjectMember).where(
                FlowProjectMember.project_id == project_id,
                FlowProjectMember.member_id == member_id,
            )
        )
        await _log_event(session, "project", project_id, "member_removed", {"member_id": member_id})
        await session.commit()
    return {"ok": True}
