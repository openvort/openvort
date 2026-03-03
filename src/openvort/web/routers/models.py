"""模型管理路由（CRUD + 连通性测试 + API 格式自动检测）"""

import asyncio
import time
from typing import Any

from fastapi import APIRouter
from pydantic import BaseModel

from openvort.utils.logging import get_logger
from openvort.web.deps import get_config_service

log = get_logger("web.models")

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
    api_format: str = "auto"


class ModelUpdateRequest(BaseModel):
    name: str | None = None
    provider: str | None = None
    model: str | None = None
    api_key: str | None = None
    api_base: str | None = None
    max_tokens: int | None = None
    timeout: int | None = None
    enabled: bool | None = None
    api_format: str | None = None


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


class FetchModelsRequest(BaseModel):
    provider: str
    api_key: str = ""
    api_base: str = ""


@router.post("/fetch-available")
async def fetch_available_models(req: FetchModelsRequest):
    """Fetch available models from the provider API using the given credentials."""
    import httpx

    provider_name = req.provider
    api_key = req.api_key
    api_base = req.api_base

    if not api_key:
        return {"success": False, "error": "API Key 未填写"}

    try:
        if provider_name == "anthropic":
            base = api_base.rstrip("/") if api_base else "https://api.anthropic.com"
            if base.endswith("/v1"):
                base = base[:-3]
            async with httpx.AsyncClient(timeout=15) as client:
                resp = await client.get(
                    f"{base}/v1/models",
                    headers={
                        "x-api-key": api_key,
                        "anthropic-version": "2023-06-01",
                    },
                )
                if resp.status_code == 200:
                    data = resp.json()
                    models = []
                    for m in data.get("data", []):
                        model_id = m.get("id", "")
                        if model_id:
                            models.append(model_id)
                    models.sort()
                    return {"success": True, "models": models}
                else:
                    return {"success": False, "error": f"HTTP {resp.status_code}: {resp.text[:200]}"}
        else:
            # OpenAI-compatible providers
            from openvort.core.llm import _default_api_base
            base = (api_base or _default_api_base(provider_name)).rstrip("/")
            if not base.endswith("/v1"):
                base = base + "/v1"
            async with httpx.AsyncClient(timeout=15) as client:
                resp = await client.get(
                    f"{base}/models",
                    headers={"Authorization": f"Bearer {api_key}"},
                )
                if resp.status_code == 200:
                    data = resp.json()
                    models = []
                    for m in data.get("data", []):
                        model_id = m.get("id", "")
                        if model_id:
                            models.append(model_id)
                    models.sort()
                    return {"success": True, "models": models}
                else:
                    return {"success": False, "error": f"HTTP {resp.status_code}: {resp.text[:200]}"}
    except httpx.TimeoutException:
        return {"success": False, "error": "请求超时，请检查 API Base 地址"}
    except Exception as e:
        return {"success": False, "error": str(e)[:300]}


@router.post("/batch-test")
async def batch_test_models():
    """Test all models in parallel and return results."""
    config_service = get_config_service()
    models = await config_service.get_llm_models()

    async def _test_one(item: dict) -> dict:
        model_id = item.get("id", "")
        provider_name = item.get("provider", "anthropic")
        api_key = item.get("api_key", "")
        api_base_val = item.get("api_base", "")
        model_name = item.get("model", "")
        timeout_val = item.get("timeout", 30)
        api_format = item.get("api_format", "auto")

        if not api_key:
            return {"id": model_id, "success": False, "error": "API Key 未配置"}
        if not model_name:
            return {"id": model_id, "success": False, "error": "模型名称未配置"}

        if provider_name == "anthropic":
            result = await _try_provider(
                provider_name, api_key, api_base_val, model_name, timeout_val, "chat_completions",
            )
        elif api_format != "auto":
            result = await _try_provider(
                provider_name, api_key, api_base_val, model_name, timeout_val, api_format,
            )
        else:
            result = await _try_provider(
                provider_name, api_key, api_base_val, model_name, min(timeout_val, 15), "chat_completions",
            )
            if not result["success"]:
                result = await _try_provider(
                    provider_name, api_key, api_base_val, model_name, min(timeout_val, 15), "responses",
                )
        result["id"] = model_id
        return result

    tasks = [_test_one(item) for item in models]
    results = await asyncio.gather(*tasks, return_exceptions=True)

    output = []
    for i, r in enumerate(results):
        if isinstance(r, Exception):
            output.append({"id": models[i].get("id", ""), "success": False, "error": str(r)[:200]})
        else:
            output.append(r)
    return output


async def _try_provider(provider_name: str, api_key: str, api_base: str,
                        model_name: str, timeout: int,
                        api_format: str) -> dict[str, Any]:
    """Attempt a minimal LLM call with the given api_format. Returns result dict."""
    from openvort.core.llm import create_provider

    provider = create_provider(
        provider=provider_name, api_key=api_key, api_base=api_base,
        timeout=min(timeout, 30), api_format=api_format,
    )
    try:
        t0 = time.monotonic()
        resp = await provider.create(
            model=model_name, max_tokens=32,
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
            "api_format": api_format,
            "usage": {
                "input_tokens": resp.usage.input_tokens,
                "output_tokens": resp.usage.output_tokens,
            },
        }
    except Exception as e:
        return {"success": False, "error": str(e)[:500], "api_format": api_format}
    finally:
        await provider.close()


@router.post("/{model_id}/test")
async def test_model(model_id: str):
    """Test model connectivity with auto-detection of API format."""
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
    api_format = target.get("api_format", "auto")

    if not api_key:
        return {"success": False, "error": "API Key 未配置"}
    if not model_name:
        return {"success": False, "error": "模型名称未配置"}

    if provider_name == "anthropic":
        result = await _try_provider(
            provider_name, api_key, api_base, model_name, timeout, "chat_completions",
        )
        return result

    if api_format != "auto":
        result = await _try_provider(
            provider_name, api_key, api_base, model_name, timeout, api_format,
        )
        return result

    # Auto-detect: try chat_completions first, fallback to responses
    # Use shorter timeout for detection to avoid long waits
    detect_timeout = min(timeout, 15)
    result = await _try_provider(
        provider_name, api_key, api_base, model_name, detect_timeout, "chat_completions",
    )
    if result["success"]:
        result["detected_format"] = "chat_completions"
        await _save_detected_format(config_service, models, model_id, "chat_completions")
        return result

    first_error = result.get("error", "")
    log.info(f"模型 {model_name} chat_completions 失败 ({first_error[:80]}), 尝试 responses API...")

    result = await _try_provider(
        provider_name, api_key, api_base, model_name, detect_timeout, "responses",
    )
    if result["success"]:
        result["detected_format"] = "responses"
        await _save_detected_format(config_service, models, model_id, "responses")
        return result

    return {
        "success": False,
        "error": f"两种格式均失败。Chat Completions: {first_error[:200]}; "
                 f"Responses API: {result.get('error', '')[:200]}",
    }


async def _save_detected_format(config_service, models: list[dict],
                                model_id: str, detected: str) -> None:
    """Persist the detected api_format back to the model config."""
    for item in models:
        if item.get("id") == model_id:
            if item.get("api_format", "auto") == "auto":
                item["api_format"] = detected
                await config_service.save_llm_models(models)
                log.info(f"模型 {model_id} 自动检测到 api_format={detected}, 已保存")
            break
