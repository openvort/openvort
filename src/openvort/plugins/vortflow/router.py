"""VortFlow FastAPI 子路由 — 完整 CRUD + 状态流转 + 事件日志"""

import asyncio
import json
from datetime import datetime

from fastapi import APIRouter, Body, Query, Request
from pydantic import BaseModel
from sqlalchemy import func, or_, select, delete as sa_delete

from openvort.db.engine import get_session_factory
from openvort.plugins.vortflow.notifier import notifier as _notifier
from openvort.web.app import require_auth
from openvort.plugins.vortflow.engine import (
    STORY_TRANSITIONS, TASK_TRANSITIONS, BUG_TRANSITIONS,
    StoryState, TaskState, BugState,
)
from openvort.plugins.vortflow.models import (
    FlowBug, FlowComment, FlowEvent, FlowMilestone, FlowProject,
    FlowProjectMember, FlowStory, FlowTask,
    FlowIteration, FlowVersion,
    FlowIterationStory, FlowIterationTask, FlowVersionStory,
    FlowView, FlowColumnSetting, FlowWorkItemLink,
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
    project_id: str | None = None
    start_at: str | None = None
    end_at: str | None = None
    repo_id: str | None = None
    branch: str | None = None

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
    start_at: str | None = None
    end_at: str | None = None
    repo_id: str | None = None
    branch: str | None = None

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
    estimate_hours: float | None = None
    actual_hours: float | None = None
    deadline: str | None = None
    start_at: str | None = None
    end_at: str | None = None
    repo_id: str | None = None
    branch: str | None = None

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
        "start_at": r.start_at.isoformat() if getattr(r, "start_at", None) else None,
        "end_at": r.end_at.isoformat() if getattr(r, "end_at", None) else None,
        "repo_id": getattr(r, "repo_id", None) or "",
        "branch": getattr(r, "branch", None) or "",
        "created_at": r.created_at.isoformat() if r.created_at else None,
        "updated_at": r.updated_at.isoformat() if r.updated_at else None,
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
        "start_at": r.start_at.isoformat() if getattr(r, "start_at", None) else None,
        "end_at": r.end_at.isoformat() if getattr(r, "end_at", None) else None,
        "repo_id": getattr(r, "repo_id", None) or "",
        "branch": getattr(r, "branch", None) or "",
        "created_at": r.created_at.isoformat() if r.created_at else None,
        "updated_at": r.updated_at.isoformat() if r.updated_at else None,
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
        "estimate_hours": getattr(r, "estimate_hours", None),
        "actual_hours": getattr(r, "actual_hours", None),
        "deadline": r.deadline.isoformat() if getattr(r, "deadline", None) else None,
        "start_at": r.start_at.isoformat() if getattr(r, "start_at", None) else None,
        "end_at": r.end_at.isoformat() if getattr(r, "end_at", None) else None,
        "repo_id": getattr(r, "repo_id", None) or "",
        "branch": getattr(r, "branch", None) or "",
        "created_at": r.created_at.isoformat() if r.created_at else None,
        "updated_at": r.updated_at.isoformat() if r.updated_at else None,
    }


async def _attach_story_links(session, items: list[dict]) -> list[dict]:
    story_ids = [str(item.get("id") or "").strip() for item in items if item.get("id")]
    if not story_ids:
        return items

    iteration_rows = await session.execute(
        select(FlowIterationStory.story_id, FlowIteration.id, FlowIteration.name)
        .join(FlowIteration, FlowIteration.id == FlowIterationStory.iteration_id)
        .where(FlowIterationStory.story_id.in_(story_ids))
    )
    story_iteration_map: dict[str, tuple[str, str]] = {}
    for story_id, iteration_id, iteration_name in iteration_rows.all():
        sid = str(story_id or "")
        if sid and sid not in story_iteration_map:
            story_iteration_map[sid] = (str(iteration_id or ""), str(iteration_name or ""))

    version_rows = await session.execute(
        select(FlowVersionStory.story_id, FlowVersion.id, FlowVersion.name)
        .join(FlowVersion, FlowVersion.id == FlowVersionStory.version_id)
        .where(FlowVersionStory.story_id.in_(story_ids))
    )
    story_version_map: dict[str, tuple[str, str]] = {}
    for story_id, version_id, version_name in version_rows.all():
        sid = str(story_id or "")
        if sid and sid not in story_version_map:
            story_version_map[sid] = (str(version_id or ""), str(version_name or ""))

    # Milestone links (story_id on FlowMilestone)
    milestone_rows = await session.execute(
        select(FlowMilestone.story_id, FlowMilestone.id, FlowMilestone.name)
        .where(FlowMilestone.story_id.in_(story_ids))
    )
    story_milestone_map: dict[str, tuple[str, str]] = {}
    for ms_story_id, ms_id, ms_name in milestone_rows.all():
        msid = str(ms_story_id or "")
        if msid and msid not in story_milestone_map:
            story_milestone_map[msid] = (str(ms_id or ""), str(ms_name or ""))

    for item in items:
        sid = str(item.get("id") or "").strip()
        iteration = story_iteration_map.get(sid)
        version = story_version_map.get(sid)
        milestone = story_milestone_map.get(sid)
        item["iteration_id"] = iteration[0] if iteration else ""
        item["iteration_name"] = iteration[1] if iteration else ""
        item["version_id"] = version[0] if version else ""
        item["version_name"] = version[1] if version else ""
        item["milestone_id"] = milestone[0] if milestone else ""
        item["milestone_name"] = milestone[1] if milestone else ""
    return items


