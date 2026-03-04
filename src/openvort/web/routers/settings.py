"""系统设置路由"""

import os
import sys
import json
import asyncio
import subprocess
import threading

from fastapi import APIRouter
from fastapi.responses import StreamingResponse
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
    cli_config = await config_service.get_cli_config()
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

    cli_tools_info = _get_cli_tools_info()

    from openvort.plugins.vortgit.cli_runner import CLIRunner
    cli_tools_status = CLIRunner.get_tools_status()

    return {
        "llm_primary_model_id": primary_model_id,
        "llm_fallback_model_ids": fallback_model_ids,
        "llm_models": model_summary,
        # CLI coding config
        "cli_default_tool": cli_config["cli_default_tool"],
        "cli_primary_model_id": cli_config["cli_primary_model_id"],
        "cli_fallbacks": cli_config["cli_fallbacks"],
        "cli_fallback_model_ids": cli_config["cli_fallback_model_ids"],
        "cli_tools": cli_tools_info,
        "cli_tools_status": cli_tools_status,
        # 兼容旧前端字段
        "llm_provider": settings.llm.provider,
        "llm_api_key": _mask_key(settings.llm.api_key),
        "llm_model": settings.llm.model,
        "llm_api_base": settings.llm.api_base,
        "llm_max_tokens": settings.llm.max_tokens,
        "llm_timeout": settings.llm.timeout,
    }


def _get_cli_tools_info() -> list[dict]:
    """Return CLI tool specs for frontend display/filtering."""
    try:
        from openvort.plugins.vortgit.cli_runner import BUILTIN_CLI_TOOLS
        return [
            {
                "name": spec.name,
                "display_name": spec.display_name,
                "supported_providers": spec.supported_providers,
            }
            for spec in BUILTIN_CLI_TOOLS.values()
        ]
    except Exception:
        return []


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

    # CLI coding config
    cli_default_tool: str | None = None
    cli_primary_model_id: str | None = None
    cli_fallbacks: list[dict] | None = None
    cli_fallback_model_ids: list[str] | None = None  # legacy compat

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

    # CLI coding config
    if any(v is not None for v in [req.cli_default_tool, req.cli_primary_model_id, req.cli_fallbacks, req.cli_fallback_model_ids]):
        await config_service.save_cli_config(
            default_tool=req.cli_default_tool,
            primary_model_id=req.cli_primary_model_id,
            fallbacks=req.cli_fallbacks,
            fallback_model_ids=req.cli_fallback_model_ids if req.cli_fallbacks is None else None,
        )

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
        time.sleep(1)
        from openvort.cli import _cleanup_pid
        _cleanup_pid()
        os.execv(sys.executable, [sys.executable] + sys.argv)

    threading.Thread(target=_do_restart, daemon=True).start()
    return {"success": True, "message": "服务即将重启"}


# ---- CLI 工具管理 API ----


@router.get("/cli-tools")
async def list_cli_tools():
    """Return install status of all built-in CLI tools."""
    from openvort.plugins.vortgit.cli_runner import CLIRunner
    return CLIRunner.get_tools_status()


@router.post("/cli-tools/{tool_name}/install")
async def install_cli_tool(tool_name: str):
    """Install a CLI tool via SSE stream."""
    from openvort.plugins.vortgit.cli_runner import BUILTIN_CLI_TOOLS
    spec = BUILTIN_CLI_TOOLS.get(tool_name)
    if not spec:
        return {"success": False, "error": f"Unknown tool: {tool_name}"}

    async def _stream():
        yield f"data: {json.dumps({'type': 'start', 'cmd': spec.install_cmd})}\n\n"
        try:
            proc = await asyncio.create_subprocess_shell(
                spec.install_cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.STDOUT,
            )
            async for line in proc.stdout:
                text = line.decode(errors="replace").rstrip()
                yield f"data: {json.dumps({'type': 'output', 'text': text})}\n\n"
            await proc.wait()
            success = proc.returncode == 0
            yield f"data: {json.dumps({'type': 'done', 'success': success, 'exit_code': proc.returncode})}\n\n"
        except Exception as e:
            yield f"data: {json.dumps({'type': 'error', 'text': str(e)})}\n\n"

    return StreamingResponse(_stream(), media_type="text/event-stream")


@router.post("/cli-tools/{tool_name}/uninstall")
async def uninstall_cli_tool(tool_name: str):
    """Uninstall a CLI tool via SSE stream."""
    from openvort.plugins.vortgit.cli_runner import BUILTIN_CLI_TOOLS
    spec = BUILTIN_CLI_TOOLS.get(tool_name)
    if not spec or not spec.uninstall_cmd:
        return {"success": False, "error": f"No uninstall command for: {tool_name}"}

    async def _stream():
        yield f"data: {json.dumps({'type': 'start', 'cmd': spec.uninstall_cmd})}\n\n"
        try:
            proc = await asyncio.create_subprocess_shell(
                spec.uninstall_cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.STDOUT,
            )
            async for line in proc.stdout:
                text = line.decode(errors="replace").rstrip()
                yield f"data: {json.dumps({'type': 'output', 'text': text})}\n\n"
            await proc.wait()
            success = proc.returncode == 0
            yield f"data: {json.dumps({'type': 'done', 'success': success, 'exit_code': proc.returncode})}\n\n"
        except Exception as e:
            yield f"data: {json.dumps({'type': 'error', 'text': str(e)})}\n\n"

    return StreamingResponse(_stream(), media_type="text/event-stream")
