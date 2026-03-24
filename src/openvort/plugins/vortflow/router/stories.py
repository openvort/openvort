import json

from fastapi import APIRouter, Query, Request
from sqlalchemy import func, select, delete as sa_delete

from openvort.db.engine import get_session_factory
from openvort.web.app import require_auth
from openvort.plugins.vortflow.router.helpers import (
    _parse_dt,
    _story_dict,
    _log_event,
    _apply_sort,
    _parse_json_list,
    _validate_story_parent,
    _collect_story_descendant_ids,
    _attach_story_links,
)
from openvort.plugins.vortflow.router.schemas import (
    StoryCreate,
    StoryUpdate,
    TransitionBody,
)
from openvort.plugins.vortflow.models import (
    FlowStory,
    FlowTask,
    FlowBug,
    FlowIterationStory,
)
from openvort.plugins.vortflow.engine import (
    STORY_TRANSITIONS,
    StoryState,
)
from openvort.plugins.vortflow.notifier import notifier as _notifier, schedule_notification

sub_router = APIRouter()


# ============ Story CRUD + Transition ============

@sub_router.get("/stories")
async def list_stories(
    project_id: str = Query("", description="按项目过滤"),
    state: str = Query("", description="按状态过滤"),
    keyword: str = Query("", description="关键词搜索"),
    priority: int = Query(0, description="按优先级过滤"),
    parent_id: str | None = Query(None, description="按父需求过滤，root 表示仅顶层需求"),
    submitter_id: str = Query("", description="按创建者过滤"),
    assignee_id: str = Query("", description="按负责人过滤"),
    pm_id: str = Query("", description="按产品经理过滤"),
    participant_id: str = Query("", description="按参与者过滤（检查 collaborators）"),
    iteration_id: str = Query("", description="按迭代过滤"),
    sort_by: str = Query("", description="排序字段"),
    sort_order: str = Query("desc", description="排序方向 asc/desc"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=200),
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
        if assignee_id:
            stmt = stmt.where(FlowStory.assignee_id == assignee_id)
            count_stmt = count_stmt.where(FlowStory.assignee_id == assignee_id)
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

@sub_router.get("/stories/{story_id}")
async def get_story(story_id: str):
    sf = get_session_factory()
    async with sf() as session:
        r = await session.get(FlowStory, story_id)
        if not r:
            return {"error": "需求不存在"}
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

@sub_router.post("/stories")
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
            assignee_id=body.assignee_id or None,
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
            actor_id=member_id,
        )
        await session.commit()
        await session.refresh(s)
    schedule_notification(_notifier.notify_item_created(
        "story", s.id, s.title, s.project_id, member_id,
        assignee_id=body.assignee_id,
        collaborator_ids=body.collaborators,
    ))
    return _story_dict(s)

@sub_router.put("/stories/{story_id}")
async def update_story(story_id: str, body: StoryUpdate, request: Request):
    payload = require_auth(request)
    actor_id = payload.get("sub", "")
    sf = get_session_factory()
    async with sf() as session:
        s = await session.get(FlowStory, story_id)
        if not s:
            return {"error": "需求不存在"}
        old_pm_id = s.pm_id
        old_assignee_id = getattr(s, "assignee_id", None)
        old_priority = s.priority
        old_collaborators = _parse_json_list(s.collaborators_json)
        old_deadline = str(s.deadline) if s.deadline else None
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
        for field in ["title", "description", "state", "priority", "assignee_id", "pm_id", "project_id"]:
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
            await _log_event(session, "story", story_id, "updated", changes, actor_id=actor_id)
        await session.commit()
        await session.refresh(s)
        project_id = s.project_id or ""
        collaborators = _parse_json_list(s.collaborators_json)
    if body.assignee_id and body.assignee_id != old_assignee_id:
        schedule_notification(_notifier.notify_assignment(
            "story", story_id, s.title, actor_id, body.assignee_id,
            project_id=project_id,
        ))
    if body.pm_id and body.pm_id != old_pm_id:
        schedule_notification(_notifier.notify_assignment(
            "story", story_id, s.title, actor_id, body.pm_id,
            project_id=project_id,
        ))
    if body.collaborators is not None:
        new_ids = [c for c in body.collaborators if c not in old_collaborators]
        if new_ids:
            schedule_notification(_notifier.notify_collaborator_added(
                "story", story_id, s.title, project_id, actor_id, new_ids,
            ))
    field_changes: dict[str, tuple] = {}
    if "priority" in changes and body.priority != old_priority:
        field_changes["priority"] = (old_priority, body.priority)
    if "deadline" in changes and str(body.deadline) != old_deadline:
        field_changes["deadline"] = (old_deadline, body.deadline)
    if field_changes:
        schedule_notification(_notifier.notify_field_changes(
            "story", story_id, s.title, project_id, actor_id, field_changes,
            assignee_id=getattr(s, "assignee_id", None) or s.pm_id,
            creator_id=s.submitter_id,
            collaborator_ids=collaborators,
        ))
    return _story_dict(s)

@sub_router.delete("/stories/{story_id}")
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

@sub_router.post("/stories/{story_id}/transition")
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
        await _log_event(
            session,
            "story",
            story_id,
            "state_changed",
            {"from": old_state, "to": target.value},
            actor_id=actor_id,
        )
        await session.commit()
        await session.refresh(s)
    schedule_notification(_notifier.notify_state_change(
        "story", story_id, s.title, actor_id,
        old_state, target.value,
        assignee_id=getattr(s, "assignee_id", None) or s.pm_id,
        collaborator_ids=collaborators,
        creator_id=s.submitter_id,
        project_id=s.project_id or "",
    ))
    return _story_dict(s)

@sub_router.post("/stories/{story_id}/copy")
async def copy_story(story_id: str, request: Request):
    payload = require_auth(request)
    member_id = payload.get("sub", "")
    sf = get_session_factory()
    async with sf() as session:
        src = await session.get(FlowStory, story_id)
        if not src:
            return {"error": "需求不存在"}
        new_story = FlowStory(
            project_id=src.project_id,
            title=f"{src.title} (副本)",
            description=src.description,
            priority=src.priority,
            parent_id=src.parent_id,
            submitter_id=member_id or None,
            assignee_id=getattr(src, "assignee_id", None),
            tags_json=src.tags_json,
            collaborators_json=src.collaborators_json,
            deadline=src.deadline,
        )
        session.add(new_story)
        await session.flush()

        iter_row = (await session.execute(
            select(FlowIterationStory.iteration_id)
            .where(FlowIterationStory.story_id == story_id)
            .limit(1)
        )).scalar()
        if iter_row:
            session.add(FlowIterationStory(iteration_id=iter_row, story_id=new_story.id))

        from openvort.plugins.vortflow.models import FlowVersionStory
        ver_row = (await session.execute(
            select(FlowVersionStory.version_id)
            .where(FlowVersionStory.story_id == story_id)
            .limit(1)
        )).scalar()
        if ver_row:
            session.add(FlowVersionStory(version_id=ver_row, story_id=new_story.id))

        await _log_event(session, "story", new_story.id, "created",
                         {"title": new_story.title, "copied_from": story_id}, actor_id=member_id)
        await session.commit()
        await session.refresh(new_story)
    return _story_dict(new_story)

@sub_router.get("/stories/{story_id}/transitions")
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