async def _attach_task_links(session, items: list[dict]) -> list[dict]:
    task_ids = [str(item.get("id") or "").strip() for item in items if item.get("id")]
    if not task_ids:
        return items

    iteration_rows = await session.execute(
        select(FlowIterationTask.task_id, FlowIteration.id, FlowIteration.name)
        .join(FlowIteration, FlowIteration.id == FlowIterationTask.iteration_id)
        .where(FlowIterationTask.task_id.in_(task_ids))
    )
    task_iteration_map: dict[str, tuple[str, str]] = {}
    for task_id, iteration_id, iteration_name in iteration_rows.all():
        tid = str(task_id or "")
        if tid and tid not in task_iteration_map:
            task_iteration_map[tid] = (str(iteration_id or ""), str(iteration_name or ""))

    for item in items:
        tid = str(item.get("id") or "").strip()
        iteration = task_iteration_map.get(tid)
        item["iteration_id"] = iteration[0] if iteration else ""
        item["iteration_name"] = iteration[1] if iteration else ""
    return items


async def _attach_bug_links(session, items: list[dict]) -> list[dict]:
    story_ids = [str(item.get("story_id") or "").strip() for item in items if item.get("story_id")]
    if not story_ids:
        return items

    story_items = [{"id": story_id} for story_id in story_ids]
    await _attach_story_links(session, story_items)
    story_map = {str(item["id"]): item for item in story_items}

    for item in items:
        linked_story = story_map.get(str(item.get("story_id") or "").strip())
        item["iteration_id"] = str((linked_story or {}).get("iteration_id") or "")
        item["iteration_name"] = str((linked_story or {}).get("iteration_name") or "")
        item["version_id"] = str((linked_story or {}).get("version_id") or "")
        item["version_name"] = str((linked_story or {}).get("version_name") or "")
    return items

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

