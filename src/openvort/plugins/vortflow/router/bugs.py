import json

from fastapi import APIRouter, Query, Request
from sqlalchemy import func, or_, select

from openvort.db.engine import get_session_factory
from openvort.web.app import require_auth
from openvort.plugins.vortflow.router.helpers import (
    _parse_dt,
    _bug_dict,
    _log_event,
    _apply_sort,
    _parse_json_list,
    _attach_bug_links,
)
from openvort.plugins.vortflow.router.schemas import (
    BugCreate,
    BugUpdate,
    TransitionBody,
)
from openvort.plugins.vortflow.models import (
    FlowBug,
    FlowStory,
    FlowIteration,
    FlowIterationStory,
    FlowIterationBug,
)
from openvort.plugins.vortflow.engine import (
    BUG_TRANSITIONS,
    BugState,
)
from openvort.plugins.vortflow.notifier import notifier as _notifier, schedule_notification

sub_router = APIRouter()


# ============ Bug CRUD + Transition ============

@sub_router.get("/bugs")
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
            planned_bug_ids = select(FlowIterationBug.bug_id)
            unplanned_cond = or_(
                FlowBug.story_id.is_(None),
                FlowBug.story_id == "",
                ~FlowBug.story_id.in_(planned_story_ids),
            )
            stmt = stmt.where(unplanned_cond, ~FlowBug.id.in_(planned_bug_ids))
            count_stmt = count_stmt.where(unplanned_cond, ~FlowBug.id.in_(planned_bug_ids))
        elif iteration_id:
            iter_story_ids = select(FlowIterationStory.story_id).where(FlowIterationStory.iteration_id == iteration_id)
            direct_bug_ids = select(FlowIterationBug.bug_id).where(FlowIterationBug.iteration_id == iteration_id)
            iter_cond = or_(
                FlowBug.story_id.in_(iter_story_ids),
                FlowBug.id.in_(direct_bug_ids),
            )
            stmt = stmt.where(iter_cond)
            count_stmt = count_stmt.where(iter_cond)
        if project_id:
            project_story_ids = select(FlowStory.id).where(FlowStory.project_id == project_id)
            project_cond = or_(
                FlowBug.project_id == project_id,
                FlowBug.story_id.in_(project_story_ids),
            )
            stmt = stmt.where(project_cond)
            count_stmt = count_stmt.where(project_cond)
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

        bug_ids = [i["id"] for i in items if i.get("id")]
        if bug_ids:
            iter_links = (await session.execute(
                select(FlowIterationBug.bug_id, FlowIteration.id, FlowIteration.name)
                .join(FlowIteration, FlowIteration.id == FlowIterationBug.iteration_id)
                .where(FlowIterationBug.bug_id.in_(bug_ids))
            )).all()
            bug_iter_map: dict[str, tuple[str, str]] = {}
            for bug_id, iter_id, iter_name in iter_links:
                bid = str(bug_id or "")
                if bid and bid not in bug_iter_map:
                    bug_iter_map[bid] = (str(iter_id or ""), str(iter_name or ""))
            for item in items:
                link = bug_iter_map.get(item["id"])
                if link:
                    item["iteration_id"] = link[0]
                    item["iteration_name"] = link[1]

    return {"total": total, "items": items}

@sub_router.get("/bugs/{bug_id}")
async def get_bug(bug_id: str):
    sf = get_session_factory()
    async with sf() as session:
        r = await session.get(FlowBug, bug_id)
        if not r:
            return {"error": "缺陷不存在"}
        items = await _attach_bug_links(session, [_bug_dict(r)])
        iter_row = (await session.execute(
            select(FlowIteration.id, FlowIteration.name)
            .join(FlowIterationBug, FlowIteration.id == FlowIterationBug.iteration_id)
            .where(FlowIterationBug.bug_id == bug_id)
            .limit(1)
        )).first()
        if iter_row:
            items[0]["iteration_id"] = str(iter_row[0] or "")
            items[0]["iteration_name"] = str(iter_row[1] or "")
    return items[0]

