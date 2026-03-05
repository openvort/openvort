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
    deadline: str | None = None

class StoryUpdate(BaseModel):
    title: str | None = None
    description: str | None = None
    priority: int | None = None
    deadline: str | None = None

class TaskCreate(BaseModel):
    story_id: str
    title: str
    description: str = ""
    task_type: str = "fullstack"
    assignee_id: str | None = None
    estimate_hours: float | None = None
    deadline: str | None = None

class TaskUpdate(BaseModel):
    title: str | None = None
    description: str | None = None
    task_type: str | None = None
    assignee_id: str | None = None
    estimate_hours: float | None = None
    actual_hours: float | None = None
    deadline: str | None = None

class BugCreate(BaseModel):
    story_id: str | None = None
    task_id: str | None = None
    title: str
    description: str = ""
    severity: int = 3
    assignee_id: str | None = None

class BugUpdate(BaseModel):
    title: str | None = None
    description: str | None = None
    severity: int | None = None
    assignee_id: str | None = None

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


# ============ Helpers ============

def _parse_dt(s: str | None) -> datetime | None:
    if not s:
        return None
    try:
        return datetime.fromisoformat(s)
    except ValueError:
        return None

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
        "project_id": r.project_id, "submitter_id": r.submitter_id,
        "pm_id": r.pm_id, "designer_id": r.designer_id, "reviewer_id": r.reviewer_id,
        "deadline": r.deadline.isoformat() if r.deadline else None,
        "created_at": r.created_at.isoformat() if r.created_at else None,
    }

def _task_dict(r: FlowTask) -> dict:
    return {
        "id": r.id, "title": r.title, "description": r.description,
        "state": r.state, "task_type": r.task_type,
        "story_id": r.story_id, "assignee_id": r.assignee_id,
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

async def _log_event(session, entity_type: str, entity_id: str, action: str, detail: dict | None = None):
    ev = FlowEvent(entity_type=entity_type, entity_id=entity_id, action=action,
                   detail=json.dumps(detail or {}, ensure_ascii=False))
    session.add(ev)

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
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
):
    sf = get_session_factory()
    async with sf() as session:
        stmt = select(FlowStory).order_by(FlowStory.created_at.desc())
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
        total = (await session.execute(count_stmt)).scalar_one()
        stmt = stmt.offset((page - 1) * page_size).limit(page_size)
        rows = (await session.execute(stmt)).scalars().all()
    return {"total": total, "items": [_story_dict(r) for r in rows]}

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
    return {**_story_dict(r), "task_count": task_count, "bug_count": bug_count}

@router.post("/stories")
async def create_story(body: StoryCreate):
    sf = get_session_factory()
    async with sf() as session:
        s = FlowStory(
            project_id=body.project_id, title=body.title,
            description=body.description, priority=body.priority,
            deadline=_parse_dt(body.deadline),
        )
        session.add(s)
        await session.flush()
        await _log_event(session, "story", s.id, "created", {"title": body.title})
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
        for field in ["title", "description", "priority"]:
            val = getattr(body, field)
            if val is not None:
                changes[field] = val
                setattr(s, field, val)
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
        # Delete related tasks and bugs
        await session.execute(sa_delete(FlowTask).where(FlowTask.story_id == story_id))
        await session.execute(sa_delete(FlowBug).where(FlowBug.story_id == story_id))
        await session.delete(s)
        await _log_event(session, "story", story_id, "deleted", {"title": s.title})
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
    state: str = Query("", description="按状态过滤"),
    task_type: str = Query("", description="按类型过滤"),
    assignee_id: str = Query("", description="按负责人过滤"),
    keyword: str = Query("", description="关键词搜索"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
):
    sf = get_session_factory()
    async with sf() as session:
        stmt = select(FlowTask).order_by(FlowTask.created_at.desc())
        count_stmt = select(func.count()).select_from(FlowTask)
        if story_id:
            stmt = stmt.where(FlowTask.story_id == story_id)
            count_stmt = count_stmt.where(FlowTask.story_id == story_id)
        if state:
            stmt = stmt.where(FlowTask.state == state)
            count_stmt = count_stmt.where(FlowTask.state == state)
        if task_type:
            stmt = stmt.where(FlowTask.task_type == task_type)
            count_stmt = count_stmt.where(FlowTask.task_type == task_type)
        if assignee_id:
            stmt = stmt.where(FlowTask.assignee_id == assignee_id)
            count_stmt = count_stmt.where(FlowTask.assignee_id == assignee_id)
        if keyword:
            like = f"%{keyword}%"
            stmt = stmt.where(FlowTask.title.ilike(like))
            count_stmt = count_stmt.where(FlowTask.title.ilike(like))
        total = (await session.execute(count_stmt)).scalar_one()
        stmt = stmt.offset((page - 1) * page_size).limit(page_size)
        rows = (await session.execute(stmt)).scalars().all()
    return {"total": total, "items": [_task_dict(r) for r in rows]}

@router.get("/tasks/{task_id}")
async def get_task(task_id: str):
    sf = get_session_factory()
    async with sf() as session:
        r = await session.get(FlowTask, task_id)
        if not r:
            return {"error": "任务不存在"}
    return _task_dict(r)

@router.post("/tasks")
async def create_task(body: TaskCreate):
    sf = get_session_factory()
    async with sf() as session:
        t = FlowTask(
            story_id=body.story_id, title=body.title,
            description=body.description, task_type=body.task_type,
            assignee_id=body.assignee_id, estimate_hours=body.estimate_hours,
            deadline=_parse_dt(body.deadline),
        )
        session.add(t)
        await session.flush()
        await _log_event(session, "task", t.id, "created", {"title": body.title})
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
        for field in ["title", "description", "task_type", "assignee_id", "estimate_hours", "actual_hours"]:
            val = getattr(body, field)
            if val is not None:
                changes[field] = val
                setattr(t, field, val)
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
        await session.delete(t)
        await _log_event(session, "task", task_id, "deleted", {"title": t.title})
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
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
):
    sf = get_session_factory()
    async with sf() as session:
        stmt = select(FlowBug).order_by(FlowBug.created_at.desc())
        count_stmt = select(func.count()).select_from(FlowBug)
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
        for field in ["title", "description", "severity", "assignee_id"]:
            val = getattr(body, field)
            if val is not None:
                changes[field] = val
                setattr(b, field, val)
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
            task_q.where(FlowTask.state.in_(["done", "closed"]))
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
