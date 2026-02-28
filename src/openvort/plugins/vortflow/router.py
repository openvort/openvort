"""VortFlow FastAPI 子路由"""

from fastapi import APIRouter, Query
from sqlalchemy import func, select

from openvort.db.engine import get_session_factory
from openvort.plugins.vortflow.models import (
    FlowBug,
    FlowEvent,
    FlowMilestone,
    FlowProject,
    FlowStory,
    FlowTask,
)

router = APIRouter(prefix="/api/vortflow", tags=["vortflow"])


@router.get("/projects")
async def list_projects():
    sf = get_session_factory()
    async with sf() as session:
        result = await session.execute(select(FlowProject).order_by(FlowProject.created_at.desc()))
        rows = result.scalars().all()
    return {
        "items": [
            {
                "id": r.id, "name": r.name, "description": r.description,
                "product": r.product, "iteration": r.iteration, "version": r.version,
                "owner_id": r.owner_id,
                "start_date": r.start_date.isoformat() if r.start_date else None,
                "end_date": r.end_date.isoformat() if r.end_date else None,
            }
            for r in rows
        ]
    }


@router.get("/stories")
async def list_stories(
    project_id: str = Query("", description="按项目过滤"),
    state: str = Query("", description="按状态过滤"),
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
        total = (await session.execute(count_stmt)).scalar_one()
        stmt = stmt.offset((page - 1) * page_size).limit(page_size)
        rows = (await session.execute(stmt)).scalars().all()
    return {
        "total": total,
        "items": [
            {
                "id": r.id, "title": r.title, "state": r.state, "priority": r.priority,
                "project_id": r.project_id, "submitter_id": r.submitter_id,
                "pm_id": r.pm_id, "designer_id": r.designer_id, "reviewer_id": r.reviewer_id,
                "deadline": r.deadline.isoformat() if r.deadline else None,
                "created_at": r.created_at.isoformat() if r.created_at else None,
            }
            for r in rows
        ],
    }


@router.get("/tasks")
async def list_tasks(
    story_id: str = Query("", description="按需求过滤"),
    state: str = Query("", description="按状态过滤"),
    assignee_id: str = Query("", description="按负责人过滤"),
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
        if assignee_id:
            stmt = stmt.where(FlowTask.assignee_id == assignee_id)
            count_stmt = count_stmt.where(FlowTask.assignee_id == assignee_id)
        total = (await session.execute(count_stmt)).scalar_one()
        stmt = stmt.offset((page - 1) * page_size).limit(page_size)
        rows = (await session.execute(stmt)).scalars().all()
    return {
        "total": total,
        "items": [
            {
                "id": r.id, "title": r.title, "state": r.state, "task_type": r.task_type,
                "story_id": r.story_id, "assignee_id": r.assignee_id,
                "estimate_hours": r.estimate_hours, "actual_hours": r.actual_hours,
                "deadline": r.deadline.isoformat() if r.deadline else None,
                "created_at": r.created_at.isoformat() if r.created_at else None,
            }
            for r in rows
        ],
    }


@router.get("/bugs")
async def list_bugs(
    story_id: str = Query("", description="按需求过滤"),
    state: str = Query("", description="按状态过滤"),
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
        total = (await session.execute(count_stmt)).scalar_one()
        stmt = stmt.offset((page - 1) * page_size).limit(page_size)
        rows = (await session.execute(stmt)).scalars().all()
    return {
        "total": total,
        "items": [
            {
                "id": r.id, "title": r.title, "state": r.state, "severity": r.severity,
                "story_id": r.story_id, "task_id": r.task_id,
                "reporter_id": r.reporter_id, "assignee_id": r.assignee_id,
                "developer_id": r.developer_id,
                "created_at": r.created_at.isoformat() if r.created_at else None,
            }
            for r in rows
        ],
    }


@router.get("/milestones")
async def list_milestones(
    project_id: str = Query("", description="按项目过滤"),
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
        total = (await session.execute(count_stmt)).scalar_one()
        stmt = stmt.offset((page - 1) * page_size).limit(page_size)
        rows = (await session.execute(stmt)).scalars().all()
    return {
        "total": total,
        "items": [
            {
                "id": r.id, "name": r.name, "project_id": r.project_id,
                "story_id": r.story_id,
                "due_date": r.due_date.isoformat() if r.due_date else None,
                "completed_at": r.completed_at.isoformat() if r.completed_at else None,
                "created_at": r.created_at.isoformat() if r.created_at else None,
            }
            for r in rows
        ],
    }


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