@sub_router.post("/bugs")
async def create_bug(body: BugCreate, request: Request):
    payload = require_auth(request)
    member_id = payload.get("sub", "")
    sf = get_session_factory()
    async with sf() as session:
        project_id = body.project_id or None
        if not project_id and body.story_id:
            story = await session.get(FlowStory, body.story_id)
            if story:
                project_id = story.project_id
        b = FlowBug(
            project_id=project_id,
            story_id=body.story_id, task_id=body.task_id,
            title=body.title, description=body.description,
            severity=body.severity, assignee_id=body.assignee_id,
            reporter_id=member_id or None,
            deadline=_parse_dt(body.deadline) if body.deadline else None,
            tags_json=json.dumps(body.tags or [], ensure_ascii=False),
            collaborators_json=json.dumps(body.collaborators or [], ensure_ascii=False),
        )
        session.add(b)
        await session.flush()
        await _log_event(session, "bug", b.id, "created", {"title": body.title}, actor_id=member_id)
        await session.commit()
        await session.refresh(b)
    schedule_notification(_notifier.notify_item_created(
        "bug", b.id, b.title, project_id or "", member_id,
        assignee_id=body.assignee_id,
        collaborator_ids=body.collaborators,
    ))
    return _bug_dict(b)

@sub_router.put("/bugs/{bug_id}")
async def update_bug(bug_id: str, body: BugUpdate, request: Request):
    payload = require_auth(request)
    actor_id = payload.get("sub", "")
    sf = get_session_factory()
    async with sf() as session:
        b = await session.get(FlowBug, bug_id)
        if not b:
            return {"error": "缺陷不存在"}
        old_assignee_id = b.assignee_id
        old_severity = b.severity
        old_collaborators = _parse_json_list(b.collaborators_json)
        old_deadline = str(b.deadline) if b.deadline else None
        changes = {}
        if body.project_id is not None:
            b.project_id = body.project_id or None
            changes["project_id"] = body.project_id
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
            await _log_event(session, "bug", bug_id, "updated", changes, actor_id=actor_id)
        await session.commit()
        await session.refresh(b)
        project_id = b.project_id or ""
        collaborators = _parse_json_list(b.collaborators_json)
    if body.assignee_id and body.assignee_id != old_assignee_id:
        schedule_notification(_notifier.notify_assignment(
            "bug", bug_id, b.title, actor_id, body.assignee_id,
            project_id=project_id,
        ))
    if body.collaborators is not None:
        new_ids = [c for c in body.collaborators if c not in old_collaborators]
        if new_ids:
            schedule_notification(_notifier.notify_collaborator_added(
                "bug", bug_id, b.title, project_id, actor_id, new_ids,
            ))
    field_changes: dict[str, tuple] = {}
    if "severity" in changes and body.severity != old_severity:
        field_changes["severity"] = (old_severity, body.severity)
    if "deadline" in changes and str(body.deadline) != old_deadline:
        field_changes["deadline"] = (old_deadline, body.deadline)
    if field_changes:
        schedule_notification(_notifier.notify_field_changes(
            "bug", bug_id, b.title, project_id, actor_id, field_changes,
            assignee_id=b.assignee_id, creator_id=b.reporter_id,
            collaborator_ids=collaborators,
        ))
    return _bug_dict(b)

@sub_router.delete("/bugs/{bug_id}")
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

@sub_router.post("/bugs/{bug_id}/transition")
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
                         {"from": old_state, "to": target.value}, actor_id=actor_id)
        await session.commit()
        await session.refresh(b)
    schedule_notification(_notifier.notify_state_change(
        "bug", bug_id, b.title, actor_id,
        old_state, target.value,
        assignee_id=b.assignee_id,
        collaborator_ids=collaborators,
        creator_id=b.reporter_id,
        project_id=b.project_id or "",
    ))
    return _bug_dict(b)

@sub_router.post("/bugs/{bug_id}/copy")
async def copy_bug(bug_id: str, request: Request):
    payload = require_auth(request)
    member_id = payload.get("sub", "")
    sf = get_session_factory()
    async with sf() as session:
        src = await session.get(FlowBug, bug_id)
        if not src:
            return {"error": "缺陷不存在"}
        new_bug = FlowBug(
            project_id=src.project_id,
            story_id=src.story_id,
            task_id=src.task_id,
            title=f"{src.title} (副本)",
            description=src.description,
            severity=src.severity,
            assignee_id=src.assignee_id,
            reporter_id=member_id or None,
            tags_json=src.tags_json,
            collaborators_json=src.collaborators_json,
            deadline=src.deadline,
        )
        session.add(new_bug)
        await session.flush()

        iter_row = (await session.execute(
            select(FlowIterationBug.iteration_id)
            .where(FlowIterationBug.bug_id == bug_id)
            .limit(1)
        )).scalar()
        if iter_row:
            session.add(FlowIterationBug(iteration_id=iter_row, bug_id=new_bug.id))

        await _log_event(session, "bug", new_bug.id, "created",
                         {"title": new_bug.title, "copied_from": bug_id}, actor_id=member_id)
        await session.commit()
        await session.refresh(new_bug)
    return _bug_dict(new_bug)

@sub_router.get("/bugs/{bug_id}/transitions")
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
