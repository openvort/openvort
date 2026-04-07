"""
VortFlow implementation of the ProjectProvider slot.
"""

from __future__ import annotations

from datetime import datetime
from typing import Callable

from sqlalchemy import select, func as sa_func

from openvort.plugin.slots import ProjectInfo, TasksSummary, WorkItemInfo
from openvort.utils.logging import get_logger

log = get_logger("plugins.vortflow.provider")


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
            task_q = select(sa_func.count()).select_from(FlowTask)
            bug_q = select(sa_func.count()).select_from(FlowBug)

            if project_id:
                task_q = task_q.where(FlowTask.project_id == project_id)
                bug_q = bug_q.where(FlowBug.project_id == project_id)

            task_done_q = task_q.where(FlowTask.state == "done")
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

    async def get_member_daily_details(
        self,
        member_id: str,
        since: datetime,
        until: datetime,
    ) -> dict:
        """Get detailed work items and activity events for a member in a time range.

        Returns structured dict with tasks_completed, bugs_fixed, tasks_in_progress,
        stories_in_progress, events timeline, and summary counts.
        """
        from openvort.plugins.vortflow.models import (
            FlowBug, FlowEvent, FlowProject, FlowStory, FlowTask,
        )

        sf = self._sf()
        async with sf() as session:
            tasks_done = (await session.execute(
                select(FlowTask).where(
                    FlowTask.assignee_id == member_id,
                    FlowTask.state == "done",
                    FlowTask.updated_at >= since,
                    FlowTask.updated_at <= until,
                )
            )).scalars().all()

            bugs_fixed = (await session.execute(
                select(FlowBug).where(
                    FlowBug.assignee_id == member_id,
                    FlowBug.state.in_(("closed", "resolved")),
                    FlowBug.updated_at >= since,
                    FlowBug.updated_at <= until,
                )
            )).scalars().all()

            tasks_doing = (await session.execute(
                select(FlowTask).where(
                    FlowTask.assignee_id == member_id,
                    FlowTask.state.in_(("doing", "in_progress")),
                )
            )).scalars().all()

            stories = (await session.execute(
                select(FlowStory).where(
                    FlowStory.assignee_id == member_id,
                    FlowStory.state.in_(("developing", "reviewing", "testing")),
                )
            )).scalars().all()

            events = (await session.execute(
                select(FlowEvent).where(
                    FlowEvent.actor_id == member_id,
                    FlowEvent.created_at >= since,
                    FlowEvent.created_at <= until,
                ).order_by(FlowEvent.created_at.asc()).limit(100)
            )).scalars().all()

            project_ids = set()
            for items in (tasks_done, bugs_fixed, tasks_doing, stories):
                for item in items:
                    pid = getattr(item, "project_id", None)
                    if pid:
                        project_ids.add(pid)

            project_names: dict[str, str] = {}
            if project_ids:
                proj_rows = (await session.execute(
                    select(FlowProject.id, FlowProject.name)
                    .where(FlowProject.id.in_(list(project_ids)))
                )).all()
                project_names = {pid: pname for pid, pname in proj_rows}

            entity_ids_by_type: dict[str, set[str]] = {}
            for ev in events:
                entity_ids_by_type.setdefault(ev.entity_type, set()).add(ev.entity_id)

            entity_titles: dict[str, str] = {}
            model_map = {"task": FlowTask, "bug": FlowBug, "story": FlowStory}
            for etype, eids in entity_ids_by_type.items():
                model = model_map.get(etype)
                if model and eids:
                    rows = (await session.execute(
                        select(model.id, model.title).where(model.id.in_(list(eids)))
                    )).all()
                    for eid, title in rows:
                        entity_titles[f"{etype}:{eid}"] = title

        severity_labels = {1: "致命", 2: "严重", 3: "一般", 4: "轻微"}

        def _item_dict(item, item_type: str) -> dict:
            pid = getattr(item, "project_id", "") or ""
            d = {
                "id": item.id,
                "title": item.title,
                "type": item_type,
                "state": getattr(item, "state", ""),
                "project_name": project_names.get(pid, ""),
            }
            if item_type == "bug":
                d["severity"] = severity_labels.get(getattr(item, "severity", 3), "一般")
            if item_type == "task":
                d["task_type"] = getattr(item, "task_type", "")
            progress = getattr(item, "progress", None)
            if progress is not None:
                d["progress"] = progress
            return d

        type_labels = {"story": "需求", "task": "任务", "bug": "缺陷", "project": "项目"}
        events_list = []
        for ev in events:
            key = f"{ev.entity_type}:{ev.entity_id}"
            events_list.append({
                "entity_type": type_labels.get(ev.entity_type, ev.entity_type),
                "entity_title": entity_titles.get(key, ev.entity_id),
                "action": ev.action,
                "detail": ev.detail,
                "time": ev.created_at.strftime("%H:%M") if ev.created_at else "",
            })

        has_data = bool(tasks_done or bugs_fixed or tasks_doing or stories or events)

        return {
            "has_data": has_data,
            "tasks_completed": [_item_dict(t, "task") for t in tasks_done],
            "bugs_fixed": [_item_dict(b, "bug") for b in bugs_fixed],
            "tasks_in_progress": [_item_dict(t, "task") for t in tasks_doing],
            "stories_in_progress": [_item_dict(s, "story") for s in stories],
            "events": events_list,
            "summary": {
                "tasks_completed_count": len(tasks_done),
                "bugs_fixed_count": len(bugs_fixed),
                "tasks_in_progress_count": len(tasks_doing),
                "stories_in_progress_count": len(stories),
                "events_count": len(events),
            },
        }