def _apply_sort(stmt, model, sort_by: str, sort_order: str, default_col=None):
    """Apply dynamic sorting to a SQLAlchemy select statement."""
    col = getattr(model, sort_by, None) if sort_by else None
    if col is not None:
        order_fn = col.asc() if sort_order == "asc" else col.desc()
        return stmt.order_by(order_fn, model.id.desc())
    if default_col is not None:
        return stmt.order_by(default_col.desc(), model.id.desc())
    return stmt.order_by(model.created_at.desc(), model.id.desc())


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
    iteration_id: str = Query("", description="按迭代过滤"),
    sort_by: str = Query("", description="排序字段"),
    sort_order: str = Query("desc", description="排序方向 asc/desc"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
):
    sf = get_session_factory()
    async with sf() as session:
        stmt = _apply_sort(select(FlowStory), FlowStory, sort_by, sort_order, FlowStory.created_at)
        count_stmt = select(func.count()).select_from(FlowStory)
        if iteration_id == "__unplanned__":
            planned_ids = select(FlowIterationStory.story_id)
            stmt = stmt.where(~FlowStory.id.in_(planned_ids))
            count_stmt = count_stmt.where(~FlowStory.id.in_(planned_ids))
        elif iteration_id:
            iter_story_ids = select(FlowIterationStory.story_id).where(FlowIterationStory.iteration_id == iteration_id)
            stmt = stmt.where(FlowStory.id.in_(iter_story_ids))
            count_stmt = count_stmt.where(FlowStory.id.in_(iter_story_ids))
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
        items = [{**_story_dict(r), "children_count": child_count_map.get(r.id, 0)} for r in rows]
        await _attach_story_links(session, items)
    return {
        "total": total,
        "items": items,
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
        items = await _attach_story_links(session, [{
            **_story_dict(r),
            "task_count": task_count,
            "bug_count": bug_count,
            "children_count": children_count,
        }])
    return items[0]

@router.post("/stories")
async def create_story(body: StoryCreate, request: Request):
    payload = require_auth(request)
    member_id = payload.get("sub", "")
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
            submitter_id=member_id or None,
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
    asyncio.create_task(_notifier.notify_item_created(
        "story", s.id, s.title, s.project_id, member_id,
        collaborator_ids=body.collaborators,
    ))
    return _story_dict(s)

@router.put("/stories/{story_id}")
async def update_story(story_id: str, body: StoryUpdate, request: Request):
    payload = require_auth(request)
    actor_id = payload.get("sub", "")
    sf = get_session_factory()
    async with sf() as session:
        s = await session.get(FlowStory, story_id)
        if not s:
            return {"error": "需求不存在"}
        old_pm_id = s.pm_id
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
        for field in ["title", "description", "state", "priority", "pm_id", "project_id"]:
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
        if body.start_at is not None:
            s.start_at = _parse_dt(body.start_at)
            changes["start_at"] = body.start_at
        if body.end_at is not None:
            s.end_at = _parse_dt(body.end_at)
            changes["end_at"] = body.end_at
        if body.repo_id is not None:
            s.repo_id = body.repo_id or None
            changes["repo_id"] = body.repo_id
        if body.branch is not None:
            s.branch = body.branch
            changes["branch"] = body.branch
        if changes:
            await _log_event(session, "story", story_id, "updated", changes)
        await session.commit()
        await session.refresh(s)
    if body.pm_id and body.pm_id != old_pm_id:
        asyncio.create_task(_notifier.notify_assignment(
            "story", story_id, s.title, actor_id, body.pm_id,
        ))
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
async def transition_story(story_id: str, body: TransitionBody, request: Request):
    payload = require_auth(request)
    actor_id = payload.get("sub", "")
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
        collaborators = _parse_json_list(s.collaborators_json)
        await _log_event(session, "story", story_id, "state_changed",
                         {"from": old_state, "to": target.value})
        await session.commit()
        await session.refresh(s)
    asyncio.create_task(_notifier.notify_state_change(
        "story", story_id, s.title, actor_id,
        old_state, target.value,
        assignee_id=s.pm_id,
        collaborator_ids=collaborators,
        creator_id=s.submitter_id,
    ))
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
    iteration_id: str = Query("", description="按迭代过滤"),
    sort_by: str = Query("", description="排序字段"),
    sort_order: str = Query("desc", description="排序方向 asc/desc"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
):
    sf = get_session_factory()
    async with sf() as session:
        stmt = _apply_sort(select(FlowTask), FlowTask, sort_by, sort_order, FlowTask.created_at)
        count_stmt = select(func.count()).select_from(FlowTask)
        if iteration_id == "__unplanned__":
            planned_ids = select(FlowIterationTask.task_id)
            stmt = stmt.where(~FlowTask.id.in_(planned_ids))
            count_stmt = count_stmt.where(~FlowTask.id.in_(planned_ids))
        elif iteration_id:
            iter_task_ids = select(FlowIterationTask.task_id).where(FlowIterationTask.iteration_id == iteration_id)
            stmt = stmt.where(FlowTask.id.in_(iter_task_ids))
            count_stmt = count_stmt.where(FlowTask.id.in_(iter_task_ids))
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
        items = [{**_task_dict(r), "children_count": child_count_map.get(r.id, 0)} for r in rows]
        await _attach_task_links(session, items)
    return {
        "total": total,
        "items": items,
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
        items = await _attach_task_links(session, [{**_task_dict(r), "children_count": children_count}])
    return items[0]

@router.post("/tasks")
async def create_task(body: TaskCreate, request: Request):
    payload = require_auth(request)
    member_id = payload.get("sub", "")
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
            assignee_id=body.assignee_id, creator_id=member_id or body.creator_id,
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
    asyncio.create_task(_notifier.notify_item_created(
        "task", t.id, t.title, resolved_story_id or "", member_id,
        assignee_id=body.assignee_id,
        collaborator_ids=body.collaborators,
    ))
    return _task_dict(t)

@router.put("/tasks/{task_id}")
async def update_task(task_id: str, body: TaskUpdate, request: Request):
    payload = require_auth(request)
    actor_id = payload.get("sub", "")
    sf = get_session_factory()
    async with sf() as session:
        t = await session.get(FlowTask, task_id)
        if not t:
            return {"error": "任务不存在"}
        old_assignee_id = t.assignee_id
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
        if body.start_at is not None:
            t.start_at = _parse_dt(body.start_at)
            changes["start_at"] = body.start_at
        if body.end_at is not None:
            t.end_at = _parse_dt(body.end_at)
            changes["end_at"] = body.end_at
        if body.repo_id is not None:
            t.repo_id = body.repo_id or None
            changes["repo_id"] = body.repo_id
        if body.branch is not None:
            t.branch = body.branch
            changes["branch"] = body.branch
        if changes:
            await _log_event(session, "task", task_id, "updated", changes)
        await session.commit()
        await session.refresh(t)
    if body.assignee_id and body.assignee_id != old_assignee_id:
        asyncio.create_task(_notifier.notify_assignment(
            "task", task_id, t.title, actor_id, body.assignee_id,
        ))
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
async def transition_task(task_id: str, body: TransitionBody, request: Request):
    payload = require_auth(request)
    actor_id = payload.get("sub", "")
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
        collaborators = _parse_json_list(t.collaborators_json)
        await _log_event(session, "task", task_id, "state_changed",
                         {"from": old_state, "to": target.value})
        await session.commit()
        await session.refresh(t)
    asyncio.create_task(_notifier.notify_state_change(
        "task", task_id, t.title, actor_id,
        old_state, target.value,
        assignee_id=t.assignee_id,
        collaborator_ids=collaborators,
        creator_id=t.creator_id,
    ))
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
    iteration_id: str = Query("", description="按迭代过滤（通过迭代关联的需求）"),
    sort_by: str = Query("", description="排序字段"),
    sort_order: str = Query("desc", description="排序方向 asc/desc"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
):
    sf = get_session_factory()
    async with sf() as session:
        stmt = _apply_sort(select(FlowBug), FlowBug, sort_by, sort_order, FlowBug.created_at)
        count_stmt = select(func.count()).select_from(FlowBug)
        if iteration_id == "__unplanned__":
            planned_story_ids = select(FlowIterationStory.story_id)
            unplanned_cond = or_(
                FlowBug.story_id.is_(None),
                FlowBug.story_id == "",
                ~FlowBug.story_id.in_(planned_story_ids),
            )
            stmt = stmt.where(unplanned_cond)
            count_stmt = count_stmt.where(unplanned_cond)
        elif iteration_id:
            iter_story_ids = select(FlowIterationStory.story_id).where(FlowIterationStory.iteration_id == iteration_id)
            stmt = stmt.where(FlowBug.story_id.in_(iter_story_ids))
            count_stmt = count_stmt.where(FlowBug.story_id.in_(iter_story_ids))
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
        items = [_bug_dict(r) for r in rows]
        await _attach_bug_links(session, items)
    return {"total": total, "items": items}

@router.get("/bugs/{bug_id}")
async def get_bug(bug_id: str):
    sf = get_session_factory()
    async with sf() as session:
        r = await session.get(FlowBug, bug_id)
        if not r:
            return {"error": "缺陷不存在"}
        items = await _attach_bug_links(session, [_bug_dict(r)])
    return items[0]

@router.post("/bugs")
async def create_bug(body: BugCreate, request: Request):
    payload = require_auth(request)
    member_id = payload.get("sub", "")
    sf = get_session_factory()
    async with sf() as session:
        b = FlowBug(
            story_id=body.story_id, task_id=body.task_id,
            title=body.title, description=body.description,
            severity=body.severity, assignee_id=body.assignee_id,
            reporter_id=member_id or None,
            tags_json=json.dumps(body.tags or [], ensure_ascii=False),
            collaborators_json=json.dumps(body.collaborators or [], ensure_ascii=False),
        )
        session.add(b)
        await session.flush()
        await _log_event(session, "bug", b.id, "created", {"title": body.title})
        await session.commit()
        await session.refresh(b)
    asyncio.create_task(_notifier.notify_item_created(
        "bug", b.id, b.title, body.story_id or "", member_id,
        assignee_id=body.assignee_id,
        collaborator_ids=body.collaborators,
    ))
    return _bug_dict(b)

@router.put("/bugs/{bug_id}")
async def update_bug(bug_id: str, body: BugUpdate, request: Request):
    payload = require_auth(request)
    actor_id = payload.get("sub", "")
    sf = get_session_factory()
    async with sf() as session:
        b = await session.get(FlowBug, bug_id)
        if not b:
            return {"error": "缺陷不存在"}
        old_assignee_id = b.assignee_id
        changes = {}
        for field in ["title", "description", "severity", "state", "assignee_id", "estimate_hours", "actual_hours"]:
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
        if body.deadline is not None:
            b.deadline = _parse_dt(body.deadline)
            changes["deadline"] = body.deadline
        if body.start_at is not None:
            b.start_at = _parse_dt(body.start_at)
            changes["start_at"] = body.start_at
        if body.end_at is not None:
            b.end_at = _parse_dt(body.end_at)
            changes["end_at"] = body.end_at
        if body.repo_id is not None:
            b.repo_id = body.repo_id or None
            changes["repo_id"] = body.repo_id
        if body.branch is not None:
            b.branch = body.branch
            changes["branch"] = body.branch
        if changes:
            await _log_event(session, "bug", bug_id, "updated", changes)
        await session.commit()
        await session.refresh(b)
    if body.assignee_id and body.assignee_id != old_assignee_id:
        asyncio.create_task(_notifier.notify_assignment(
            "bug", bug_id, b.title, actor_id, body.assignee_id,
        ))
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
async def transition_bug(bug_id: str, body: TransitionBody, request: Request):
    payload = require_auth(request)
    actor_id = payload.get("sub", "")
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
        collaborators = _parse_json_list(b.collaborators_json)
        await _log_event(session, "bug", bug_id, "state_changed",
                         {"from": old_state, "to": target.value})
        await session.commit()
        await session.refresh(b)
    asyncio.create_task(_notifier.notify_state_change(
        "bug", bug_id, b.title, actor_id,
        old_state, target.value,
        assignee_id=b.assignee_id,
        collaborator_ids=collaborators,
        creator_id=b.reporter_id,
    ))
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
    page_size: int = Query(20, ge=1, le=200),
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

        iter_ids = [r.id for r in rows]
        story_stats: dict[str, dict[str, int]] = {}
        task_stats: dict[str, dict[str, int]] = {}
        if iter_ids:
            for iter_id, cnt in (await session.execute(
                select(FlowIterationStory.iteration_id, func.count())
                .where(FlowIterationStory.iteration_id.in_(iter_ids))
                .group_by(FlowIterationStory.iteration_id)
            )):
                story_stats.setdefault(iter_id, {"total": 0, "done": 0})["total"] = cnt
            for iter_id, cnt in (await session.execute(
                select(FlowIterationStory.iteration_id, func.count())
                .join(FlowStory, FlowIterationStory.story_id == FlowStory.id)
                .where(FlowIterationStory.iteration_id.in_(iter_ids), FlowStory.state == "done")
                .group_by(FlowIterationStory.iteration_id)
            )):
                story_stats.setdefault(iter_id, {"total": 0, "done": 0})["done"] = cnt
            for iter_id, cnt in (await session.execute(
                select(FlowIterationTask.iteration_id, func.count())
                .where(FlowIterationTask.iteration_id.in_(iter_ids))
                .group_by(FlowIterationTask.iteration_id)
            )):
                task_stats.setdefault(iter_id, {"total": 0, "done": 0})["total"] = cnt
            for iter_id, cnt in (await session.execute(
                select(FlowIterationTask.iteration_id, func.count())
                .join(FlowTask, FlowIterationTask.task_id == FlowTask.id)
                .where(FlowIterationTask.iteration_id.in_(iter_ids), FlowTask.state == "done")
                .group_by(FlowIterationTask.iteration_id)
            )):
                task_stats.setdefault(iter_id, {"total": 0, "done": 0})["done"] = cnt

        items = []
        for r in rows:
            d = _iteration_dict(r)
            s = story_stats.get(r.id, {"total": 0, "done": 0})
            t = task_stats.get(r.id, {"total": 0, "done": 0})
            d["work_item_total"] = s["total"] + t["total"]
            d["work_item_done"] = s["done"] + t["done"]
            items.append(d)
    return {"total": total, "items": items}


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


# ============ Custom Views CRUD ============

class ViewCreate(BaseModel):
    name: str
    work_item_type: str  # 需求/任务/缺陷
    scope: str = "personal"  # personal/shared
    filters: dict = {}
    columns: list = []

class ViewUpdate(BaseModel):
    name: str | None = None
    filters: dict | None = None
    columns: list | None = None
    view_order: int | None = None

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

@router.get("/views")
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

@router.post("/views")
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

@router.put("/views/{view_id}")
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

@router.delete("/views/{view_id}")
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

class ColumnSettingBody(BaseModel):
    work_item_type: str  # 需求/任务/缺陷
    columns: list  # [{"key":"workNo","visible":true}, ...]

@router.get("/column-settings")
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

@router.put("/column-settings")
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


# ============ Comments & Activity ============

class CommentCreate(BaseModel):
    content: str
    mentions: list[str] = []

@router.get("/comments/{entity_type}/{entity_id}")
async def list_comments(entity_type: str, entity_id: str):
    sf = get_session_factory()
    async with sf() as session:
        stmt = (
            select(FlowComment)
            .where(FlowComment.entity_type == entity_type, FlowComment.entity_id == entity_id)
            .order_by(FlowComment.created_at.asc())
        )
        rows = (await session.execute(stmt)).scalars().all()
    return {"items": [
        {
            "id": r.id, "entity_type": r.entity_type, "entity_id": r.entity_id,
            "author_id": r.author_id, "content": r.content,
            "mentions": _parse_json_list(r.mentions_json),
            "created_at": r.created_at.isoformat() if r.created_at else None,
            "updated_at": r.updated_at.isoformat() if r.updated_at else None,
        }
        for r in rows
    ]}

@router.post("/comments/{entity_type}/{entity_id}")
async def create_comment(entity_type: str, entity_id: str, body: CommentCreate, request: Request):
    payload = require_auth(request)
    member_id = payload.get("sub", "")
    sf = get_session_factory()
    async with sf() as session:
        c = FlowComment(
            entity_type=entity_type,
            entity_id=entity_id,
            author_id=member_id,
            content=body.content,
            mentions_json=json.dumps(body.mentions or [], ensure_ascii=False),
        )
        session.add(c)
        await _log_event(session, entity_type, entity_id, "comment_added",
                         {"author_id": member_id, "preview": body.content[:100]})
        await session.commit()
        await session.refresh(c)
    return {
        "id": c.id, "entity_type": c.entity_type, "entity_id": c.entity_id,
        "author_id": c.author_id, "content": c.content,
        "mentions": _parse_json_list(c.mentions_json),
        "created_at": c.created_at.isoformat() if c.created_at else None,
        "updated_at": c.updated_at.isoformat() if c.updated_at else None,
    }

@router.get("/activity/{entity_type}/{entity_id}")
async def list_activity(entity_type: str, entity_id: str, page: int = Query(1, ge=1), page_size: int = Query(50, ge=1, le=200)):
    sf = get_session_factory()
    async with sf() as session:
        stmt = (
            select(FlowEvent)
            .where(FlowEvent.entity_type == entity_type, FlowEvent.entity_id == entity_id)
            .order_by(FlowEvent.created_at.desc())
            .offset((page - 1) * page_size).limit(page_size)
        )
        rows = (await session.execute(stmt)).scalars().all()
    return {"items": [
        {
            "id": r.id, "entity_type": r.entity_type, "entity_id": r.entity_id,
            "action": r.action, "actor_id": r.actor_id,
            "detail": r.detail,
            "created_at": r.created_at.isoformat() if r.created_at else None,
        }
        for r in rows
    ]}


# ============ Work Item Links ============

_LINK_TYPE_MODEL = {"story": FlowStory, "task": FlowTask, "bug": FlowBug}
_LINK_TYPE_DICT = {"story": _story_dict, "task": _task_dict, "bug": _bug_dict}


class WorkItemLinkCreate(BaseModel):
    source_type: str  # story/task/bug
    source_id: str
    target_type: str  # story/task/bug
    target_id: str


@router.get("/work-item-links")
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


@router.post("/work-item-links")
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


@router.delete("/work-item-links/{link_id}")
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
