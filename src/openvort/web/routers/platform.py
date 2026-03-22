"""
Platform standard API — Slot-backed endpoints for cross-module data access.

Plugins call these instead of importing core module APIs directly.
"""

from fastapi import APIRouter, Depends

from openvort.web.deps import get_registry

router = APIRouter()


@router.get("/projects")
async def list_projects(registry=Depends(get_registry)):
    provider = registry.get_slot("project_provider")
    if not provider:
        return {"items": []}
    projects = await provider.list_projects()
    return {"items": [{"id": p.id, "name": p.name, "description": p.description} for p in projects]}


@router.get("/projects/{project_id}")
async def get_project(project_id: str, registry=Depends(get_registry)):
    provider = registry.get_slot("project_provider")
    if not provider:
        return None
    project = await provider.get_project(project_id)
    if not project:
        return None
    return {"id": project.id, "name": project.name, "description": project.description}
