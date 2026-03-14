"""VortFlow FastAPI 子路由 — 完整 CRUD + 状态流转 + 事件日志"""

import json
from datetime import datetime

from fastapi import APIRouter, Body, Query
from pydantic import BaseModel
from sqlalchemy import func, select, delete as sa_delete

from openvort.db.engine import get_session_factory
from openvort.plugins.vortflow.engine import (
    STORY_TRANSITIONS, TASK_TRANSITIONS, BUG_TRANSITIONS,
    StoryState, TaskState, BugState,
)
from openvort.plugins.vortflow.models import (
    FlowBug, FlowEvent, FlowMilestone, FlowProject,
    FlowProjectMember, FlowStory, FlowTask,
    FlowIteration, FlowVersion,
    FlowIterationStory, FlowIterationTask, FlowVersionStory,
)

router = APIRouter(prefix="/api/vortflow", tags=["vortflow"])


# ============ Pydantic Schemas ============

class ProjectCreate(BaseModel):
    name: str
    description: str = ""
    product: str = ""
    iteration: str = ""
    version: str = ""
    start_date: str | None = None
    end_date: str | None = None

class ProjectUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    product: str | None = None
    iteration: str | None = None
    version: str | None = None
    start_date: str | None = None
    end_date: str | None = None

class StoryCreate(BaseModel):
    project_id: str
    title: str
    description: str = ""
    priority: int = 3
    parent_id: str | None = None
    tags: list[str] = []
    collaborators: list[str] = []
    deadline: str | None = None

class StoryUpdate(BaseModel):
    title: str | None = None
    description: str | None = None
    state: str | None = None
    priority: int | None = None
    parent_id: str | None = None
    tags: list[str] | None = None
    collaborators: list[str] | None = None
    deadline: str | None = None
    pm_id: str | None = None

class TaskCreate(BaseModel):
    story_id: str | None = None
    parent_id: str | None = None
    title: str
    description: str = ""
    task_type: str = "fullstack"
    assignee_id: str | None = None
    creator_id: str | None = None
    tags: list[str] = []
    collaborators: list[str] = []
    estimate_hours: float | None = None
    deadline: str | None = None

class TaskUpdate(BaseModel):
    title: str | None = None
    description: str | None = None
    task_type: str | None = None
    state: str | None = None
    assignee_id: str | None = None
    tags: list[str] | None = None
    collaborators: list[str] | None = None
    estimate_hours: float | None = None
    actual_hours: float | None = None
    deadline: str | None = None

class BugCreate(BaseModel):
    story_id: str | None = None
    task_id: str | None = None
    title: str
    description: str = ""
    severity: int = 3
    tags: list[str] = []
    collaborators: list[str] = []
    assignee_id: str | None = None

class BugUpdate(BaseModel):
    title: str | None = None
    description: str | None = None
    severity: int | None = None
    state: str | None = None
    assignee_id: str | None = None
    tags: list[str] | None = None
    collaborators: list[str] | None = None

class MilestoneCreate(BaseModel):
    project_id: str
    name: str
    description: str = ""
    due_date: str | None = None
    story_id: str | None = None

class MilestoneUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    due_date: str | None = None
    completed_at: str | None = None

class TransitionBody(BaseModel):
    target_state: str

class ProjectMemberBody(BaseModel):
    member_id: str
    role: str = "member"


class IterationCreate(BaseModel):
    project_id: str
    name: str
    goal: str = ""
    owner_id: str | None = None
    start_date: str | None = None
    end_date: str | None = None
    status: str = "planning"
    estimate_hours: float | None = None


class IterationUpdate(BaseModel):
    name: str | None = None
    goal: str | None = None
    owner_id: str | None = None
    start_date: str | None = None
    end_date: str | None = None
    status: str | None = None
    estimate_hours: float | None = None


class VersionCreate(BaseModel):
    project_id: str
    name: str
    description: str = ""
    owner_id: str | None = None
    planned_release_at: str | None = None
    actual_release_at: str | None = None
    progress: int = 0
    release_date: str | None = None  # backward compatibility
    status: str = "planning"


class VersionUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    owner_id: str | None = None
    planned_release_at: str | None = None
    actual_release_at: str | None = None
    progress: int | None = None
    release_date: str | None = None  # backward compatibility
    status: str | None = None


class IterationStoryBody(BaseModel):
    story_id: str
    story_order: int = 0


class IterationTaskBody(BaseModel):
    task_id: str
    task_order: int = 0


class VersionStoryBody(BaseModel):
    story_id: str
    added_reason: str = ""
    story_order: int = 0


# ============ Helpers ============

def _parse_dt(s: str | None) -> datetime | None:
    if not s:
        return None
    try:
        return datetime.fromisoformat(s)
    except ValueError:
        return None


def _parse_json_list(raw: str | None) -> list[str]:
    if not raw:
        return []
    try:
        data = json.loads(raw)
    except Exception:
        return []
    if not isinstance(data, list):
        return []
    result: list[str] = []
    for item in data:
        text = str(item or "").strip()
        if text:
            result.append(text)
    return result

def _project_dict(r: FlowProject) -> dict:
    return {
        "id": r.id, "name": r.name, "description": r.description,
        "product": r.product, "iteration": r.iteration, "version": r.version,
        "owner_id": r.owner_id,
        "start_date": r.start_date.isoformat() if r.start_date else None,
        "end_date": r.end_date.isoformat() if r.end_date else None,
        "created_at": r.created_at.isoformat() if r.created_at else None,
    }

def _story_dict(r: FlowStory) -> dict:
    return {
        "id": r.id, "title": r.title, "description": r.description,
        "state": r.state, "priority": r.priority,
        "parent_id": r.parent_id,
        "project_id": r.project_id, "submitter_id": r.submitter_id,
        "pm_id": r.pm_id, "designer_id": r.designer_id, "reviewer_id": r.reviewer_id,
        "tags": _parse_json_list(r.tags_json),
        "collaborators": _parse_json_list(r.collaborators_json),
        "deadline": r.deadline.isoformat() if r.deadline else None,
        "created_at": r.created_at.isoformat() if r.created_at else None,
    }

def _task_dict(r: FlowTask) -> dict:
    return {
        "id": r.id, "title": r.title, "description": r.description,
        "state": r.state, "task_type": r.task_type,
        "story_id": r.story_id, "parent_id": r.parent_id,
        "assignee_id": r.assignee_id, "creator_id": r.creator_id,
        "tags": _parse_json_list(r.tags_json),
        "collaborators": _parse_json_list(r.collaborators_json),
        "estimate_hours": r.estimate_hours, "actual_hours": r.actual_hours,
        "deadline": r.deadline.isoformat() if r.deadline else None,
        "created_at": r.created_at.isoformat() if r.created_at else None,
    }

