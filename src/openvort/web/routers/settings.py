"""系统设置路由"""

import os
import sys
import json
import asyncio
import threading

from fastapi import APIRouter
from pydantic import BaseModel

from openvort.config.settings import get_settings
from openvort.web.deps import get_config_service
from openvort.utils.logging import get_logger

log = get_logger("web.settings")

router = APIRouter()


def _mask_key(api_key: str) -> str:
    if not api_key:
        return ""
    if len(api_key) > 8:
        return api_key[:3] + "***" + api_key[-4:]
    return "***"


@router.get("")
async def get_current_settings():
    config_service = get_config_service()
    settings = get_settings()
    models = await config_service.get_llm_models()
    primary_model_id, fallback_model_ids = await config_service.get_llm_model_selection()
    model_summary = [
        {
            "id": item.get("id", ""),
            "name": item.get("name", ""),
            "provider": item.get("provider", ""),
            "model": item.get("model", ""),
            "enabled": item.get("enabled", True),
        }
        for item in models
    ]

    return {
        "llm_primary_model_id": primary_model_id,
        "llm_fallback_model_ids": fallback_model_ids,
        "llm_models": model_summary,
        # 兼容旧前端字段
        "llm_provider": settings.llm.provider,
        "llm_api_key": _mask_key(settings.llm.api_key),
        "llm_model": settings.llm.model,
        "llm_api_base": settings.llm.api_base,
        "llm_max_tokens": settings.llm.max_tokens,
        "llm_timeout": settings.llm.timeout
    }


class FallbackModelItem(BaseModel):
    provider: str = "openai"
    api_key: str = ""
    api_base: str = ""
    model: str = ""
    max_tokens: int = 4096
    timeout: int = 120


class UpdateSettingsRequest(BaseModel):
    llm_primary_model_id: str | None = None
    llm_fallback_model_ids: list[str] | None = None

    # 兼容旧请求字段
    llm_provider: str | None = None
    llm_api_key: str | None = None
    llm_model: str | None = None
    llm_api_base: str | None = None
    llm_max_tokens: int | None = None
    llm_timeout: int | None = None
    llm_fallback_models: list[FallbackModelItem] | None = None  # deprecated


async def _reload_llm_client() -> None:
    """热更新运行时的 LLMClient，无需重启"""
    try:
        from openvort.web.deps import get_agent, get_config_service
        from openvort.core.llm import LLMClient
        settings = get_settings()
        config_service = get_config_service()
        chain = await config_service.get_effective_llm_chain()
        if not chain:
            chain = settings.llm.get_model_chain()
        agent = get_agent()
        try:
            loop = asyncio.get_running_loop()
            loop.create_task(agent._llm.close())
        except Exception:
            pass
        agent._llm = LLMClient(chain)
        agent._model = settings.llm.model
        agent._max_tokens = settings.llm.max_tokens
        log.info(f"LLMClient 已热更新: provider={settings.llm.provider}, model={settings.llm.model}, api_base={settings.llm.api_base}")
    except Exception as e:
        log.warning(f"热更新 LLMClient 失败: {e}")


@router.put("")
async def update_settings(req: UpdateSettingsRequest):
    """更新设置（保存到数据库 + 热更新 LLMClient）"""
    config_service = get_config_service()

    if req.llm_primary_model_id is not None or req.llm_fallback_model_ids is not None:
        current_primary, current_fallback = await config_service.get_llm_model_selection()
        primary_id = req.llm_primary_model_id if req.llm_primary_model_id is not None else current_primary
        fallback_ids = req.llm_fallback_model_ids if req.llm_fallback_model_ids is not None else current_fallback
        await config_service.save_llm_model_selection(primary_id, fallback_ids)

    data: dict = {}
    if req.llm_provider is not None:
        data["provider"] = req.llm_provider
    if req.llm_api_key is not None and "***" not in req.llm_api_key:
        data["api_key"] = req.llm_api_key
    if req.llm_model is not None:
        data["model"] = req.llm_model
    if req.llm_api_base is not None:
        data["api_base"] = req.llm_api_base
    if req.llm_max_tokens is not None:
        data["max_tokens"] = req.llm_max_tokens
    if req.llm_timeout is not None:
        data["timeout"] = req.llm_timeout
    if req.llm_fallback_models is not None:
        data["fallback_models"] = json.dumps([m.model_dump() for m in req.llm_fallback_models], ensure_ascii=False)

    if data:
        await config_service.save_llm_settings(data)
    await config_service.apply_llm_to_settings()
    await _reload_llm_client()

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
