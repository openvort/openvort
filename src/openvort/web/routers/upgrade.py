"""System upgrade & backup management router."""

import json

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse, StreamingResponse
from pydantic import BaseModel

from openvort.core.updater import get_update_service
from openvort.utils.logging import get_logger

log = get_logger("web.upgrade")

router = APIRouter()


# ------------------------------------------------------------------ #
#  Version check & upgrade
# ------------------------------------------------------------------ #


@router.get("/check")
async def check_upgrade(force: bool = False):
    """Check for available updates."""
    svc = get_update_service()
    return await svc.check_update(force=force)


@router.get("/releases")
async def list_releases(per_page: int = 20):
    """List recent GitHub releases for version selection."""
    svc = get_update_service()
    return await svc.get_releases(per_page=per_page)


class ApplyUpgradeRequest(BaseModel):
    version: str


@router.post("/apply")
async def apply_upgrade(req: ApplyUpgradeRequest):
    """Apply upgrade/downgrade to a specified version. Returns SSE stream."""
    svc = get_update_service()
    if svc.is_upgrading:
        raise HTTPException(status_code=409, detail="已有升级任务正在执行")

    async def _stream():
        async for event in svc.apply_update(req.version):
            yield event

    return StreamingResponse(_stream(), media_type="text/event-stream")


# ------------------------------------------------------------------ #
#  Backup management
# ------------------------------------------------------------------ #


@router.get("/backups")
async def list_backups():
    """List database backup files."""
    svc = get_update_service()
    return svc.list_backups()


@router.post("/backups")
async def create_backup():
    """Manually create a database backup."""
    svc = get_update_service()
    try:
        info = await svc.backup_database()
        return info
    except Exception as e:
        log.error(f"手动备份失败: {e}")
        raise HTTPException(status_code=500, detail=f"备份失败: {e}")


@router.get("/backups/{filename}")
async def download_backup(filename: str):
    """Download a backup file."""
    svc = get_update_service()
    path = svc.get_backup_path(filename)
    if not path:
        raise HTTPException(status_code=404, detail="备份文件不存在")
    return FileResponse(
        path=str(path),
        filename=filename,
        media_type="application/sql",
    )


@router.delete("/backups/{filename}")
async def delete_backup(filename: str):
    """Delete a backup file."""
    svc = get_update_service()
    if svc.delete_backup(filename):
        return {"success": True}
    raise HTTPException(status_code=404, detail="备份文件不存在")


@router.post("/backups/{filename}/restore")
async def restore_backup(filename: str):
    """Restore database from a backup. Returns SSE stream."""
    svc = get_update_service()
    if not svc.get_backup_path(filename):
        raise HTTPException(status_code=404, detail="备份文件不存在")

    async def _stream():
        async for event in svc.restore_database(filename):
            yield event

    return StreamingResponse(_stream(), media_type="text/event-stream")
