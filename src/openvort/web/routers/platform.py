"""
Platform standard API — Slot-backed endpoints for cross-module data access.

Plugins call these instead of importing core module APIs directly.
"""

import logging

from fastapi import APIRouter, Depends

from openvort.web.deps import get_registry

router = APIRouter()
log = logging.getLogger(__name__)


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


@router.get("/ui-extensions")
async def get_ui_extensions(registry=Depends(get_registry)):
    """Aggregate UI extension declarations from all enabled plugins."""
    extensions = []
    for plugin in registry.list_plugins():
        if registry.is_plugin_disabled(plugin.name):
            continue
        try:
            ui_ext = plugin.get_ui_extensions()
            if ui_ext:
                extensions.append({
                    "plugin": plugin.name,
                    "display_name": plugin.display_name,
                    **ui_ext,
                })
        except Exception as e:
            log.warning(f"获取插件 '{plugin.name}' UI 扩展失败: {e}")
    return {"extensions": extensions}