def _bug_dict(r: FlowBug) -> dict:
    return {
        "id": r.id, "title": r.title, "description": r.description,
        "state": r.state, "severity": r.severity,
        "story_id": r.story_id, "task_id": r.task_id,
        "reporter_id": r.reporter_id, "assignee_id": r.assignee_id,
        "developer_id": r.developer_id,
        "tags": _parse_json_list(r.tags_json),
        "collaborators": _parse_json_list(r.collaborators_json),
        "created_at": r.created_at.isoformat() if r.created_at else None,
    }

def _milestone_dict(r: FlowMilestone) -> dict:
    return {
        "id": r.id, "name": r.name, "project_id": r.project_id,
        "story_id": r.story_id,
        "due_date": r.due_date.isoformat() if r.due_date else None,
        "completed_at": r.completed_at.isoformat() if r.completed_at else None,
        "created_at": r.created_at.isoformat() if r.created_at else None,
        "description": getattr(r, "description", ""),
    }


def _iteration_dict(r: FlowIteration) -> dict:
    return {
        "id": r.id, "project_id": r.project_id, "name": r.name, "goal": r.goal,
        "owner_id": r.owner_id,
        "start_date": r.start_date.isoformat() if r.start_date else None,
        "end_date": r.end_date.isoformat() if r.end_date else None,
        "status": r.status,
        "estimate_hours": r.estimate_hours,
        "created_at": r.created_at.isoformat() if r.created_at else None,
        "updated_at": r.updated_at.isoformat() if r.updated_at else None,
    }


def _version_dict(r: FlowVersion) -> dict:
    return {
        "id": r.id, "project_id": r.project_id, "name": r.name,
        "description": r.description,
        "owner_id": r.owner_id,
        "planned_release_at": r.planned_release_at.isoformat() if r.planned_release_at else None,
        "actual_release_at": r.actual_release_at.isoformat() if r.actual_release_at else None,
        "progress": r.progress,
        "release_date": r.release_date.isoformat() if r.release_date else None,
        "status": r.status,
        "created_at": r.created_at.isoformat() if r.created_at else None,
        "updated_at": r.updated_at.isoformat() if r.updated_at else None,
    }

async def _log_event(session, entity_type: str, entity_id: str, action: str, detail: dict | None = None):
    ev = FlowEvent(entity_type=entity_type, entity_id=entity_id, action=action,
                   detail=json.dumps(detail or {}, ensure_ascii=False))
    session.add(ev)


async def _validate_story_parent(
    session,
    *,
    project_id: str,
    parent_id: str | None,
    story_id: str | None = None,
) -> tuple[str | None, str | None]:
    normalized_parent_id = (parent_id or "").strip() or None
    if normalized_parent_id is None:
        return None, None
    if story_id and normalized_parent_id == story_id:
        return None, "父需求不能是自身"

    parent = await session.get(FlowStory, normalized_parent_id)
    if not parent:
        return None, "父需求不存在"
    if parent.project_id != project_id:
        return None, "父需求必须和当前需求属于同一个项目"

    if story_id:
        cursor = parent
        while cursor and cursor.parent_id:
            if cursor.parent_id == story_id:
                return None, "不能将需求移动到自己的子需求下"
            cursor = await session.get(FlowStory, cursor.parent_id)

    return normalized_parent_id, None


async def _collect_story_descendant_ids(session, story_ids: list[str]) -> list[str]:
    pending_ids = [story_id for story_id in story_ids if story_id]
    descendant_ids: list[str] = []
    seen: set[str] = set(pending_ids)
    while pending_ids:
        child_rows = (
            await session.execute(select(FlowStory.id).where(FlowStory.parent_id.in_(pending_ids)))
        ).scalars().all()
        next_ids = [child_id for child_id in child_rows if child_id not in seen]
        if not next_ids:
            break
        descendant_ids.extend(next_ids)
        seen.update(next_ids)
        pending_ids = next_ids
    return descendant_ids


async def _resolve_task_story_and_parent(
    session,
    *,
    story_id: str | None,
    parent_id: str | None,
) -> tuple[str | None, str | None, str | None]:
    normalized_story_id = (story_id or "").strip() or None
    normalized_parent_id = (parent_id or "").strip() or None

    parent_task: FlowTask | None = None
    if normalized_parent_id:
        parent_task = await session.get(FlowTask, normalized_parent_id)
        if not parent_task:
            return None, None, "父任务不存在"
        if parent_task.parent_id:
            return None, None, "父任务不能是子任务"

        if normalized_story_id and normalized_story_id != parent_task.story_id:
            return None, None, "子任务必须和父任务属于同一个需求"
        normalized_story_id = parent_task.story_id

    if not normalized_story_id:
        return None, None, "关联需求不能为空"

    story = await session.get(FlowStory, normalized_story_id)
    if not story:
        return None, None, "关联需求不存在"

    return normalized_story_id, normalized_parent_id, None

# ============ Project CRUD ============

@router.get("/projects")
async def list_projects():
    sf = get_session_factory()
    async with sf() as session:
        result = await session.execute(select(FlowProject).order_by(FlowProject.created_at.desc()))
        rows = result.scalars().all()
    return {"items": [_project_dict(r) for r in rows]}

@router.get("/projects/{project_id}")
async def get_project(project_id: str):
    sf = get_session_factory()
    async with sf() as session:
        r = await session.get(FlowProject, project_id)
        if not r:
            return {"error": "项目不存在"}, 404
        # Get members
        members_stmt = select(FlowProjectMember).where(FlowProjectMember.project_id == project_id)
        members = (await session.execute(members_stmt)).scalars().all()
    return {
        **_project_dict(r),
        "members": [{"id": m.id, "member_id": m.member_id, "role": m.role,
                      "joined_at": m.joined_at.isoformat() if m.joined_at else None} for m in members],
    }

@router.post("/projects")
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

@router.put("/projects/{project_id}")
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

@router.delete("/projects/{project_id}")
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

@router.get("/projects/{project_id}/members")
async def list_project_members(project_id: str):
    sf = get_session_factory()
    async with sf() as session:
        stmt = select(FlowProjectMember).where(FlowProjectMember.project_id == project_id)
        rows = (await session.execute(stmt)).scalars().all()
    return {"items": [{"id": m.id, "member_id": m.member_id, "role": m.role,
                        "joined_at": m.joined_at.isoformat() if m.joined_at else None} for m in rows]}

@router.post("/projects/{project_id}/members")
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

@router.delete("/projects/{project_id}/members/{member_id}")
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

# ============ Story CRUD + Transition ============

