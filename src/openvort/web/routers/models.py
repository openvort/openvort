"""模型管理路由（CRUD + 连通性测试）"""

import time
from typing import Any

from fastapi import APIRouter
from pydantic import BaseModel

from openvort.web.deps import get_config_service

router = APIRouter()


def _mask_key(api_key: str) -> str:
    if not api_key:
        return ""
    if len(api_key) > 8:
        return api_key[:3] + "***" + api_key[-4:]
    return "***"


class ModelCreateRequest(BaseModel):
    name: str
    provider: str
    model: str
    api_key: str = ""
    api_base: str = ""
    max_tokens: int = 4096
    timeout: int = 120
    enabled: bool = True


class ModelUpdateRequest(BaseModel):
    name: str | None = None
    provider: str | None = None
    model: str | None = None
    api_key: str | None = None
    api_base: str | None = None
    max_tokens: int | None = None
    timeout: int | None = None
    enabled: bool | None = None


@router.get("")
async def list_models():
    config_service = get_config_service()
    models = await config_service.get_llm_models()
    result = []
    for item in models:
        masked = dict(item)
        masked["api_key"] = _mask_key(str(item.get("api_key", "")))
        result.append(masked)
    return result


@router.post("")
async def create_model(req: ModelCreateRequest):
    config_service = get_config_service()
    models = await config_service.get_llm_models()
    models.append(req.model_dump())
    await config_service.save_llm_models(models)
    return {"success": True}


@router.put("/{model_id}")
async def update_model(model_id: str, req: ModelUpdateRequest):
    config_service = get_config_service()
    models = await config_service.get_llm_models()
    target: dict[str, Any] | None = None
    for item in models:
        if item.get("id") == model_id:
            target = item
            break
    if not target:
        return {"success": False, "error": "模型不存在"}

    updates = req.model_dump(exclude_unset=True)
    if "api_key" in updates and (updates["api_key"] is None or "***" in str(updates["api_key"])):
        updates.pop("api_key", None)
    target.update(updates)
    await config_service.save_llm_models(models)
    return {"success": True}


@router.delete("/{model_id}")
async def delete_model(model_id: str):
    config_service = get_config_service()
    primary_model_id, fallback_model_ids = await config_service.get_llm_model_selection()
    if model_id == primary_model_id or model_id in fallback_model_ids:
        return {"success": False, "error": "模型正在被主模型或备选模型引用，请先在系统设置中解绑"}

    cli_cfg = await config_service.get_cli_config()
    if model_id == cli_cfg["cli_primary_model_id"] or model_id in cli_cfg["cli_fallback_model_ids"]:
        return {"success": False, "error": "模型正在被 AI 编码配置引用，请先在系统设置中解绑"}

    models = await config_service.get_llm_models()
    new_models = [item for item in models if item.get("id") != model_id]
    if len(new_models) == len(models):
        return {"success": False, "error": "模型不存在"}
    await config_service.save_llm_models(new_models)
    return {"success": True}


@router.post("/{model_id}/test")
async def test_model(model_id: str):
    """Test model connectivity by sending a minimal request."""
    from openvort.core.llm import create_provider

    config_service = get_config_service()
    models = await config_service.get_llm_models()
    target: dict[str, Any] | None = None
    for item in models:
        if item.get("id") == model_id:
            target = item
            break
    if not target:
        return {"success": False, "error": "模型不存在"}

    provider_name = target.get("provider", "anthropic")
    api_key = target.get("api_key", "")
    api_base = target.get("api_base", "")
    model_name = target.get("model", "")
    timeout = target.get("timeout", 30)

    if not api_key:
        return {"success": False, "error": "API Key 未配置"}
    if not model_name:
        return {"success": False, "error": "模型名称未配置"}

    provider = create_provider(
        provider=provider_name,
        api_key=api_key,
        api_base=api_base,
        timeout=min(timeout, 30),
    )
    try:
        t0 = time.monotonic()
        resp = await provider.create(
            model=model_name,
            max_tokens=32,
            system="You are a test assistant.",
            messages=[{"role": "user", "content": "Hi"}],
        )
        latency_ms = int((time.monotonic() - t0) * 1000)
        reply = ""
        for block in resp.content:
            if hasattr(block, "text"):
                reply += block.text
        return {
            "success": True,
            "latency_ms": latency_ms,
            "reply": reply[:200],
            "usage": {
                "input_tokens": resp.usage.input_tokens,
                "output_tokens": resp.usage.output_tokens,
            },
        }
    except Exception as e:
        return {"success": False, "error": str(e)[:500]}
    finally:
        await provider.close()
