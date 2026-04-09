"""VortFlow Dashboard stats."""

from fastapi import APIRouter, Query
from sqlalchemy import func, select, or_

from openvort.db.engine import get_session_factory
from openvort.plugins.vortflow.models import FlowStory, FlowTask, FlowBug
from openvort.plugins.vortflow.engine import (
    STORY_DONE_STATES, TASK_DONE_STATES, BUG_CLOSED_STATES,
)

sub_router = APIRouter()


@sub_router.get("/dashboard/stats")
async def dashboard_stats(
    project_id: str = Query("", description="Optional project filter"),
):
    sf = get_session_factory()
    async with sf() as session:
        story_where = [FlowStory.is_archived.is_not(True)]
        task_where = [FlowTask.is_archived.is_not(True)]
        bug_where = [FlowBug.is_archived.is_not(True)]

        if project_id:
            story_where.append(FlowStory.project_id == project_id)
            task_where.append(
                or_(FlowTask.project_id == project_id, FlowTask.story_id.in_(
                    select(FlowStory.id).where(FlowStory.project_id == project_id)
                ))
            )
            bug_where.append(
                or_(FlowBug.project_id == project_id, FlowBug.story_id.in_(
                    select(FlowStory.id).where(FlowStory.project_id == project_id)
                ))
            )

        story_total = (await session.execute(
            select(func.count()).select_from(FlowStory).where(*story_where)
        )).scalar_one()
        story_done = (await session.execute(
            select(func.count()).select_from(FlowStory)
            .where(*story_where, FlowStory.state.in_(STORY_DONE_STATES))
        )).scalar_one()

        task_total = (await session.execute(
            select(func.count()).select_from(FlowTask).where(*task_where)
        )).scalar_one()
        task_done = (await session.execute(
            select(func.count()).select_from(FlowTask)
            .where(*task_where, FlowTask.state.in_(TASK_DONE_STATES))
        )).scalar_one()

        bug_total = (await session.execute(
            select(func.count()).select_from(FlowBug).where(*bug_where)
        )).scalar_one()
        bug_closed = (await session.execute(
            select(func.count()).select_from(FlowBug)
            .where(*bug_where, FlowBug.state.in_(BUG_CLOSED_STATES))
        )).scalar_one()

    return {
        "stories": {"total": story_total, "done": story_done},
        "tasks": {"total": task_total, "done": task_done},
        "bugs": {"total": bug_total, "closed": bug_closed},
    }