@router.get("/stories")
async def list_stories(
    project_id: str = Query("", description="按项目过滤"),
    state: str = Query("", description="按状态过滤"),
    keyword: str = Query("", description="关键词搜索"),
    priority: int = Query(0, description="按优先级过滤"),
    parent_id: str | None = Query(None, description="按父需求过滤，root 表示仅顶层需求"),
    submitter_id: str = Query("", description="按创建者过滤"),
    pm_id: str = Query("", description="按负责人过滤"),
    participant_id: str = Query("", description="按参与者过滤（检查 collaborators）"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
):
    sf = get_session_factory()
    async with sf() as session:
        stmt = select(FlowStory).order_by(FlowStory.created_at.desc(), FlowStory.id.desc())
        count_stmt = select(func.count()).select_from(FlowStory)
        if project_id:
            stmt = stmt.where(FlowStory.project_id == project_id)
            count_stmt = count_stmt.where(FlowStory.project_id == project_id)
        if state:
            stmt = stmt.where(FlowStory.state == state)
            count_stmt = count_stmt.where(FlowStory.state == state)
        if keyword:
            like = f"%{keyword}%"
            stmt = stmt.where(FlowStory.title.ilike(like))
            count_stmt = count_stmt.where(FlowStory.title.ilike(like))
        if priority:
            stmt = stmt.where(FlowStory.priority == priority)
            count_stmt = count_stmt.where(FlowStory.priority == priority)
        if parent_id == "root":
            stmt = stmt.where(FlowStory.parent_id.is_(None))
            count_stmt = count_stmt.where(FlowStory.parent_id.is_(None))
        elif parent_id:
            stmt = stmt.where(FlowStory.parent_id == parent_id)
            count_stmt = count_stmt.where(FlowStory.parent_id == parent_id)
        if submitter_id:
            stmt = stmt.where(FlowStory.submitter_id == submitter_id)
            count_stmt = count_stmt.where(FlowStory.submitter_id == submitter_id)
        if pm_id:
            stmt = stmt.where(FlowStory.pm_id == pm_id)
            count_stmt = count_stmt.where(FlowStory.pm_id == pm_id)
        if participant_id:
            like_p = f'%"{participant_id}"%'
            stmt = stmt.where(FlowStory.collaborators_json.like(like_p))
            count_stmt = count_stmt.where(FlowStory.collaborators_json.like(like_p))
        total = (await session.execute(count_stmt)).scalar_one()
        stmt = stmt.offset((page - 1) * page_size).limit(page_size)
        rows = (await session.execute(stmt)).scalars().all()
        story_ids = [row.id for row in rows]
        child_count_map: dict[str, int] = {}
        if story_ids:
            child_count_rows = await session.execute(
                select(FlowStory.parent_id, func.count())
                .where(FlowStory.parent_id.in_(story_ids))
                .group_by(FlowStory.parent_id)
            )
            child_count_map = {
                parent_story_id: child_count
                for parent_story_id, child_count in child_count_rows.all()
                if parent_story_id
            }
    return {
        "total": total,
        "items": [{**_story_dict(r), "children_count": child_count_map.get(r.id, 0)} for r in rows],
    }

@router.get("/stories/{story_id}")
async def get_story(story_id: str):
    sf = get_session_factory()
    async with sf() as session:
        r = await session.get(FlowStory, story_id)
        if not r:
            return {"error": "需求不存在"}
        # Get related tasks and bugs count
        task_count = (await session.execute(
            select(func.count()).select_from(FlowTask).where(FlowTask.story_id == story_id)
        )).scalar_one()
        bug_count = (await session.execute(
            select(func.count()).select_from(FlowBug).where(FlowBug.story_id == story_id)
        )).scalar_one()
        children_count = (await session.execute(
            select(func.count()).select_from(FlowStory).where(FlowStory.parent_id == story_id)
        )).scalar_one()
    return {
        **_story_dict(r),
        "task_count": task_count,
        "bug_count": bug_count,
        "children_count": children_count,
    }

@router.post("/stories")
async def create_story(body: StoryCreate):
    sf = get_session_factory()
    async with sf() as session:
        normalized_parent_id, parent_error = await _validate_story_parent(
            session,
            project_id=body.project_id,
            parent_id=body.parent_id,
        )
        if parent_error:
            return {"error": parent_error}
        s = FlowStory(
            project_id=body.project_id, title=body.title,
            description=body.description, priority=body.priority,
            parent_id=normalized_parent_id,
            tags_json=json.dumps(body.tags or [], ensure_ascii=False),
            collaborators_json=json.dumps(body.collaborators or [], ensure_ascii=False),
            deadline=_parse_dt(body.deadline),
        )
        session.add(s)
        await session.flush()
        await _log_event(
            session,
            "story",
            s.id,
            "created",
            {"title": body.title, "parent_id": normalized_parent_id},
        )
        await session.commit()
        await session.refresh(s)
    return _story_dict(s)

@router.put("/stories/{story_id}")
async def update_story(story_id: str, body: StoryUpdate):
    sf = get_session_factory()
    async with sf() as session:
        s = await session.get(FlowStory, story_id)
        if not s:
            return {"error": "需求不存在"}
        changes = {}
        if body.parent_id is not None:
            normalized_parent_id, parent_error = await _validate_story_parent(
                session,
                project_id=s.project_id,
                parent_id=body.parent_id,
                story_id=story_id,
            )
            if parent_error:
                return {"error": parent_error}
            changes["parent_id"] = normalized_parent_id
            s.parent_id = normalized_parent_id
        for field in ["title", "description", "state", "priority", "pm_id"]:
            val = getattr(body, field)
            if val is not None:
                changes[field] = val
                setattr(s, field, val)
        if body.tags is not None:
            s.tags_json = json.dumps(body.tags, ensure_ascii=False)
            changes["tags"] = body.tags
        if body.collaborators is not None:
            s.collaborators_json = json.dumps(body.collaborators, ensure_ascii=False)
            changes["collaborators"] = body.collaborators
        if body.deadline is not None:
            s.deadline = _parse_dt(body.deadline)
            changes["deadline"] = body.deadline
        if changes:
            await _log_event(session, "story", story_id, "updated", changes)
        await session.commit()
        await session.refresh(s)
    return _story_dict(s)

@router.delete("/stories/{story_id}")
async def delete_story(story_id: str):
    sf = get_session_factory()
    async with sf() as session:
        s = await session.get(FlowStory, story_id)
        if not s:
            return {"error": "需求不存在"}
        descendant_ids = await _collect_story_descendant_ids(session, [story_id])
        target_story_ids = [story_id, *descendant_ids]
        # Delete related tasks and bugs for the full story subtree.
        await session.execute(sa_delete(FlowTask).where(FlowTask.story_id.in_(target_story_ids)))
        await session.execute(sa_delete(FlowBug).where(FlowBug.story_id.in_(target_story_ids)))
        await session.execute(sa_delete(FlowStory).where(FlowStory.id.in_(descendant_ids)))
        await session.delete(s)
        await _log_event(
            session,
            "story",
            story_id,
            "deleted",
            {"title": s.title, "deleted_children": len(descendant_ids)},
        )
        await session.commit()
    return {"ok": True}

@router.post("/stories/{story_id}/transition")
async def transition_story(story_id: str, body: TransitionBody):
    sf = get_session_factory()
    async with sf() as session:
        s = await session.get(FlowStory, story_id)
        if not s:
            return {"error": "需求不存在"}
        try:
            current = StoryState(s.state)
            target = StoryState(body.target_state)
        except ValueError:
            return {"error": f"无效状态: {body.target_state}"}
        allowed = STORY_TRANSITIONS.get(current, [])
        if target not in allowed:
            allowed_names = [t.value for t in allowed]
            return {"error": f"不允许从 {current.value} 转换到 {target.value}，可选: {allowed_names}"}
        old_state = s.state
        s.state = target.value
        await _log_event(session, "story", story_id, "state_changed",
                         {"from": old_state, "to": target.value})
        await session.commit()
        await session.refresh(s)
    return _story_dict(s)

@router.get("/stories/{story_id}/transitions")
async def get_story_transitions(story_id: str):
    """Get allowed next states for a story"""
    sf = get_session_factory()
    async with sf() as session:
        s = await session.get(FlowStory, story_id)
        if not s:
            return {"error": "需求不存在"}
    try:
        current = StoryState(s.state)
    except ValueError:
        return {"transitions": []}
    allowed = STORY_TRANSITIONS.get(current, [])
    return {"current": s.state, "transitions": [t.value for t in allowed]}

# ============ Task CRUD + Transition ============

@router.get("/tasks")
async def list_tasks(
    story_id: str = Query("", description="按需求过滤"),
    parent_id: str | None = Query(None, description="按父任务过滤，root 表示仅顶层任务"),
    state: str = Query("", description="按状态过滤"),
    task_type: str = Query("", description="按类型过滤"),
    assignee_id: str = Query("", description="按负责人过滤"),
    keyword: str = Query("", description="关键词搜索"),
    project_id: str = Query("", description="按项目过滤（通过关联需求）"),
    creator_id: str = Query("", description="按创建者过滤"),
    participant_id: str = Query("", description="按参与者过滤（检查 collaborators）"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
):
    sf = get_session_factory()
    async with sf() as session:
        stmt = select(FlowTask).order_by(FlowTask.created_at.desc(), FlowTask.id.desc())
        count_stmt = select(func.count()).select_from(FlowTask)
        if project_id:
            project_story_ids = select(FlowStory.id).where(FlowStory.project_id == project_id)
            stmt = stmt.where(FlowTask.story_id.in_(project_story_ids))
            count_stmt = count_stmt.where(FlowTask.story_id.in_(project_story_ids))
        if story_id:
            stmt = stmt.where(FlowTask.story_id == story_id)
            count_stmt = count_stmt.where(FlowTask.story_id == story_id)
        if parent_id == "root":
            stmt = stmt.where(FlowTask.parent_id.is_(None))
            count_stmt = count_stmt.where(FlowTask.parent_id.is_(None))
        elif parent_id:
            stmt = stmt.where(FlowTask.parent_id == parent_id)
            count_stmt = count_stmt.where(FlowTask.parent_id == parent_id)
        if state:
            stmt = stmt.where(FlowTask.state == state)
            count_stmt = count_stmt.where(FlowTask.state == state)
        if task_type:
            stmt = stmt.where(FlowTask.task_type == task_type)
            count_stmt = count_stmt.where(FlowTask.task_type == task_type)
        if assignee_id:
            stmt = stmt.where(FlowTask.assignee_id == assignee_id)
            count_stmt = count_stmt.where(FlowTask.assignee_id == assignee_id)
        if creator_id:
            stmt = stmt.where(FlowTask.creator_id == creator_id)
            count_stmt = count_stmt.where(FlowTask.creator_id == creator_id)
        if keyword:
            like = f"%{keyword}%"
            stmt = stmt.where(FlowTask.title.ilike(like))
            count_stmt = count_stmt.where(FlowTask.title.ilike(like))
        if participant_id:
            like_p = f'%"{participant_id}"%'
            stmt = stmt.where(FlowTask.collaborators_json.like(like_p))
            count_stmt = count_stmt.where(FlowTask.collaborators_json.like(like_p))
        total = (await session.execute(count_stmt)).scalar_one()
        stmt = stmt.offset((page - 1) * page_size).limit(page_size)
        rows = (await session.execute(stmt)).scalars().all()
        task_ids = [row.id for row in rows]
        child_count_map: dict[str, int] = {}
        if task_ids:
            child_count_rows = await session.execute(
                select(FlowTask.parent_id, func.count())
                .where(FlowTask.parent_id.in_(task_ids))
                .group_by(FlowTask.parent_id)
            )
            child_count_map = {
                parent_task_id: child_count
                for parent_task_id, child_count in child_count_rows.all()
                if parent_task_id
            }
    return {
        "total": total,
        "items": [{**_task_dict(r), "children_count": child_count_map.get(r.id, 0)} for r in rows],
    }

@router.get("/tasks/{task_id}")
async def get_task(task_id: str):
    sf = get_session_factory()
    async with sf() as session:
        r = await session.get(FlowTask, task_id)
        if not r:
            return {"error": "任务不存在"}
        children_count = (await session.execute(
            select(func.count()).select_from(FlowTask).where(FlowTask.parent_id == task_id)
        )).scalar_one()
    return {**_task_dict(r), "children_count": children_count}

@router.post("/tasks")
async def create_task(body: TaskCreate):
    sf = get_session_factory()
    async with sf() as session:
        resolved_story_id, normalized_parent_id, parent_error = await _resolve_task_story_and_parent(
            session,
            story_id=body.story_id,
            parent_id=body.parent_id,
        )
        if parent_error:
            return {"error": parent_error}
        t = FlowTask(
            story_id=resolved_story_id, parent_id=normalized_parent_id, title=body.title,
            description=body.description, task_type=body.task_type,
            assignee_id=body.assignee_id, creator_id=body.creator_id,
            estimate_hours=body.estimate_hours,
            tags_json=json.dumps(body.tags or [], ensure_ascii=False),
            collaborators_json=json.dumps(body.collaborators or [], ensure_ascii=False),
            deadline=_parse_dt(body.deadline),
        )
        session.add(t)
        await session.flush()
        await _log_event(
            session,
            "task",
            t.id,
            "created",
            {"title": body.title, "story_id": resolved_story_id, "parent_id": normalized_parent_id},
        )
        await session.commit()
        await session.refresh(t)
    return _task_dict(t)

@router.put("/tasks/{task_id}")
async def update_task(task_id: str, body: TaskUpdate):
    sf = get_session_factory()
    async with sf() as session:
        t = await session.get(FlowTask, task_id)
        if not t:
            return {"error": "任务不存在"}
        changes = {}
        for field in ["title", "description", "task_type", "state", "assignee_id", "estimate_hours", "actual_hours"]:
            val = getattr(body, field)
            if val is not None:
                changes[field] = val
                setattr(t, field, val)
        if body.tags is not None:
            t.tags_json = json.dumps(body.tags, ensure_ascii=False)
            changes["tags"] = body.tags
        if body.collaborators is not None:
            t.collaborators_json = json.dumps(body.collaborators, ensure_ascii=False)
            changes["collaborators"] = body.collaborators
        if body.deadline is not None:
            t.deadline = _parse_dt(body.deadline)
            changes["deadline"] = body.deadline
        if changes:
            await _log_event(session, "task", task_id, "updated", changes)
        await session.commit()
        await session.refresh(t)
    return _task_dict(t)

@router.delete("/tasks/{task_id}")
async def delete_task(task_id: str):
    sf = get_session_factory()
    async with sf() as session:
        t = await session.get(FlowTask, task_id)
        if not t:
            return {"error": "任务不存在"}
        child_task_ids = (
            await session.execute(select(FlowTask.id).where(FlowTask.parent_id == task_id))
        ).scalars().all()
        if child_task_ids:
            await session.execute(sa_delete(FlowTask).where(FlowTask.parent_id == task_id))
        await session.delete(t)
        await _log_event(
            session,
            "task",
            task_id,
            "deleted",
            {"title": t.title, "deleted_children": len(child_task_ids)},
        )
        await session.commit()
    return {"ok": True}

@router.post("/tasks/{task_id}/transition")
async def transition_task(task_id: str, body: TransitionBody):
    sf = get_session_factory()
    async with sf() as session:
        t = await session.get(FlowTask, task_id)
        if not t:
            return {"error": "任务不存在"}
        try:
            current = TaskState(t.state)
            target = TaskState(body.target_state)
        except ValueError:
            return {"error": f"无效状态: {body.target_state}"}
        allowed = TASK_TRANSITIONS.get(current, [])
        if target not in allowed:
            return {"error": f"不允许从 {current.value} 转换到 {target.value}，可选: {[s.value for s in allowed]}"}
        old_state = t.state
        t.state = target.value
        await _log_event(session, "task", task_id, "state_changed",
                         {"from": old_state, "to": target.value})
        await session.commit()
        await session.refresh(t)
    return _task_dict(t)

@router.get("/tasks/{task_id}/transitions")
async def get_task_transitions(task_id: str):
    sf = get_session_factory()
    async with sf() as session:
        t = await session.get(FlowTask, task_id)
        if not t:
            return {"error": "任务不存在"}
    try:
        current = TaskState(t.state)
    except ValueError:
        return {"transitions": []}
    allowed = TASK_TRANSITIONS.get(current, [])
    return {"current": t.state, "transitions": [s.value for s in allowed]}

# ============ Bug CRUD + Transition ============

@router.get("/bugs")
async def list_bugs(
    story_id: str = Query("", description="按需求过滤"),
    state: str = Query("", description="按状态过滤"),
    severity: int = Query(0, description="按严重程度过滤"),
    assignee_id: str = Query("", description="按指派人过滤"),
    keyword: str = Query("", description="关键词搜索"),
    project_id: str = Query("", description="按项目过滤（通过关联需求）"),
    reporter_id: str = Query("", description="按报告者过滤"),
    participant_id: str = Query("", description="按参与者过滤（检查 collaborators）"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
):
    sf = get_session_factory()
    async with sf() as session:
        stmt = select(FlowBug).order_by(FlowBug.created_at.desc(), FlowBug.id.desc())
        count_stmt = select(func.count()).select_from(FlowBug)
        if project_id:
            project_story_ids = select(FlowStory.id).where(FlowStory.project_id == project_id)
            stmt = stmt.where(FlowBug.story_id.in_(project_story_ids))
            count_stmt = count_stmt.where(FlowBug.story_id.in_(project_story_ids))
        if story_id:
            stmt = stmt.where(FlowBug.story_id == story_id)
            count_stmt = count_stmt.where(FlowBug.story_id == story_id)
        if state:
            stmt = stmt.where(FlowBug.state == state)
            count_stmt = count_stmt.where(FlowBug.state == state)
        if severity:
            stmt = stmt.where(FlowBug.severity == severity)
            count_stmt = count_stmt.where(FlowBug.severity == severity)
        if assignee_id:
            stmt = stmt.where(FlowBug.assignee_id == assignee_id)
            count_stmt = count_stmt.where(FlowBug.assignee_id == assignee_id)
        if reporter_id:
            stmt = stmt.where(FlowBug.reporter_id == reporter_id)
            count_stmt = count_stmt.where(FlowBug.reporter_id == reporter_id)
        if participant_id:
            like_p = f'%"{participant_id}"%'
            stmt = stmt.where(FlowBug.collaborators_json.like(like_p))
            count_stmt = count_stmt.where(FlowBug.collaborators_json.like(like_p))
        if keyword:
            like = f"%{keyword}%"
            stmt = stmt.where(FlowBug.title.ilike(like))
            count_stmt = count_stmt.where(FlowBug.title.ilike(like))
        total = (await session.execute(count_stmt)).scalar_one()
        stmt = stmt.offset((page - 1) * page_size).limit(page_size)
        rows = (await session.execute(stmt)).scalars().all()
    return {"total": total, "items": [_bug_dict(r) for r in rows]}

@router.get("/bugs/{bug_id}")
async def get_bug(bug_id: str):
    sf = get_session_factory()
    async with sf() as session:
        r = await session.get(FlowBug, bug_id)
        if not r:
            return {"error": "缺陷不存在"}
    return _bug_dict(r)

@router.post("/bugs")
async def create_bug(body: BugCreate):
    sf = get_session_factory()
    async with sf() as session:
        b = FlowBug(
            story_id=body.story_id, task_id=body.task_id,
            title=body.title, description=body.description,
            severity=body.severity, assignee_id=body.assignee_id,
            tags_json=json.dumps(body.tags or [], ensure_ascii=False),
            collaborators_json=json.dumps(body.collaborators or [], ensure_ascii=False),
        )
        session.add(b)
        await session.flush()
        await _log_event(session, "bug", b.id, "created", {"title": body.title})
        await session.commit()
        await session.refresh(b)
    return _bug_dict(b)

@router.put("/bugs/{bug_id}")
async def update_bug(bug_id: str, body: BugUpdate):
    sf = get_session_factory()
    async with sf() as session:
        b = await session.get(FlowBug, bug_id)
        if not b:
            return {"error": "缺陷不存在"}
        changes = {}
        for field in ["title", "description", "severity", "state", "assignee_id"]:
            val = getattr(body, field)
            if val is not None:
                changes[field] = val
                setattr(b, field, val)
        if body.tags is not None:
            b.tags_json = json.dumps(body.tags, ensure_ascii=False)
            changes["tags"] = body.tags
        if body.collaborators is not None:
            b.collaborators_json = json.dumps(body.collaborators, ensure_ascii=False)
            changes["collaborators"] = body.collaborators
        if changes:
            await _log_event(session, "bug", bug_id, "updated", changes)
        await session.commit()
        await session.refresh(b)
    return _bug_dict(b)

@router.delete("/bugs/{bug_id}")
async def delete_bug(bug_id: str):
    sf = get_session_factory()
    async with sf() as session:
        b = await session.get(FlowBug, bug_id)
        if not b:
            return {"error": "缺陷不存在"}
        await session.delete(b)
        await _log_event(session, "bug", bug_id, "deleted", {"title": b.title})
        await session.commit()
    return {"ok": True}

@router.post("/bugs/{bug_id}/transition")
async def transition_bug(bug_id: str, body: TransitionBody):
    sf = get_session_factory()
    async with sf() as session:
        b = await session.get(FlowBug, bug_id)
        if not b:
            return {"error": "缺陷不存在"}
        try:
            current = BugState(b.state)
            target = BugState(body.target_state)
        except ValueError:
            return {"error": f"无效状态: {body.target_state}"}
        allowed = BUG_TRANSITIONS.get(current, [])
        if target not in allowed:
            return {"error": f"不允许从 {current.value} 转换到 {target.value}，可选: {[s.value for s in allowed]}"}
        old_state = b.state
        b.state = target.value
        await _log_event(session, "bug", bug_id, "state_changed",
                         {"from": old_state, "to": target.value})
        await session.commit()
        await session.refresh(b)
    return _bug_dict(b)

@router.get("/bugs/{bug_id}/transitions")
async def get_bug_transitions(bug_id: str):
    sf = get_session_factory()
    async with sf() as session:
        b = await session.get(FlowBug, bug_id)
        if not b:
            return {"error": "缺陷不存在"}
    try:
        current = BugState(b.state)
    except ValueError:
        return {"transitions": []}
    allowed = BUG_TRANSITIONS.get(current, [])
    return {"current": b.state, "transitions": [s.value for s in allowed]}

# ============ Milestone CRUD ============

@router.get("/milestones")
async def list_milestones(
    project_id: str = Query("", description="按项目过滤"),
    keyword: str = Query("", description="关键词搜索"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
):
    sf = get_session_factory()
    async with sf() as session:
        stmt = select(FlowMilestone).order_by(FlowMilestone.due_date.asc().nulls_last())
        count_stmt = select(func.count()).select_from(FlowMilestone)
        if project_id:
            stmt = stmt.where(FlowMilestone.project_id == project_id)
            count_stmt = count_stmt.where(FlowMilestone.project_id == project_id)
        if keyword:
            like = f"%{keyword}%"
            stmt = stmt.where(FlowMilestone.name.ilike(like))
            count_stmt = count_stmt.where(FlowMilestone.name.ilike(like))
        total = (await session.execute(count_stmt)).scalar_one()
        stmt = stmt.offset((page - 1) * page_size).limit(page_size)
        rows = (await session.execute(stmt)).scalars().all()
    return {"total": total, "items": [_milestone_dict(r) for r in rows]}

@router.get("/milestones/{milestone_id}")
async def get_milestone(milestone_id: str):
    sf = get_session_factory()
    async with sf() as session:
        r = await session.get(FlowMilestone, milestone_id)
        if not r:
            return {"error": "里程碑不存在"}
    return _milestone_dict(r)

@router.post("/milestones")
async def create_milestone(body: MilestoneCreate):
    sf = get_session_factory()
    async with sf() as session:
        m = FlowMilestone(
            project_id=body.project_id, name=body.name,
            story_id=body.story_id, due_date=_parse_dt(body.due_date),
        )
        session.add(m)
        await session.flush()
        await _log_event(session, "milestone", m.id, "created", {"name": body.name})
        await session.commit()
        await session.refresh(m)
    return _milestone_dict(m)

@router.put("/milestones/{milestone_id}")
async def update_milestone(milestone_id: str, body: MilestoneUpdate):
    sf = get_session_factory()
    async with sf() as session:
        m = await session.get(FlowMilestone, milestone_id)
        if not m:
            return {"error": "里程碑不存在"}
        changes = {}
        if body.name is not None:
            changes["name"] = body.name
            m.name = body.name
        if body.due_date is not None:
            m.due_date = _parse_dt(body.due_date)
            changes["due_date"] = body.due_date
        if body.completed_at is not None:
            m.completed_at = _parse_dt(body.completed_at)
            changes["completed_at"] = body.completed_at
        if changes:
            await _log_event(session, "milestone", milestone_id, "updated", changes)
        await session.commit()
        await session.refresh(m)
    return _milestone_dict(m)

@router.delete("/milestones/{milestone_id}")
async def delete_milestone(milestone_id: str):
    sf = get_session_factory()
    async with sf() as session:
        m = await session.get(FlowMilestone, milestone_id)
        if not m:
            return {"error": "里程碑不存在"}
        await session.delete(m)
        await _log_event(session, "milestone", milestone_id, "deleted", {"name": m.name})
        await session.commit()
    return {"ok": True}

@router.post("/milestones/{milestone_id}/complete")
async def complete_milestone(milestone_id: str):
    sf = get_session_factory()
    async with sf() as session:
        m = await session.get(FlowMilestone, milestone_id)
        if not m:
            return {"error": "里程碑不存在"}
        m.completed_at = datetime.utcnow()
        await _log_event(session, "milestone", milestone_id, "completed", {"name": m.name})
        await session.commit()
        await session.refresh(m)
    return _milestone_dict(m)


# ============ Event Log ============

@router.get("/events")
async def list_events(
    entity_type: str = Query("", description="实体类型"),
    entity_id: str = Query("", description="实体 ID"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
):
    sf = get_session_factory()
    async with sf() as session:
        stmt = select(FlowEvent).order_by(FlowEvent.created_at.desc())
        count_stmt = select(func.count()).select_from(FlowEvent)
        if entity_type:
            stmt = stmt.where(FlowEvent.entity_type == entity_type)
            count_stmt = count_stmt.where(FlowEvent.entity_type == entity_type)
        if entity_id:
            stmt = stmt.where(FlowEvent.entity_id == entity_id)
            count_stmt = count_stmt.where(FlowEvent.entity_id == entity_id)
        total = (await session.execute(count_stmt)).scalar_one()
        stmt = stmt.offset((page - 1) * page_size).limit(page_size)
        rows = (await session.execute(stmt)).scalars().all()
    return {
        "total": total,
        "items": [
            {
                "id": r.id, "entity_type": r.entity_type, "entity_id": r.entity_id,
                "action": r.action, "actor_id": r.actor_id, "detail": r.detail,
                "created_at": r.created_at.isoformat() if r.created_at else None,
            }
            for r in rows
        ],
    }


# ============ Dashboard Stats ============

@router.get("/dashboard/stats")
async def dashboard_stats(project_id: str = Query("", description="项目 ID")):
    sf = get_session_factory()
    async with sf() as session:
        story_q = select(func.count()).select_from(FlowStory)
        task_q = select(func.count()).select_from(FlowTask).join(
            FlowStory, FlowTask.story_id == FlowStory.id
        )
        bug_q = select(func.count()).select_from(FlowBug).outerjoin(
            FlowStory, FlowBug.story_id == FlowStory.id
        )

        if project_id:
            story_q = story_q.where(FlowStory.project_id == project_id)
            task_q = task_q.where(FlowStory.project_id == project_id)
            bug_q = bug_q.where(FlowStory.project_id == project_id)

        total_stories = (await session.execute(story_q)).scalar_one()
        total_tasks = (await session.execute(task_q)).scalar_one()
        total_bugs = (await session.execute(bug_q)).scalar_one()

        done_stories = (await session.execute(
            story_q.where(FlowStory.state == "done")
        )).scalar_one()
        done_tasks = (await session.execute(
            task_q.where(FlowTask.state == "done")
        )).scalar_one()
        closed_bugs = (await session.execute(
            bug_q.where(FlowBug.state == "closed")
        )).scalar_one()

    return {
        "stories": {"total": total_stories, "done": done_stories},
        "tasks": {"total": total_tasks, "done": done_tasks},
        "bugs": {"total": total_bugs, "closed": closed_bugs},
    }


# ============ AI 生成 ============

@router.get("/generate-description-prompt")
async def generate_vortflow_description(
    entity_type: str = Query(..., description="类型: story/task/bug/milestone"),
    project_name: str = Query("", description="项目名称"),
    title: str = Query("", description="标题"),
):
    """生成 AI 创建 VortFlow 描述内容的 prompt"""
    if entity_type == "story":
        prompt = (
            f"请为需求「{title}」生成专业、详细的需求描述内容。\n\n"
            f"项目：{project_name or '未指定'}\n"
            f"需求标题：{title}\n\n"
            f"请生成完整的需求描述（Markdown 格式），包括：\n"
            f"1. 背景与目标 - 为什么要做这个需求，解决什么问题\n"
            f"2. 功能描述 - 详细的功能点和用户故事\n"
            f"3. 验收标准 - 如何验证需求是否完成\n"
            f"4. 注意事项 - 实现过程中需要关注的点\n\n"
            f"要求：内容要清晰、完整，能帮助开发人员准确理解需求。"
        )
    elif entity_type == "task":
        prompt = (
            f"请为任务「{title}」生成详细的任务描述内容。\n\n"
            f"项目：{project_name or '未指定'}\n"
            f"任务标题：{title}\n\n"
            f"请生成完整的任务描述（Markdown 格式），包括：\n"
            f"1. 任务目标 - 具体要完成什么\n"
            f"2. 实施方案 - 建议的实现方式和技术方案\n"
            f"3. 关联需求 - 关联的需求或 Bug\n"
            f"4. 自测要点 - 如何验证任务完成\n\n"
            f"要求：内容要实用，能指导开发人员快速上手任务。"
        )
    elif entity_type == "bug":
        prompt = (
            f"请为缺陷「{title}」生成详细的缺陷描述内容。\n\n"
            f"项目：{project_name or '未指定'}\n"
            f"缺陷标题：{title}\n\n"
            f"请生成完整的缺陷描述（Markdown 格式），包括：\n"
            f"1. 问题描述 - 缺陷的详细描述\n"
            f"2. 复现步骤 - 一步步如何复现这个问题\n"
            f"3. 预期行为 - 正常应该是什么样子\n"
            f"4. 实际行为 - 实际发生了什么\n"
            f"5. 建议修复方案 - 如何修复这个问题\n\n"
            f"要求：描述要清晰、准确，帮助开发人员快速定位和修复问题。"
        )
    elif entity_type == "milestone":
        prompt = (
            f"请为里程碑「{title}」生成详细的描述内容。\n\n"
            f"项目：{project_name or '未指定'}\n"
            f"里程碑标题：{title}\n\n"
            f"请生成完整的里程碑描述（Markdown 格式），包括：\n"
            f"1. 目标概述 - 这个里程碑要达成什么目标\n"
            f"2. 关键交付物 - 需要完成哪些需求/任务\n"
            f"3. 时间安排 - 计划的时间节点\n"
            f"4. 风险与依赖 - 可能的风险和外部依赖\n\n"
            f"要求：内容要能帮助团队明确里程碑的目标和计划。"
        )
    else:
        prompt = f"请为「{title}」生成描述内容。"

    return {"prompt": prompt}


# ============ Iteration CRUD ============

@router.get("/iterations")
async def list_iterations(
    project_id: str = Query("", description="按项目过滤"),
    status: str = Query("", description="按状态过滤"),
    keyword: str = Query("", description="按名称/目标搜索"),
    owner_id: str = Query("", description="按负责人过滤"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
):
    sf = get_session_factory()
    async with sf() as session:
        stmt = select(FlowIteration).order_by(FlowIteration.start_date.desc().nulls_last())
        count_stmt = select(func.count()).select_from(FlowIteration)
        if project_id:
            stmt = stmt.where(FlowIteration.project_id == project_id)
            count_stmt = count_stmt.where(FlowIteration.project_id == project_id)
        if status:
            stmt = stmt.where(FlowIteration.status == status)
            count_stmt = count_stmt.where(FlowIteration.status == status)
        if keyword:
            like = f"%{keyword}%"
            cond = FlowIteration.name.ilike(like) | FlowIteration.goal.ilike(like)
            stmt = stmt.where(cond)
            count_stmt = count_stmt.where(cond)
        if owner_id:
            stmt = stmt.where(FlowIteration.owner_id == owner_id)
            count_stmt = count_stmt.where(FlowIteration.owner_id == owner_id)
        total = (await session.execute(count_stmt)).scalar_one()
        stmt = stmt.offset((page - 1) * page_size).limit(page_size)
        rows = (await session.execute(stmt)).scalars().all()
    return {"total": total, "items": [_iteration_dict(r) for r in rows]}


@router.get("/iterations/{iteration_id}")
async def get_iteration(iteration_id: str):
    sf = get_session_factory()
    async with sf() as session:
        r = await session.get(FlowIteration, iteration_id)
        if not r:
            return {"error": "迭代不存在"}
    return _iteration_dict(r)


@router.post("/iterations")
async def create_iteration(body: IterationCreate):
    sf = get_session_factory()
    async with sf() as session:
        i = FlowIteration(
            project_id=body.project_id, name=body.name, goal=body.goal,
            owner_id=body.owner_id,
            start_date=_parse_dt(body.start_date), end_date=_parse_dt(body.end_date),
            status=body.status,
            estimate_hours=body.estimate_hours,
        )
        session.add(i)
        await session.flush()
        await _log_event(session, "iteration", i.id, "created", {"name": body.name})
        await session.commit()
        await session.refresh(i)
    return _iteration_dict(i)


@router.put("/iterations/{iteration_id}")
async def update_iteration(iteration_id: str, body: IterationUpdate):
    sf = get_session_factory()
    async with sf() as session:
        i = await session.get(FlowIteration, iteration_id)
        if not i:
            return {"error": "迭代不存在"}
        changes = {}
        for field in ["name", "goal", "status", "owner_id", "estimate_hours"]:
            val = getattr(body, field)
            if val is not None:
                changes[field] = val
                setattr(i, field, val)
        if body.start_date is not None:
            i.start_date = _parse_dt(body.start_date)
            changes["start_date"] = body.start_date
        if body.end_date is not None:
            i.end_date = _parse_dt(body.end_date)
            changes["end_date"] = body.end_date
        if changes:
            await _log_event(session, "iteration", iteration_id, "updated", changes)
        await session.commit()
        await session.refresh(i)
    return _iteration_dict(i)


@router.delete("/iterations/{iteration_id}")
async def delete_iteration(iteration_id: str):
    sf = get_session_factory()
    async with sf() as session:
        i = await session.get(FlowIteration, iteration_id)
        if not i:
            return {"error": "迭代不存在"}
        # Delete related associations
        await session.execute(sa_delete(FlowIterationStory).where(FlowIterationStory.iteration_id == iteration_id))
        await session.execute(sa_delete(FlowIterationTask).where(FlowIterationTask.iteration_id == iteration_id))
        await session.delete(i)
        await _log_event(session, "iteration", iteration_id, "deleted", {"name": i.name})
        await session.commit()
    return {"ok": True}


# ---- Iteration Stories ----

@router.get("/iterations/{iteration_id}/stories")
async def list_iteration_stories(iteration_id: str):
    sf = get_session_factory()
    async with sf() as session:
        stmt = (
            select(FlowIterationStory, FlowStory)
            .join(FlowStory, FlowIterationStory.story_id == FlowStory.id)
            .where(FlowIterationStory.iteration_id == iteration_id)
            .order_by(FlowIterationStory.story_order.asc())
        )
        rows = await session.execute(stmt)
        items = []
        for link, story in rows:
            items.append({
                "link_id": link.id,
                "story_order": link.story_order,
                **_story_dict(story),
            })
    return {"items": items}


@router.post("/iterations/{iteration_id}/stories")
async def add_iteration_story(iteration_id: str, body: IterationStoryBody):
    sf = get_session_factory()
    async with sf() as session:
        # Check if iteration exists
        iteration = await session.get(FlowIteration, iteration_id)
        if not iteration:
            return {"error": "迭代不存在"}
        # Check if story exists
        story = await session.get(FlowStory, body.story_id)
        if not story:
            return {"error": "需求不存在"}
        # Check if already linked
        existing = await session.execute(
            select(FlowIterationStory).where(
                FlowIterationStory.iteration_id == iteration_id,
                FlowIterationStory.story_id == body.story_id,
            )
        )
        if existing.scalar_one_or_none():
            return {"error": "需求已在迭代中"}
        link = FlowIterationStory(
            iteration_id=iteration_id, story_id=body.story_id,
            story_order=body.story_order,
        )
        session.add(link)
        await _log_event(session, "iteration", iteration_id, "story_added",
                         {"story_id": body.story_id})
        await session.commit()
    return {"ok": True}


@router.delete("/iterations/{iteration_id}/stories/{story_id}")
async def remove_iteration_story(iteration_id: str, story_id: str):
    sf = get_session_factory()
    async with sf() as session:
        await session.execute(
            sa_delete(FlowIterationStory).where(
                FlowIterationStory.iteration_id == iteration_id,
                FlowIterationStory.story_id == story_id,
            )
        )
        await _log_event(session, "iteration", iteration_id, "story_removed",
                         {"story_id": story_id})
        await session.commit()
    return {"ok": True}


# ---- Iteration Tasks ----

@router.get("/iterations/{iteration_id}/tasks")
async def list_iteration_tasks(iteration_id: str):
    sf = get_session_factory()
    async with sf() as session:
        stmt = (
            select(FlowIterationTask, FlowTask)
            .join(FlowTask, FlowIterationTask.task_id == FlowTask.id)
            .where(FlowIterationTask.iteration_id == iteration_id)
            .order_by(FlowIterationTask.task_order.asc())
        )
        rows = await session.execute(stmt)
        items = []
        for link, task in rows:
            items.append({
                "link_id": link.id,
                "task_order": link.task_order,
                **_task_dict(task),
            })
    return {"items": items}


@router.post("/iterations/{iteration_id}/tasks")
async def add_iteration_task(iteration_id: str, body: IterationTaskBody):
    sf = get_session_factory()
    async with sf() as session:
        iteration = await session.get(FlowIteration, iteration_id)
        if not iteration:
            return {"error": "迭代不存在"}
        task = await session.get(FlowTask, body.task_id)
        if not task:
            return {"error": "任务不存在"}
        existing = await session.execute(
            select(FlowIterationTask).where(
                FlowIterationTask.iteration_id == iteration_id,
                FlowIterationTask.task_id == body.task_id,
            )
        )
        if existing.scalar_one_or_none():
            return {"error": "任务已在迭代中"}
        link = FlowIterationTask(
            iteration_id=iteration_id, task_id=body.task_id,
            task_order=body.task_order,
        )
        session.add(link)
        await _log_event(session, "iteration", iteration_id, "task_added",
                         {"task_id": body.task_id})
        await session.commit()
    return {"ok": True}


@router.delete("/iterations/{iteration_id}/tasks/{task_id}")
async def remove_iteration_task(iteration_id: str, task_id: str):
    sf = get_session_factory()
    async with sf() as session:
        await session.execute(
            sa_delete(FlowIterationTask).where(
                FlowIterationTask.iteration_id == iteration_id,
                FlowIterationTask.task_id == task_id,
            )
        )
        await _log_event(session, "iteration", iteration_id, "task_removed",
                         {"task_id": task_id})
        await session.commit()
    return {"ok": True}


# ============ Version CRUD ============

@router.get("/versions")
async def list_versions(
    project_id: str = Query("", description="按项目过滤"),
    status: str = Query("", description="按状态过滤"),
    keyword: str = Query("", description="按版本号/名称搜索"),
    owner_id: str = Query("", description="按负责人过滤"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
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


@router.get("/versions/{version_id}")
async def get_version(version_id: str):
    sf = get_session_factory()
    async with sf() as session:
        r = await session.get(FlowVersion, version_id)
        if not r:
            return {"error": "版本不存在"}
    return _version_dict(r)


@router.post("/versions")
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


@router.put("/versions/{version_id}")
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
                if field == "progress":
                    val = max(0, min(100, int(val)))
                changes[field] = val
                setattr(v, field, val)
        if body.planned_release_at is not None or body.release_date is not None:
            planned = _parse_dt(body.planned_release_at) if body.planned_release_at is not None else _parse_dt(body.release_date)
            v.planned_release_at = planned
            v.release_date = planned
            changes["planned_release_at"] = body.planned_release_at or body.release_date
        if body.actual_release_at is not None:
            v.actual_release_at = _parse_dt(body.actual_release_at)
            changes["actual_release_at"] = body.actual_release_at
        if changes:
            await _log_event(session, "version", version_id, "updated", changes)
        await session.commit()
        await session.refresh(v)
    return _version_dict(v)


@router.delete("/versions/{version_id}")
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


@router.post("/versions/{version_id}/release")
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

@router.get("/versions/{version_id}/stories")
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


@router.post("/versions/{version_id}/stories")
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


@router.delete("/versions/{version_id}/stories/{story_id}")
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
