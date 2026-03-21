"""Iteration CRUD, Iteration Stories & Tasks."""

from fastapi import APIRouter, Query
from sqlalchemy import func, select, delete as sa_delete

from openvort.db.engine import get_session_factory
from openvort.plugins.vortflow.models import (
    FlowIteration, FlowIterationStory, FlowIterationTask, FlowIterationBug,
    FlowStory, FlowTask, FlowBug,
)
from .helpers import _iteration_dict, _log_event, _parse_dt, _story_dict, _task_dict, _bug_dict
from .schemas import (
    IterationCreate, IterationUpdate, IterationStoryBody, IterationTaskBody, IterationBugBody,
)

sub_router = APIRouter()


# ============ Iteration CRUD ============

@sub_router.get("/iterations")
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
        bug_stats: dict[str, dict[str, int]] = {}
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
            for iter_id, cnt in (await session.execute(
                select(FlowIterationBug.iteration_id, func.count())
                .where(FlowIterationBug.iteration_id.in_(iter_ids))
                .group_by(FlowIterationBug.iteration_id)
            )):
                bug_stats.setdefault(iter_id, {"total": 0, "done": 0})["total"] = cnt
            for iter_id, cnt in (await session.execute(
                select(FlowIterationBug.iteration_id, func.count())
                .join(FlowBug, FlowIterationBug.bug_id == FlowBug.id)
                .where(FlowIterationBug.iteration_id.in_(iter_ids), FlowBug.state == "closed")
                .group_by(FlowIterationBug.iteration_id)
            )):
                bug_stats.setdefault(iter_id, {"total": 0, "done": 0})["done"] = cnt

        items = []
        for r in rows:
            d = _iteration_dict(r)
            s = story_stats.get(r.id, {"total": 0, "done": 0})
            t = task_stats.get(r.id, {"total": 0, "done": 0})
            b = bug_stats.get(r.id, {"total": 0, "done": 0})
            d["work_item_total"] = s["total"] + t["total"] + b["total"]
            d["work_item_done"] = s["done"] + t["done"] + b["done"]
            items.append(d)
    return {"total": total, "items": items}


@sub_router.get("/iterations/{iteration_id}")
async def get_iteration(iteration_id: str):
    sf = get_session_factory()
    async with sf() as session:
        r = await session.get(FlowIteration, iteration_id)
        if not r:
            return {"error": "迭代不存在"}
    return _iteration_dict(r)


@sub_router.post("/iterations")
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


@sub_router.put("/iterations/{iteration_id}")
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


@sub_router.delete("/iterations/{iteration_id}")
async def delete_iteration(iteration_id: str):
    sf = get_session_factory()
    async with sf() as session:
        i = await session.get(FlowIteration, iteration_id)
        if not i:
            return {"error": "迭代不存在"}
        await session.execute(sa_delete(FlowIterationStory).where(FlowIterationStory.iteration_id == iteration_id))
        await session.execute(sa_delete(FlowIterationTask).where(FlowIterationTask.iteration_id == iteration_id))
        await session.execute(sa_delete(FlowIterationBug).where(FlowIterationBug.iteration_id == iteration_id))
        await session.delete(i)
        await _log_event(session, "iteration", iteration_id, "deleted", {"name": i.name})
        await session.commit()
    return {"ok": True}


# ---- Iteration Stories ----

@sub_router.get("/iterations/{iteration_id}/stories")
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


@sub_router.post("/iterations/{iteration_id}/stories")
async def add_iteration_story(iteration_id: str, body: IterationStoryBody):
    sf = get_session_factory()
    async with sf() as session:
        iteration = await session.get(FlowIteration, iteration_id)
        if not iteration:
            return {"error": "迭代不存在"}
        story = await session.get(FlowStory, body.story_id)
        if not story:
            return {"error": "需求不存在"}
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


@sub_router.delete("/iterations/{iteration_id}/stories/{story_id}")
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

@sub_router.get("/iterations/{iteration_id}/tasks")
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


@sub_router.post("/iterations/{iteration_id}/tasks")
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


@sub_router.delete("/iterations/{iteration_id}/tasks/{task_id}")
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


# ---- Iteration Bugs ----

@sub_router.post("/iterations/{iteration_id}/bugs")
async def add_iteration_bug(iteration_id: str, body: IterationBugBody):
    sf = get_session_factory()
    async with sf() as session:
        iteration = await session.get(FlowIteration, iteration_id)
        if not iteration:
            return {"error": "迭代不存在"}
        bug = await session.get(FlowBug, body.bug_id)
        if not bug:
            return {"error": "缺陷不存在"}
        existing = await session.execute(
            select(FlowIterationBug).where(
                FlowIterationBug.iteration_id == iteration_id,
                FlowIterationBug.bug_id == body.bug_id,
            )
        )
        if existing.scalar_one_or_none():
            return {"error": "缺陷已在迭代中"}
        link = FlowIterationBug(
            iteration_id=iteration_id, bug_id=body.bug_id,
            bug_order=body.bug_order,
        )
        session.add(link)
        await _log_event(session, "iteration", iteration_id, "bug_added",
                         {"bug_id": body.bug_id})
        await session.commit()
    return {"ok": True}


@sub_router.delete("/iterations/{iteration_id}/bugs/{bug_id}")
async def remove_iteration_bug(iteration_id: str, bug_id: str):
    sf = get_session_factory()
    async with sf() as session:
        await session.execute(
            sa_delete(FlowIterationBug).where(
                FlowIterationBug.iteration_id == iteration_id,
                FlowIterationBug.bug_id == bug_id,
            )
        )
        await _log_event(session, "iteration", iteration_id, "bug_removed",
                         {"bug_id": bug_id})
        await session.commit()
    return {"ok": True}
