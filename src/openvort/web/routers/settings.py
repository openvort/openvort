"""系统设置路由"""

import os
import sys
import threading

from fastapi import APIRouter
from pydantic import BaseModel

from openvort.config.settings import get_settings

router = APIRouter()


@router.get("")
async def get_current_settings():
    settings = get_settings()
    return {
        "llm_model": settings.llm.model,
        "llm_api_base": settings.llm.api_base,
        "llm_max_tokens": settings.llm.max_tokens,
        "llm_timeout": settings.llm.timeout,
    }


class UpdateSettingsRequest(BaseModel):
    llm_model: str | None = None
    llm_api_base: str | None = None
    llm_max_tokens: int | None = None
    llm_timeout: int | None = None


@router.put("")
async def update_settings(req: UpdateSettingsRequest):
    """更新设置（运行时生效，不持久化到 .env）"""
    settings = get_settings()
    if req.llm_model is not None:
        settings.llm.model = req.llm_model
    if req.llm_api_base is not None:
        settings.llm.api_base = req.llm_api_base
    if req.llm_max_tokens is not None:
        settings.llm.max_tokens = req.llm_max_tokens
    if req.llm_timeout is not None:
        settings.llm.timeout = req.llm_timeout
    return {"success": True}


@router.post("/restart")
async def restart_service():
    """重启后端服务（仅管理员，由 app.py 的 require_admin 保护）"""
    import logging
    log = logging.getLogger("openvort.web")
    log.info("收到重启请求，将在 1 秒后重启...")

    def _do_restart():
        import time
        time.sleep(1)  # 等待响应返回给前端
        # 清理 PID 文件
        from openvort.cli import _cleanup_pid
        _cleanup_pid()
        # 用 os.execv 替换当前进程，实现原地重启
        os.execv(sys.executable, [sys.executable] + sys.argv)

    threading.Thread(target=_do_restart, daemon=True).start()
    return {"success": True, "message": "服务即将重启"}
