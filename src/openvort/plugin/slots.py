"""
Standard Slot interfaces — contracts between core modules and plugins.

Slots are exclusive capability providers: only one plugin/module can register
a given slot. Consumers access data through these Protocol interfaces without
knowing (or importing) the actual provider.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Protocol, runtime_checkable


@dataclass
class ProjectInfo:
    id: str
    name: str
    description: str = ""
    members: list[str] = field(default_factory=list)


@dataclass
class WorkItemInfo:
    id: str
    title: str
    type: str  # story / task / bug
    status: str
    assignee: str = ""
    description: str = ""
    extra: dict = field(default_factory=dict)


@dataclass
class TasksSummary:
    tasks_done: int = 0
    tasks_total: int = 0
    bugs_fixed: int = 0
    bugs_total: int = 0
    stories_completed: int = 0
    stories_total: int = 0
    items: list[WorkItemInfo] = field(default_factory=list)


@runtime_checkable
class ProjectProvider(Protocol):
    """Slot: project_provider — project / story / task / bug data."""

    async def list_projects(self, member_id: str = "") -> list[ProjectInfo]: ...

    async def get_project(self, project_id: str) -> ProjectInfo | None: ...

    async def get_work_item(self, item_type: str, item_id: str) -> WorkItemInfo | None: ...

    async def get_tasks_summary(
        self,
        project_id: str,
        member_id: str = "",
        since: datetime | None = None,
        until: datetime | None = None,
    ) -> TasksSummary: ...
