import asyncio
import json

from fastapi import APIRouter, Query, Request
from sqlalchemy import func, select, delete as sa_delete

from openvort.db.engine import get_session_factory
from openvort.web.app import require_auth
from openvort.plugins.vortflow.router.helpers import (
    _parse_dt,
    _task_dict,
    _log_event,
    _apply_sort,
    _parse_json_list,
    _resolve_task_story_and_parent,
    _attach_task_links,
)
from openvort.plugins.vortflow.router.schemas import (
    TaskCreate,
    TaskUpdate,
    TransitionBody,
)
from openvort.plugins.vortflow.models import (
    FlowTask,
    FlowStory,
    FlowIterationTask,
)
from openvort.plugins.vortflow.engine import (
    TASK_TRANSITIONS,
    TaskState,
)
from openvort.plugins.vortflow.notifier import notifier as _notifier

sub_router = APIRouter()


# ============ Task CRUD + Transition ============

@sub_router.get("/tasks")
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

@sub_router.get("/tasks/{task_id}")
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

@sub_router.post("/tasks")
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

@sub_router.put("/tasks/{task_id}")
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

@sub_router.delete("/tasks/{task_id}")
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

@sub_router.post("/tasks/{task_id}/transition")
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

@sub_router.get("/tasks/{task_id}/transitions")
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
