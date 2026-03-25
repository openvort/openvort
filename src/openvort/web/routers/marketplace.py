"""
Marketplace API router for the OpenVort admin panel.

Endpoints for searching, installing, and managing marketplace extensions.
"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from openvort.web.deps import get_marketplace_installer

router = APIRouter()


class InstallRequest(BaseModel):
    slug: str
    author: str = ""


class UninstallRequest(BaseModel):
    slug: str
    type: str = "skill"


@router.get("/search")
async def search_marketplace(
    query: str = "",
    type: str = "all",
    category: str = "",
    sort: str = "latest",
    page: int = 1,
    limit: int = 12,
):
    """Search the remote marketplace."""
    installer = get_marketplace_installer()
    if not installer:
        raise HTTPException(status_code=503, detail="Marketplace not configured")

    try:
        result = await installer.client.search(
            query=query, type=type, category=category,
            sort=sort, page=page, limit=limit,
        )
        return result
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Marketplace request failed: {e}")


@router.get("/detail/{slug}")
async def get_extension_detail(slug: str, author: str = ""):
    """Get full extension detail by slug, enriched with local registry data."""
    installer = get_marketplace_installer()
    if not installer:
        raise HTTPException(status_code=503, detail="Marketplace not configured")

    try:
        result = await installer.client.get_extension_detail(slug, author=author)
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Marketplace request failed: {e}")

    if isinstance(result, dict) and result.get("type") == "plugin":
        plugin = installer.registry.get_plugin(slug)
        if plugin:
            tools = [{"name": t.name, "description": t.description} for t in plugin.get_tools()]
            result["tools"] = tools
            result["toolsCount"] = len(tools)
            result["promptsCount"] = len(plugin.get_prompts())
            result["localEnabled"] = not installer.registry.is_plugin_disabled(slug)

    return result


@router.post("/install/skill")
async def install_skill(req: InstallRequest):
    """Install a skill from the marketplace (supports content and bundle)."""
    installer = get_marketplace_installer()
    if not installer:
        raise HTTPException(status_code=503, detail="Marketplace not configured")

    try:
        result = await installer.install_skill(req.slug, author=req.author)
        return result
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Installation failed: {e}")


@router.post("/install/plugin")
async def install_plugin(req: InstallRequest):
    """Install a plugin from the marketplace (supports pip and bundle)."""
    installer = get_marketplace_installer()
    if not installer:
        raise HTTPException(status_code=503, detail="Marketplace not configured")

    try:
        result = await installer.install_plugin(req.slug, author=req.author)
        return result
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except RuntimeError as e:
        raise HTTPException(status_code=500, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Installation failed: {e}")


@router.get("/installed")
async def list_installed():
    """List marketplace-installed extensions (skills + plugin bundles)."""
    installer = get_marketplace_installer()
    if not installer:
        raise HTTPException(status_code=503, detail="Marketplace not configured")

    return await installer.list_installed()


@router.post("/uninstall")
async def uninstall_extension(req: UninstallRequest):
    """Uninstall a marketplace extension (skill or plugin)."""
    installer = get_marketplace_installer()
    if not installer:
        raise HTTPException(status_code=503, detail="Marketplace not configured")

    try:
        if req.type == "plugin":
            result = await installer.uninstall_plugin(req.slug)
        else:
            result = await installer.uninstall_skill(req.slug)
        return result
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Uninstall failed: {e}")


@router.get("/updates")
async def check_updates():
    """Check for available updates (compares version + content hash)."""
    installer = get_marketplace_installer()
    if not installer:
        raise HTTPException(status_code=503, detail="Marketplace not configured")

    updates = await installer.check_updates()
    return {"updates": updates, "count": len(updates)}
