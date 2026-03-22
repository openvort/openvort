"""
VortFlow implementation of the ProjectProvider slot.
"""

from __future__ import annotations

from datetime import datetime
from typing import Callable

from sqlalchemy import select, func as sa_func

from openvort.plugin.slots import ProjectInfo, TasksSummary, WorkItemInfo


class VortFlowProjectProvider:
    """ProjectProvider backed by VortFlow ORM models."""

    def __init__(self, db_factory_getter: Callable):
        self._sf = db_factory_getter

    async def list_projects(self, member_id: str = "") -> list[ProjectInfo]:
        from openvort.plugins.vortflow.models import FlowProject, FlowProjectMember

        sf = self._sf()
        async with sf() as session:
            if member_id:
                stmt = (
                    select(FlowProject)
                    .join(FlowProjectMember, FlowProjectMember.project_id == FlowProject.id)
                    .where(FlowProjectMember.member_id == member_id)
                    .order_by(FlowProject.created_at.desc())
                )
            else:
                stmt = select(FlowProject).order_by(FlowProject.created_at.desc())

            result = await session.execute(stmt)
            rows = result.scalars().all()

        return [
            ProjectInfo(id=p.id, name=p.name, description=p.description or "")
            for p in rows
        ]

    async def get_project(self, project_id: str) -> ProjectInfo | None:
        from openvort.plugins.vortflow.models import FlowProject

        sf = self._sf()
        async with sf() as session:
            project = await session.get(FlowProject, project_id)
            if not project:
                return None
            return ProjectInfo(
                id=project.id,
                name=project.name,
                description=project.description or "",
            )

    async def get_work_item(self, item_type: str, item_id: str) -> WorkItemInfo | None:
        from openvort.plugins.vortflow.models import FlowBug, FlowStory, FlowTask

        model_map = {"story": FlowStory, "task": FlowTask, "bug": FlowBug}
        model = model_map.get(item_type)
        if not model:
            return None

        sf = self._sf()
        async with sf() as session:
            row = await session.get(model, item_id)
            if not row:
                return None

            extra: dict = {}
            if item_type == "bug":
                extra["severity"] = getattr(row, "severity", None)
                extra["steps"] = getattr(row, "steps", "")
            if item_type == "task":
                extra["task_type"] = getattr(row, "task_type", "")

            return WorkItemInfo(
                id=row.id,
                title=row.title,
                type=item_type,
                status=getattr(row, "state", ""),
                assignee=getattr(row, "assignee_id", "") or "",
                description=getattr(row, "description", "") or "",
                extra=extra,
            )

    async def get_tasks_summary(
        self,
        project_id: str,
        member_id: str = "",
        since: datetime | None = None,
        until: datetime | None = None,
    ) -> TasksSummary:
        from openvort.plugins.vortflow.models import FlowBug, FlowTask

        sf = self._sf()
        async with sf() as session:
            task_q = select(sa_func.count()).select_from(FlowTask).where(FlowTask.project_id == project_id)
            task_done_q = task_q.where(FlowTask.state == "done")
            bug_q = select(sa_func.count()).select_from(FlowBug).where(FlowBug.project_id == project_id)
            bug_fixed_q = bug_q.where(FlowBug.state == "closed")

            if member_id:
                task_q = task_q.where(FlowTask.assignee_id == member_id)
                task_done_q = task_done_q.where(FlowTask.assignee_id == member_id)
                bug_q = bug_q.where(FlowBug.assignee_id == member_id)
                bug_fixed_q = bug_fixed_q.where(FlowBug.assignee_id == member_id)

            if since:
                task_q = task_q.where(FlowTask.updated_at >= since)
                task_done_q = task_done_q.where(FlowTask.updated_at >= since)
                bug_q = bug_q.where(FlowBug.updated_at >= since)
                bug_fixed_q = bug_fixed_q.where(FlowBug.updated_at >= since)

            if until:
                task_q = task_q.where(FlowTask.updated_at <= until)
                task_done_q = task_done_q.where(FlowTask.updated_at <= until)
                bug_q = bug_q.where(FlowBug.updated_at <= until)
                bug_fixed_q = bug_fixed_q.where(FlowBug.updated_at <= until)

            tasks_total = (await session.execute(task_q)).scalar() or 0
            tasks_done = (await session.execute(task_done_q)).scalar() or 0
            bugs_total = (await session.execute(bug_q)).scalar() or 0
            bugs_fixed = (await session.execute(bug_fixed_q)).scalar() or 0

        return TasksSummary(
            tasks_done=tasks_done,
            tasks_total=tasks_total,
            bugs_fixed=bugs_fixed,
            bugs_total=bugs_total,
        )
