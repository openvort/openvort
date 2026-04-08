from fastapi import APIRouter
from sqlalchemy import func, select, delete as sa_delete, update as sa_update, or_

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
from openvort.plugins.vortgit.models import GitRepo

sub_router = APIRouter()


# ============ Project CRUD ============

@sub_router.get("/projects")
async def list_projects():
    sf = get_session_factory()
    async with sf() as session:
        result = await session.execute(select(FlowProject).order_by(FlowProject.created_at.desc()))
        rows = result.scalars().all()

        items = []
        for r in rows:
            story_ids_sub = select(FlowStory.id).where(FlowStory.project_id == r.id)

            story_count = (await session.execute(
                select(func.count()).select_from(FlowStory).where(FlowStory.project_id == r.id)
            )).scalar_one()

            task_count = (await session.execute(
                select(func.count()).select_from(FlowTask).where(
                    or_(FlowTask.project_id == r.id, FlowTask.story_id.in_(story_ids_sub))
                )
            )).scalar_one()

            bug_count = (await session.execute(
                select(func.count()).select_from(FlowBug).where(
                    or_(FlowBug.project_id == r.id, FlowBug.story_id.in_(story_ids_sub))
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
            name=body.name, code=body.code, color=body.color,
            description=body.description,
            product=body.product, iteration=body.iteration, version=body.version,
            owner_id=body.owner_id or None,
            start_date=_parse_dt(body.start_date), end_date=_parse_dt(body.end_date),
        )
        session.add(p)
        await session.flush()

        added_member_ids: set[str] = set()
        if body.owner_id:
            session.add(FlowProjectMember(project_id=p.id, member_id=body.owner_id, role="owner"))
            added_member_ids.add(body.owner_id)

        for mid in body.member_ids:
            if mid not in added_member_ids:
                session.add(FlowProjectMember(project_id=p.id, member_id=mid, role="member"))
                added_member_ids.add(mid)

        if body.repo_ids:
            await session.execute(
                sa_update(GitRepo)
                .where(GitRepo.id.in_(body.repo_ids))
                .values(project_id=p.id)
            )

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
        for field in ["name", "code", "color", "description", "product", "iteration", "version"]:
            val = getattr(body, field)
            if val is not None:
                old_val = getattr(p, field)
                changes[field] = {"from": old_val, "to": val}
                setattr(p, field, val)
        if body.owner_id is not None:
            old_owner_id = p.owner_id
            new_owner_id = body.owner_id or None
            p.owner_id = new_owner_id
            changes["owner_id"] = {"from": old_owner_id, "to": body.owner_id}

            if old_owner_id and old_owner_id != new_owner_id:
                await session.execute(
                    sa_update(FlowProjectMember)
                    .where(FlowProjectMember.project_id == project_id,
                           FlowProjectMember.member_id == old_owner_id,
                           FlowProjectMember.role == "owner")
                    .values(role="member")
                )

            if new_owner_id:
                existing = (await session.execute(
                    select(FlowProjectMember).where(
                        FlowProjectMember.project_id == project_id,
                        FlowProjectMember.member_id == new_owner_id,
                    )
                )).scalar_one_or_none()
                if existing:
                    existing.role = "owner"
                else:
                    session.add(FlowProjectMember(
                        project_id=project_id, member_id=new_owner_id, role="owner"))

        if body.start_date is not None:
            old_val = str(p.start_date) if p.start_date else None
            p.start_date = _parse_dt(body.start_date)
            changes["start_date"] = {"from": old_val, "to": body.start_date}
        if body.end_date is not None:
            old_val = str(p.end_date) if p.end_date else None
            p.end_date = _parse_dt(body.end_date)
            changes["end_date"] = {"from": old_val, "to": body.end_date}
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

        if body.role == "owner":
            p = await session.get(FlowProject, project_id)
            if p:
                old_owner_id = p.owner_id
                p.owner_id = body.member_id
                if old_owner_id and old_owner_id != body.member_id:
                    await session.execute(
                        sa_update(FlowProjectMember)
                        .where(FlowProjectMember.project_id == project_id,
                               FlowProjectMember.member_id == old_owner_id,
                               FlowProjectMember.role == "owner")
                        .values(role="member")
                    )

        await _log_event(session, "project", project_id, "member_added",
                         {"member_id": body.member_id, "role": body.role})
        await session.commit()
    return {"ok": True}

@sub_router.put("/projects/{project_id}/members/{member_id}")
async def update_project_member_role(project_id: str, member_id: str, body: ProjectMemberBody):
    sf = get_session_factory()
    async with sf() as session:
        row = (await session.execute(
            select(FlowProjectMember).where(
                FlowProjectMember.project_id == project_id,
                FlowProjectMember.member_id == member_id,
            )
        )).scalar_one_or_none()
        if not row:
            return {"error": "成员不存在"}, 404
        old_role = row.role
        row.role = body.role
        await _log_event(session, "project", project_id, "member_role_changed",
                         {"member_id": member_id, "old_role": old_role, "new_role": body.role})
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
